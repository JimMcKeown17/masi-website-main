"""HTTP behavior for the operator-triggered, configured budget export."""
from django.test import TestCase
from rest_framework.test import APIClient
from api.finance_run_test_utils import actor, candidate
from api.finance_budget_test_utils import budget_ledger, budget_workbook
from api.models import FinanceRun
from contextlib import contextmanager
from io import BytesIO
import json
from unittest.mock import patch, Mock
import asyncio


class BudgetPullTests(TestCase):
    def pull(self, user, ledger, **extra):
        client = APIClient()
        client.force_authenticate(user)
        return client.post('/api/finance/runs/pull-budget/',
                           dict(year=2026, ledger_run_id=str(ledger.pk), **extra), format='json')

    @contextmanager
    def google_export(self, *, after=None, status=200, data=None, token_bytes=None):
        metadata = {'modifiedTime': '2026-09-07T23:30:00Z', 'version': '42',
                    'mimeType': 'application/vnd.google-apps.spreadsheet'}
        def reply(body, code=200):
            class Response:
                status = code
                headers = {}
                raw = BytesIO(body)
                async def __aenter__(self): return self
                async def __aexit__(self, *args): self.raw.close()
                @property
                def content(self): return self
                async def read(self, count): return self.raw.read(count)
            return Response()
        responses = [reply(b'{"access_token":"synthetic-token"}' if token_bytes is None else token_bytes),
                     reply(json.dumps(metadata).encode(), status),
                     reply(budget_workbook() if data is None else data),
                     reply(json.dumps(metadata if after is None else after).encode())]
        credentials = Mock(token='synthetic-token')
        with patch.dict('os.environ', {
            'GOOGLE_CREDENTIALS': json.dumps({'client_email': 'synthetic@example.invalid'}),
            'GOOGLE_SERVICE_ACCOUNT_EMAIL': 'synthetic@example.invalid',
            'MASI_BUDGET_2026_URL': 'https://docs.google.com/spreadsheets/d/synthetic-sheet/edit'}), \
             patch('google.oauth2.service_account.Credentials.from_service_account_info', return_value=credentials), \
             patch('google.auth.jwt.encode', return_value=b'synthetic-assertion'), \
             patch('aiohttp.ClientSession.request', side_effect=responses) as network:
            yield network

    def test_pull_creates_reviewable_candidate_with_source_modified_date(self):
        user = actor()
        ledger = budget_ledger(user)
        with self.google_export() as network:
            response = self.pull(user, ledger)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['status'], 'candidate')
        self.assertEqual(response.data['source_name'], '20260907 - Masi 2026 Budget.xlsx')
        self.assertEqual(response.data['manifest']['acquisition']['method'], 'google_sheets_export')
        self.assertEqual(response.data['manifest']['acquisition']['source_modified_at'], '2026-09-07T23:30:00Z')
        self.assertEqual(response.json()['dependency_run'], str(ledger.pk))
        self.assertEqual(network.call_count, 4)
        self.assertFalse(FinanceRun.objects.filter(kind='budgets', status='approved').exists())

    def test_pull_requires_publisher_before_acquisition(self):
        user = actor('project-manager', role='PROJECT MANAGER')
        client = APIClient()
        client.force_authenticate(user)
        response = client.post('/api/finance/runs/pull-budget/',
                               {'year': 2026, 'ledger_run_id': '00000000-0000-4000-8000-000000000001'},
                               format='json')
        self.assertEqual(response.status_code, 403)

    def test_pull_rejects_duplicate_json_fields_before_acquisition(self):
        user = actor()
        ledger = budget_ledger(user)
        client = APIClient()
        client.force_authenticate(user)
        response = client.post('/api/finance/runs/pull-budget/',
            '{"year":2025,"year":2026,"ledger_run_id":"' + str(ledger.pk) + '"}',
            content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'code': 'UPLOAD_METADATA_INVALID'})

    def test_token_response_is_bounded_before_export_or_producer(self):
        from api.services import finance_runs as service
        user = actor()
        ledger = budget_ledger(user)
        with self.google_export(token_bytes=b'x' * 16385) as network, \
             patch.object(service, 'build_budget_run_artifact', wraps=service.build_budget_run_artifact) as producer:
            response = self.pull(user, ledger)
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(response.json(), {'code': 'BUDGET_PULL_SIZE_LIMIT'})
        self.assertEqual(network.call_count, 1)
        producer.assert_not_called()
        self.assertFalse(FinanceRun.objects.filter(kind='budgets').exists())

    def test_source_changed_or_missing_metadata_never_enters_producer(self):
        from api.services import finance_runs as service
        user = actor()
        ledger = budget_ledger(user)
        for after, expected in [
            ({'modifiedTime': '2026-09-07T23:30:00Z', 'version': '43',
              'mimeType': 'application/vnd.google-apps.spreadsheet'}, 'BUDGET_PULL_SOURCE_CHANGED'),
            ({'version': '42'}, 'BUDGET_PULL_METADATA_INVALID'),
        ]:
            with self.subTest(expected=expected), self.google_export(after=after), \
                 patch.object(service, 'build_budget_run_artifact', wraps=service.build_budget_run_artifact) as producer:
                response = self.pull(user, ledger)
            self.assertEqual(response.json(), {'code': expected})
            producer.assert_not_called()
        self.assertFalse(FinanceRun.objects.filter(kind='budgets').exists())

    def test_transport_failures_are_value_free_and_create_no_history(self):
        from api.services import finance_runs as service
        user = actor()
        ledger = budget_ledger(user)
        for status, expected in [(403, 'BUDGET_PULL_ACCESS_DENIED'), (429, 'BUDGET_PULL_QUOTA'),
                                 (302, 'BUDGET_PULL_UNAVAILABLE'), (500, 'BUDGET_PULL_UNAVAILABLE')]:
            with self.subTest(status=status), self.google_export(status=status) as network, \
                 patch.object(service, 'build_budget_run_artifact', wraps=service.build_budget_run_artifact) as producer:
                response = self.pull(user, ledger)
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json(), {'code': expected})
            self.assertEqual(network.call_count, 2)
            self.assertFalse(network.call_args.kwargs['allow_redirects'])
            producer.assert_not_called()
        with self.google_export() as network:
            network.side_effect = TimeoutError('PRIVATE_REMOTE_BODY_AND_TOKEN')
            response = self.pull(user, ledger)
        self.assertEqual(response.status_code, 504)
        self.assertEqual(response.json(), {'code': 'BUDGET_PULL_TIMEOUT'})
        self.assertFalse(FinanceRun.objects.filter(kind='budgets').exists())

    def test_export_size_limit_closes_remote_stream_before_producer(self):
        from api.services import finance_runs as service
        user = actor()
        ledger = budget_ledger(user)
        with self.google_export(data=b'x' * 1025) as network, \
             patch('api.services.finance_budget_pull.MAX_EXPORT_BYTES', 1024), \
             patch.object(service, 'build_budget_run_artifact', wraps=service.build_budget_run_artifact) as producer:
            # Retain the mocked transport's raw streams to verify cleanup on rejection.
            responses = list(network.side_effect)
            network.side_effect = responses
            response = self.pull(user, ledger)
        self.assertEqual(response.json(), {'code': 'BUDGET_PULL_SIZE_LIMIT'})
        self.assertTrue(responses[0].raw.closed)
        self.assertTrue(responses[1].raw.closed)
        self.assertTrue(responses[2].raw.closed)
        producer.assert_not_called()
        self.assertFalse(FinanceRun.objects.filter(kind='budgets').exists())

    def test_file_and_pull_replay_same_immutable_run_in_both_orders(self):
        from urllib.parse import urlencode
        from api.parsers.finance_workbook import MIME
        user = actor()
        ledger = budget_ledger(user)
        client = APIClient()
        client.force_authenticate(user)
        for first in ('file', 'sheets'):
            with self.subTest(first=first):
                # Distinct valid bytes keep both immutable histories in one test.
                data = budget_workbook(half=first == 'sheets')
                query = urlencode(dict(kind='budgets', year=2026,
                    source_name='20260907 - Manual export.xlsx', ledger_run_id=str(ledger.pk)))
                def upload():
                    return client.post('/api/finance/runs/?' + query, data, content_type=MIME)
                with self.google_export(data=data):
                    original = upload() if first == 'file' else self.pull(user, ledger)
                with self.google_export(data=data):
                    replay = self.pull(user, ledger) if first == 'file' else upload()
                self.assertEqual(original.status_code, 201, original.data.get('code'))
                self.assertEqual(replay.status_code, 200, replay.data.get('code'))
                self.assertEqual(replay.json(), original.json())
        self.assertEqual(FinanceRun.objects.filter(kind='budgets').count(), 2)

    def test_admission_denies_unknown_fields_invalid_dependency_and_non_publishers_before_google(self):
        user = actor()
        ledger = budget_ledger(user)
        with self.google_export() as network:
            self.assertEqual(self.pull(user, ledger, url='https://attacker.invalid').status_code, 400)
            ledger = candidate(user, sha='1' * 64)
            self.assertEqual(self.pull(user, ledger).status_code, 400)
            for role in ('PROJECT MANAGER', 'STAFF'):
                self.assertEqual(self.pull(actor(role, role=role), ledger).status_code, 403)
        network.assert_not_called()

    def test_acquisition_latency_is_included_in_candidate_measurement(self):
        from time import sleep
        user = actor()
        ledger = budget_ledger(user)
        with self.google_export() as network:
            replies = iter(network.side_effect)
            def delayed(*args, **kwargs):
                sleep(0.02)
                return next(replies)
            network.side_effect = delayed
            response = self.pull(user, ledger)
        self.assertEqual(response.status_code, 201, response.data.get('code'))
        self.assertGreaterEqual(response.data['total_duration_ms'], 60)
        self.assertGreater(response.data['peak_memory_bytes'], 0)

    def test_token_and_export_requests_negotiate_identity_encoding_for_bounded_raw_reads(self):
        user = actor()
        ledger = budget_ledger(user)
        with self.google_export() as network:
            response = self.pull(user, ledger)
        self.assertEqual(response.status_code, 201)
        self.assertTrue(all(call.kwargs['headers'].get('Accept-Encoding') == 'identity'
                            for call in network.call_args_list))

    def test_downstream_failures_keep_their_classification_and_close_workbook(self):
        from api.services.finance_budget_pull import budget_export
        with self.google_export(), self.assertRaisesRegex(RuntimeError, '^synthetic downstream failure$'):
            with budget_export(2026) as export:
                stream = export['stream']
                raise RuntimeError('synthetic downstream failure')
        self.assertTrue(stream.closed)

    def test_total_deadline_cancels_dns_without_executor_or_pending_tasks(self):
        from api.services.finance_budget_pull import _acquire
        cancelled = []
        async def stalled_dns(*args, **kwargs):
            try:
                await asyncio.sleep(10)
            finally:
                cancelled.append(True)
        async def probe():
            with patch('aiohttp.AsyncResolver.resolve', side_effect=stalled_dns), \
                 patch('api.services.finance_budget_pull.ACQUISITION_SECONDS', 0.03):
                with self.assertRaises(TimeoutError):
                    await _acquire('synthetic', b'synthetic')
            self.assertTrue(cancelled)
            self.assertFalse([task for task in asyncio.all_tasks() if task is not asyncio.current_task() and not task.done()])
        asyncio.run(probe())

    def test_total_deadline_stops_dripping_headers_and_body_using_real_http_parser(self):
        import aiohttp
        from time import monotonic
        from api.services.finance_budget_pull import _acquire
        async def probe(phase):
            handlers = set()
            async def drip(reader, writer):
                task = asyncio.current_task()
                handlers.add(task)
                try:
                    await reader.readuntil(b'\r\n\r\n')
                    prefix = (b'HTTP/1.1 200 OK\r\nX-Drip: ' if phase == 'headers' else
                              b'HTTP/1.1 200 OK\r\nContent-Length: 10000\r\n\r\n')
                    writer.write(prefix)
                    await writer.drain()
                    for _ in range(1000):
                        writer.write(b'x')
                        await writer.drain()
                        await asyncio.sleep(0.005)
                except (ConnectionError, asyncio.CancelledError):
                    pass
                finally:
                    writer.close()
                    try:
                        await writer.wait_closed()
                    except ConnectionError:
                        pass
                    handlers.discard(task)
            server = await asyncio.start_server(drip, '127.0.0.1', 0)
            port = server.sockets[0].getsockname()[1]
            request = aiohttp.ClientSession.request
            def loopback(session, method, url, **kwargs):
                return request(session, method, f'http://127.0.0.1:{port}/synthetic', **kwargs)
            try:
                with patch('aiohttp.ClientSession.request', loopback), \
                     patch('api.services.finance_budget_pull.ACQUISITION_SECONDS', 0.05):
                    started = monotonic()
                    with self.assertRaises(TimeoutError):
                        await _acquire('synthetic', b'synthetic')
                    self.assertLess(monotonic() - started, 0.5)
            finally:
                server.close()
                await server.wait_closed()
                tasks = list(handlers)
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
            self.assertFalse([task for task in asyncio.all_tasks() if task is not asyncio.current_task() and not task.done()])
        for phase in ('headers', 'body'):
            with self.subTest(phase=phase):
                asyncio.run(probe(phase))
