"""Read one server-configured Google Sheet; never persist the source or credentials."""
import asyncio
from contextlib import contextmanager
from datetime import datetime, timezone
from io import BytesIO
import json
import os
import re
from time import time
from urllib.parse import urlsplit

import aiohttp
from google.auth import jwt
from google.oauth2.service_account import Credentials

from api.parsers.finance_workbook import MIME
from api.services.finance_runs import FinanceRunError

SCOPE = 'https://www.googleapis.com/auth/drive.readonly'
TOKEN_URL = 'https://oauth2.googleapis.com/token'
MAX_EXPORT_BYTES = 10 * 1024 * 1024  # Drive files.export provider limit.
MAX_METADATA_BYTES = 16 * 1024
ACQUISITION_SECONDS = 60
CHUNK_BYTES = 16 * 1024


async def _read(session, url, *, limit, headers, method='GET', body=None):
    async with session.request(method, url, data=body,
            headers={**headers, 'Accept-Encoding': 'identity'}, allow_redirects=False) as response:
        if response.status in (401, 403):
            raise FinanceRunError('BUDGET_PULL_ACCESS_DENIED', status=503)
        if response.status == 429:
            raise FinanceRunError('BUDGET_PULL_QUOTA', status=503)
        if response.status != 200 or response.headers.get('Content-Encoding', 'identity').lower() != 'identity':
            raise FinanceRunError('BUDGET_PULL_UNAVAILABLE', status=503)
        with BytesIO() as buffer:
            while True:
                chunk = await response.content.read(min(CHUNK_BYTES, limit - buffer.tell() + 1))
                if not chunk:
                    break
                buffer.write(chunk)
                if buffer.tell() > limit:
                    raise FinanceRunError('BUDGET_PULL_SIZE_LIMIT', status=400)
            return buffer.getvalue()


async def _metadata(session, url, headers):
    try:
        data = json.loads(await _read(session, url, limit=MAX_METADATA_BYTES, headers=headers))
        modified = data['modifiedTime']
        stamp = datetime.fromisoformat(modified.replace('Z', '+00:00'))
        if (stamp.utcoffset() is None or data['mimeType'] != 'application/vnd.google-apps.spreadsheet'
                or not isinstance(data['version'], str) or not data['version'].isdigit()):
            raise ValueError()
        return (modified, data['version']), stamp.astimezone(timezone.utc)
    except FinanceRunError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError):
        raise FinanceRunError('BUDGET_PULL_METADATA_INVALID', status=400) from None


async def _acquire(sheet_id, assertion):
    # One cancellable deadline covers DNS, TLS, headers and every response body.
    # AsyncResolver avoids an uncancellable getaddrinfo executor thread at shutdown.
    async with asyncio.timeout(ACQUISITION_SECONDS):
        resolver = aiohttp.AsyncResolver()
        try:
            connector = aiohttp.TCPConnector(resolver=resolver, limit=1)
            async with aiohttp.ClientSession(connector=connector,
                    timeout=aiohttp.ClientTimeout(total=ACQUISITION_SECONDS, sock_connect=5, sock_read=5),
                    auto_decompress=False, trust_env=False, cookie_jar=aiohttp.DummyCookieJar(),
                    read_bufsize=CHUNK_BYTES, max_line_size=8190, max_field_size=8190, max_headers=64) as session:
                token_data = json.loads(await _read(session, TOKEN_URL, limit=MAX_METADATA_BYTES,
                    method='POST', headers={}, body={'grant_type':'urn:ietf:params:oauth:grant-type:jwt-bearer',
                                                     'assertion':assertion.decode('ascii')}))
                token = token_data.get('access_token')
                if not isinstance(token, str) or not token or len(token) > MAX_METADATA_BYTES:
                    raise FinanceRunError('BUDGET_PULL_UNAVAILABLE', status=503)
                headers = {'Authorization': f'Bearer {token}'}
                base = f'https://www.googleapis.com/drive/v3/files/{sheet_id}'
                metadata_url = base + '?fields=modifiedTime,version,mimeType'
                before, stamp = await _metadata(session, metadata_url, headers)
                data = await _read(session, base + '/export?mimeType=' + MIME,
                                   limit=MAX_EXPORT_BYTES, headers=headers)
                after, _ = await _metadata(session, metadata_url, headers)
                if before != after:
                    raise FinanceRunError('BUDGET_PULL_SOURCE_CHANGED', status=409)
                return data, stamp, before[0]
        finally:
            await resolver.close()


@contextmanager
def budget_export(year):
    try:
        source = urlsplit(os.environ.get(f'MASI_BUDGET_{year}_URL', ''))
        match = re.fullmatch(r'/spreadsheets/d/([A-Za-z0-9_-]+)(?:/.*)?', source.path)
        info = json.loads(os.environ.get('GOOGLE_CREDENTIALS', ''))
        expected_email = os.environ.get('GOOGLE_SERVICE_ACCOUNT_EMAIL')
        if (source.scheme != 'https' or source.netloc != 'docs.google.com' or not match
                or not expected_email or info.get('client_email') != expected_email
                or info.get('token_uri', TOKEN_URL) != TOKEN_URL):
            raise ValueError()
        info['token_uri'] = TOKEN_URL
        credentials = Credentials.from_service_account_info(info, scopes=[SCOPE])
        issued = int(time())
        # Public signing API; fixed audience/scope and no delegated subject.
        assertion = jwt.encode(credentials.signer, {'iss':expected_email, 'scope':SCOPE,
                               'aud':TOKEN_URL, 'iat':issued, 'exp':issued + 3600})
    except Exception:
        raise FinanceRunError('BUDGET_PULL_NOT_CONFIGURED', status=503) from None
    try:
        data, stamp, modified = asyncio.run(_acquire(match[1], assertion))
    except FinanceRunError:
        raise
    except TimeoutError:
        raise FinanceRunError('BUDGET_PULL_TIMEOUT', status=504) from None
    except Exception:
        raise FinanceRunError('BUDGET_PULL_UNAVAILABLE', status=503) from None
    # Acquisition exception translation ends here. Downstream service failures
    # retain their own classification, and the workbook closes on every exit.
    with BytesIO(data) as stream:
        del data
        yield {'stream': stream, 'source_name': f'{stamp:%Y%m%d} - Masi {year} Budget.xlsx',
               'content_type': MIME, 'acquisition': {
                   'method':'google_sheets_export', 'source_modified_at':modified,
                   'fetched_at':datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')}}
