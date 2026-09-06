"""Bounded raw XLSX envelope and XML preflight; never materialises a workbook.

Envelope/ZIP validation precedes tuple locking. Sheet scanning belongs inside the
lock, after idempotency. The context owns and closes its in-memory buffer.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
import hashlib
from io import BytesIO
import re
import struct
import zipfile
import zlib
from xml.etree.ElementTree import ParseError
from defusedxml.ElementTree import iterparse
from defusedxml.common import DefusedXmlException

MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
CHUNK = 64 * 1024
MAX_COMPRESSED = 32 * 1024 * 1024
MAX_ENTRY_EXPANDED = 256 * 1024 * 1024
MAX_TOTAL_EXPANDED = 512 * 1024 * 1024
MAX_ENTRIES = 256
MAX_RATIO = 100
LEDGER_HEADERS = ('Date', 'Year', 'Name', 'Amount', 'Paid By', 'Category 1', 'Category 2', 'Category 3', 'BC')
CONTRACT_HEADERS = ('Budget Key', 'Funder', 'Start Date', 'End Date', 'Description')
NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
RID = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'


class WorkbookError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def require(condition, code):
    if not condition:
        raise WorkbookError(code)


@dataclass
class Upload:
    buffer: BytesIO
    source_name: str
    source_date: date
    size_bytes: int
    sha256: str


def _safe_path(name):
    return (bool(name) and not name.startswith('/') and '\\' not in name
            and ':' not in name and all(p not in ('.', '..', '') for p in name.rstrip('/').split('/')))


@contextmanager
def preflight(stream, *, source_name, content_type, content_length=None):
    require(content_type == MIME, 'CONTENT_TYPE_INVALID')
    require(isinstance(source_name, str) and len(source_name) <= 255
            and re.fullmatch(r'[0-9]{8} - [^/\\\x00-\x1f\x7f]+\.xlsx', source_name) is not None,
            'SOURCE_INVALID')
    try:
        source_date = date(int(source_name[:4]), int(source_name[4:6]), int(source_name[6:8]))
    except ValueError:
        raise WorkbookError('SOURCE_INVALID') from None
    if content_length is not None:
        require(isinstance(content_length, (int, str)) and re.fullmatch(r'[0-9]+', str(content_length)) is not None,
                'CONTENT_LENGTH_INVALID')
        require(0 < int(content_length) <= MAX_COMPRESSED, 'CONTENT_LENGTH_INVALID')
    with BytesIO() as buffer:
        digest = hashlib.sha256()
        size = 0
        while True:
            count = min(CHUNK, MAX_COMPRESSED + 1 - size)
            # Sized in-memory WSGI inputs expose remaining bytes (Django's test
            # transport rejects over-reads). This never uses Content-Length.
            if hasattr(stream, '__len__'):
                count = min(count, len(stream))
            chunk = stream.read(count)
            if not chunk:
                break
            size += len(chunk)
            require(size <= MAX_COMPRESSED, 'UPLOAD_TOO_LARGE')
            buffer.write(chunk)
            digest.update(chunk)
        require(size > 0, 'EMPTY_WORKBOOK')
        buffer.seek(0)
        _check_zip(buffer)
        buffer.seek(0)
        yield Upload(buffer, source_name, source_date, size, digest.hexdigest())


def _check_zip(buffer):
    """Inflate independently: ZipExtFile trusts file_size to truncate output.

    Central-directory sizes delimit input but never authorize expansion. Verify
    actual compressed/expanded lengths and CRC, with bounded zlib output chunks.
    """
    try:
        with zipfile.ZipFile(buffer) as archive:
            entries = archive.infolist()
            require(len(entries) <= MAX_ENTRIES, 'ZIP_ENTRY_LIMIT')
            names = set()
            for entry in entries:
                require(not entry.flag_bits & 1, 'ZIP_ENCRYPTED')
                require(entry.filename not in names, 'ZIP_DUPLICATE_ENTRY')
                names.add(entry.filename)
                require(_safe_path(entry.filename), 'ZIP_PATH_INVALID')
            total = 0
            for entry in entries:
                require(entry.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED), 'ZIP_COMPRESSION_INVALID')
                buffer.seek(entry.header_offset)
                header = buffer.read(30)
                require(len(header) == 30 and header[:4] == b'PK\x03\x04', 'ZIP_INVALID')
                fields = struct.unpack('<4s5H3I2H', header)
                require(not fields[2] & 1, 'ZIP_ENCRYPTED')
                require(fields[3] == entry.compress_type, 'ZIP_INVALID')
                buffer.seek(fields[-2] + fields[-1], 1)
                require(buffer.tell() + entry.compress_size <= archive.start_dir, 'ZIP_INVALID')
                remaining = entry.compress_size
                expanded = crc = compressed = 0
                inflater = zlib.decompressobj(-15) if entry.compress_type == zipfile.ZIP_DEFLATED else None
                while remaining:
                    raw = buffer.read(min(CHUNK, remaining))
                    require(bool(raw), 'ZIP_INVALID')
                    remaining -= len(raw)
                    compressed += len(raw)
                    pending = raw
                    while pending:
                        output = inflater.decompress(pending, CHUNK) if inflater else pending
                        pending = inflater.unconsumed_tail if inflater else b''
                        expanded += len(output)
                        total += len(output)
                        crc = zlib.crc32(output, crc)
                        require(expanded <= MAX_ENTRY_EXPANDED, 'ZIP_ENTRY_EXPANDED_LIMIT')
                        require(total <= MAX_TOTAL_EXPANDED, 'ZIP_TOTAL_EXPANDED_LIMIT')
                        require(expanded <= MAX_RATIO * max(entry.compress_size, 1), 'ZIP_RATIO_LIMIT')
                    if inflater and inflater.eof:
                        require(not remaining and not inflater.unused_data, 'ZIP_INVALID')
                require(inflater is None or inflater.eof, 'ZIP_INVALID')
                require(expanded == entry.file_size and crc == entry.CRC, 'ZIP_INVALID')
                require(expanded <= MAX_RATIO * max(compressed, 1), 'ZIP_RATIO_LIMIT')
    except (zipfile.BadZipFile, zlib.error, EOFError, OSError, struct.error, NotImplementedError):
        raise WorkbookError('ZIP_INVALID') from None


def _events(archive, path):
    require(path in archive.namelist(), 'WORKBOOK_METADATA_INVALID')
    with archive.open(path) as stream:
        stack = []
        retained = {NS + name for name in ('t', 'v', 'f', 'is', 'r', 'rPr')}
        for event, element in iterparse(stream, events=('start', 'end'), forbid_dtd=True,
                                        forbid_entities=True, forbid_external=True):
            if event == 'start':
                stack.append(element)
            yield event, element
            if event == 'end':
                stack.pop()
                if stack and element.tag not in retained and element in stack[-1]:
                    stack[-1].remove(element)


def _coordinate(value):
    match = re.fullmatch(r'([A-Z]{1,3})([1-9][0-9]{0,6})', value or '')
    require(match is not None, 'SHEET_BOUNDS')
    column = 0
    for letter in match[1]:
        column = column * 26 + ord(letter) - 64
    return int(match[2]), column


def _label(value):
    """Retain header vocabulary or nonblank marker, never shared-string contents."""
    value = value.strip()
    return value if value in (*LEDGER_HEADERS, *CONTRACT_HEADERS) else bool(value)


def _shared_strings(archive):
    values = []
    if 'xl/sharedStrings.xml' not in archive.namelist():
        return values
    root = None
    for event, element in _events(archive, 'xl/sharedStrings.xml'):
        if root is None:
            root = element
        if event == 'end' and element.tag == NS + 'si':
            values.append(_label(''.join(t.text or '' for t in element.iter(NS + 't'))))
            element.clear()
            root.clear()
    return values


def _scan_sheet(archive, path, name, strings):
    limit = 50000 if name == 'Expenditure' else 5000
    extent = header_width = header_rows = max_data_col = 0
    headers = {}
    row_values = {}
    root = sheet_data = None
    for event, element in _events(archive, path):
        if root is None:
            root = element
        tag = element.tag
        if event == 'start' and tag == NS + 'sheetData':
            sheet_data = element
        if event == 'start' and tag == NS + 'dimension':
            coordinates = element.get('ref', '').split(':')
            require(1 <= len(coordinates) <= 2, 'SHEET_BOUNDS')
            for coordinate in coordinates:
                row, col = _coordinate(coordinate)
                require(row <= limit and col <= 256, 'SHEET_BOUNDS')
                extent = max(extent, row)
        if event == 'start' and tag == NS + 'row':
            number = element.get('r', '')
            require(re.fullmatch(r'[1-9][0-9]{0,6}', number) is not None and int(number) <= limit, 'SHEET_BOUNDS')
            extent = max(extent, int(number))
            row_values = {}
        if event == 'end' and tag == NS + 'c':
            row, col = _coordinate(element.get('r'))
            require(row <= limit and col <= 256, 'SHEET_BOUNDS')
            extent = max(extent, row)
            value = element.find(NS + 'v')
            formula = element.find(NS + 'f')
            if element.get('t') == 's':
                try:
                    index = int(value.text)
                    require(0 <= index < len(strings), 'XML_INVALID')
                    label = strings[index]
                except (ValueError, TypeError, AttributeError):
                    raise WorkbookError('XML_INVALID') from None
            elif element.get('t') == 'inlineStr':
                label = _label(''.join(t.text or '' for t in element.iter(NS + 't')))
            else:
                label = _label(value.text or '') if value is not None else False
            nonblank = bool(label) or formula is not None
            if name == 'Expenditure':
                if row == 1 and nonblank:
                    require(col <= 128, 'LEDGER_HEADER_LIMIT')
                    require(col not in headers, 'LEDGER_DUPLICATE_HEADER')
                    headers[col] = label
                    header_width = max(header_width, col)
                elif nonblank:
                    max_data_col = max(max_data_col, col)
                require(extent * header_width <= 4000000, 'LEDGER_CELL_LIMIT')
            elif label:
                require(col not in row_values, 'CONTRACT_KEY_HEADER')
                row_values[col] = label
            element.clear()
        if event == 'end' and tag == NS + 'row':
            if name == 'Funder Budgets' and all(h in row_values.values() for h in CONTRACT_HEADERS):
                require(all(list(row_values.values()).count(h) == 1 for h in CONTRACT_HEADERS), 'CONTRACT_KEY_HEADER')
                header_rows += 1
            element.clear()
            if sheet_data is not None:
                sheet_data.clear()
        if event == 'end' and tag == NS + 'sheetData':
            root.clear()
    if name == 'Expenditure':
        require(all(list(headers.values()).count(h) == 1 for h in LEDGER_HEADERS), 'LEDGER_REQUIRED_HEADER')
        require(extent * header_width <= 4000000, 'LEDGER_CELL_LIMIT')
        require(max_data_col <= header_width, 'LEDGER_DATA_BEYOND_HEADER')
    else:
        require(header_rows == 1, 'CONTRACT_KEY_HEADER')


def scan_workbook(upload):
    try:
        with zipfile.ZipFile(upload.buffer) as archive:
            sheets, relationships = [], {}
            for event, element in _events(archive, 'xl/workbook.xml'):
                if event == 'end':
                    if element.tag == NS + 'sheet':
                        sheets.append((element.get('name'), element.get(RID)))
                    element.clear()
            require(all(sum(name == required for name, _ in sheets) == 1
                        for required in ('Funder Budgets', 'Expenditure')), 'REQUIRED_SHEETS')
            for event, element in _events(archive, 'xl/_rels/workbook.xml.rels'):
                if event == 'end':
                    if element.tag.endswith('}Relationship'):
                        key, target = element.get('Id'), element.get('Target', '')
                        require(key not in relationships, 'WORKBOOK_METADATA_INVALID')
                        if element.get('TargetMode') == 'External':
                            relationships[key] = None
                        else:
                            path = target.lstrip('/') if target.startswith('/xl/') else 'xl/' + target
                            require(_safe_path(path), 'WORKBOOK_METADATA_INVALID')
                            relationships[key] = path
                    element.clear()
            strings = _shared_strings(archive)
            for name, key in sheets:
                if name in ('Funder Budgets', 'Expenditure'):
                    require(bool(relationships.get(key)), 'WORKBOOK_METADATA_INVALID')
                    _scan_sheet(archive, relationships[key], name, strings)
    except (ParseError, DefusedXmlException, zipfile.BadZipFile, KeyError, OSError, ValueError) as error:
        if isinstance(error, WorkbookError):
            raise
        raise WorkbookError('XML_INVALID') from None
    finally:
        upload.buffer.seek(0)
