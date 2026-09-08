"""Bounded raw XLSX envelope and XML preflight; never materialises a workbook.

Envelope/ZIP validation precedes tuple locking. Sheet scanning belongs inside the
lock, after idempotency. The context owns and closes its in-memory buffer.
"""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
import hashlib
import posixpath
from io import BytesIO
import re
import struct
import zipfile
import zlib
from xml.etree.ElementTree import ParseError
from defusedxml.ElementTree import iterparse, fromstring
from openpyxl.xml.constants import XLSX, XLSM, XLTX, XLTM, SHARED_STRINGS
from defusedxml.common import DefusedXmlException

MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
CHUNK = 64 * 1024
MAX_COMPRESSED = 32 * 1024 * 1024
MAX_ENTRY_EXPANDED = 256 * 1024 * 1024
MAX_TOTAL_EXPANDED = 512 * 1024 * 1024
MAX_METADATA_EXPANDED = 1024 * 1024
MAX_SHARED_STRINGS_EXPANDED = 64 * 1024 * 1024
MAX_SHARED_STRINGS = 4000000
MAX_SHARED_STRING_CHILDREN = 1024
MAX_SHARED_STRING_NODES = 2 * MAX_SHARED_STRINGS
MAX_SHEET_NODES = 8000000
MAX_SHEET_RETAINED_NODES = 65536
MAX_STRING_LENGTH = 32767
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


def _part_limit(path):
    if path in ('[Content_Types].xml', 'xl/workbook.xml') or path.endswith('.rels'):
        return MAX_METADATA_EXPANDED
    if path == 'xl/sharedStrings.xml':
        return MAX_SHARED_STRINGS_EXPANDED
    return MAX_ENTRY_EXPANDED


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
            normalized_names = set()
            for entry in entries:
                require(not entry.flag_bits & 1, 'ZIP_ENCRYPTED')
                require(entry.filename not in names, 'ZIP_DUPLICATE_ENTRY')
                names.add(entry.filename)
                require(_safe_path(entry.filename), 'ZIP_PATH_INVALID')
                normalized = posixpath.normpath(entry.filename)
                require(normalized not in normalized_names, 'WORKBOOK_METADATA_INVALID')
                normalized_names.add(normalized)
                require(entry.file_size <= _part_limit(entry.filename), 'PART_SIZE_LIMIT'
                        if _part_limit(entry.filename) < MAX_ENTRY_EXPANDED else 'ZIP_ENTRY_EXPANDED_LIMIT')
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
                    while True:
                        output = inflater.decompress(pending, CHUNK) if inflater else pending
                        pending = inflater.unconsumed_tail if inflater else b''
                        expanded += len(output)
                        total += len(output)
                        crc = zlib.crc32(output, crc)
                        require(expanded <= _part_limit(entry.filename), 'PART_SIZE_LIMIT'
                                if _part_limit(entry.filename) < MAX_ENTRY_EXPANDED else 'ZIP_ENTRY_EXPANDED_LIMIT')
                        require(expanded <= MAX_ENTRY_EXPANDED, 'ZIP_ENTRY_EXPANDED_LIMIT')
                        require(total <= MAX_TOTAL_EXPANDED, 'ZIP_TOTAL_EXPANDED_LIMIT')
                        require(expanded <= MAX_RATIO * max(entry.compress_size, 1), 'ZIP_RATIO_LIMIT')
                        # zlib can retain output after consuming all input. Drain
                        # a full output chunk before asking for more compressed bytes.
                        if (inflater and inflater.eof) or (
                                not pending and (inflater is None or len(output) < CHUNK)):
                            break
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
        yield from _xml_events(stream)


def _xml_events(stream):
    stack = []
    for event, element in iterparse(stream, events=('start', 'end'), forbid_dtd=True,
                                    forbid_entities=True, forbid_external=True):
        if event == 'start':
            stack.append(element)
        yield event, element
        if event == 'end':
            stack.pop()
            element.clear()
            if stack:
                stack[-1].remove(element)


def _coordinate(value, code='SHEET_BOUNDS'):
    match = re.fullmatch(r'([A-Z]{1,3})([1-9][0-9]{0,6})', value or '')
    require(match is not None, code)
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
    _check_declarations(archive, 'xl/sharedStrings.xml', 'XML_INVALID')
    nodes = children = length = depth = 0
    texts = None
    for event, element in _events(archive, 'xl/sharedStrings.xml'):
        if event == 'start':
            depth += 1
            # openpyxl clears si only: no extensions or wrappers may survive
            # outside entries until the complete string table has been read.
            if depth == 1:
                require(element.tag == NS + 'sst', 'SHARED_STRING_LIMIT')
            elif texts is None:
                require(depth == 2 and element.tag == NS + 'si', 'SHARED_STRING_LIMIT')
            nodes += 1
            require(nodes <= MAX_SHARED_STRING_NODES, 'SHARED_STRING_LIMIT')
            if texts is not None:
                children += 1
                require(children <= MAX_SHARED_STRING_CHILDREN, 'SHARED_STRING_LIMIT')
            if element.tag == NS + 'si':
                require(texts is None, 'XML_INVALID')
                require(len(values) < MAX_SHARED_STRINGS, 'SHARED_STRING_LIMIT')
                texts = []
                children = length = 0
        else:
            depth -= 1
            if texts is not None and element.tag == NS + 't':
                text = element.text or ''
                length += len(text)
                require(length <= MAX_STRING_LENGTH, 'SHARED_STRING_LIMIT')
                texts.append(text)
            elif texts is not None and element.tag == NS + 'si':
                values.append(_label(''.join(texts)))
                texts = None
    return values


def _check_declarations(archive, path, code):
    require(path in archive.namelist(), 'WORKBOOK_METADATA_INVALID')
    # Bounded declaration pass before ANY parser, including NUL-separated
    # UTF-16/32 tokens. Keep the longest token's prefix across chunk boundaries.
    tokens = (b'<!DOCTYPE', b'<!ENTITY')
    overlap = max(map(len, tokens)) - 1
    tail = b''
    expanded = 0
    with archive.open(path) as stream:
        while chunk := stream.read(CHUNK):
            expanded += len(chunk)
            require(expanded <= _part_limit(path), 'PART_SIZE_LIMIT')
            declaration_bytes = tail + chunk.replace(b'\x00', b'')
            require(not any(token in declaration_bytes for token in tokens),
                    code)
            tail = declaration_bytes[-overlap:]


def _scan_sheet(archive, path, name, strings, budget=None):
    _check_declarations(archive, path, 'SHEET_XML_DECLARATION')
    # Reopen directly into the single defusedxml scanner; never buffer a part.
    return _scan_sheet_xml(archive, path, name, strings, budget)


def _scan_sheet_xml(archive, path, name, strings, budget=None):
    limit = 50000 if name == 'Expenditure' and budget is None else 5000
    seen_rows, seen_cols = set(), set()
    current_row = max_row = max_col = 0
    previous_row = previous_col = 0
    nonempty = False
    budget_header_width = 0
    extent = header_width = header_rows = max_data_col = 0
    headers = {}
    row_values = {}
    value = None
    formula = False
    inline = []
    nodes = metadata_nodes = row_nodes = depth = row_depth = 0
    parents = []
    sheet_data_seen = False
    for event, element in _events(archive, path):
        tag = element.tag
        if event == 'start':
            parent = parents[-1] if parents else None
            # The consumer emits rows on end events regardless of parent and
            # parses EVERY direct row child as a cell. Establish its structure
            # before coordinate/order checks, without accepting inferred cells.
            local_name = tag.rsplit('}', 1)[-1]
            if local_name == 'sheetData':
                require(tag == NS + 'sheetData' and parents == [NS + 'worksheet']
                        and not sheet_data_seen, 'XML_INVALID')
                sheet_data_seen = True
            if local_name == 'row':
                require(tag == NS + 'row' and parent == NS + 'sheetData', 'XML_INVALID')
            if parent == NS + 'row' or local_name == 'c':
                require(tag == NS + 'c' and parent == NS + 'row', 'XML_INVALID')
                _coordinate(element.get('r'), 'XML_INVALID')
            parents.append(tag)
            depth += 1
            if depth == 1:
                require(tag == NS + 'worksheet', 'XML_INVALID')
            nodes += 1
            require(nodes <= MAX_SHEET_NODES, 'XML_INVALID')
            # WorkSheetParser clears rows and dispatched metadata at end, but
            # retains unknown nodes and converted metadata for the whole part.
            # Count cleared row shells too: openpyxl does not detach them.
            # Bound cumulative non-row structure and each retained row tree.
            if not row_depth:
                metadata_nodes += 1
                require(metadata_nodes <= MAX_SHEET_RETAINED_NODES, 'XML_INVALID')
            if tag == NS + 'row' and not row_depth:
                row_depth = depth
                row_nodes = 0
            if row_depth:
                row_nodes += 1
                require(row_nodes <= MAX_SHEET_RETAINED_NODES, 'XML_INVALID')
        if event == 'start' and tag == NS + 'c':
            r, c = _coordinate(element.get('r'))
            # Read-only iteration advances through coordinates: disorder can
            # silently omit populated inputs. Reject as unsafe before parsing.
            require(row_depth and r == current_row and c > previous_col, 'XML_INVALID')
            previous_col = c
            if budget is not None:
                r, c = _coordinate(element.get('r'))
                require(r == current_row and r <= limit and c <= 256 and c not in seen_cols, 'BUDGET_SHEET_LIMIT')
                seen_cols.add(c)
                max_row, max_col = max(max_row, r), max(max_col, c)
                require(budget['cells'] + max_row * max_col <= 4000000, 'BUDGET_SHEET_LIMIT')
            value = None
            formula = False
            inline = []
        if event == 'end':
            if tag == NS + 'v':
                value = element.text or ''
            elif tag == NS + 'f':
                formula = True
                if budget is not None:
                    _budget_formula_references(element.text or '', budget['names'])
            elif tag == NS + 't':
                inline.append(element.text or '')
        if event == 'start' and tag == NS + 'dimension':
            coordinates = element.get('ref', '').split(':')
            require(1 <= len(coordinates) <= 2, 'SHEET_BOUNDS')
            for coordinate in coordinates:
                row, col = _coordinate(coordinate)
                require(row <= limit and col <= 256, 'SHEET_BOUNDS')
                extent = max(extent, row)
        if event == 'start' and tag == NS + 'row':
            number = element.get('r', '')
            require(re.fullmatch(r'[1-9][0-9]{0,6}', number) is not None, 'XML_INVALID')
            require(int(number) <= limit, 'SHEET_BOUNDS')
            current_row = int(number)
            require(current_row > previous_row, 'XML_INVALID')
            previous_row, previous_col = current_row, 0
            extent = max(extent, int(number))
            if budget is not None:
                current_row = int(number)
                require(current_row not in seen_rows, 'BUDGET_SHEET_LIMIT')
                seen_rows.add(current_row)
                seen_cols = set()
                max_row = max(max_row, current_row)
                require(budget['cells'] + max_row * max_col <= 4000000, 'BUDGET_SHEET_LIMIT')
            row_values = {}
        if event == 'end' and tag == NS + 'c':
            row, col = _coordinate(element.get('r'))
            require(row <= limit and col <= 256, 'SHEET_BOUNDS')
            extent = max(extent, row)
            if element.get('t') == 's':
                try:
                    index = int(value)
                    require(0 <= index < len(strings), 'XML_INVALID')
                    label = strings[index]
                except (ValueError, TypeError, AttributeError):
                    raise WorkbookError('XML_INVALID') from None
            elif element.get('t') == 'inlineStr':
                label = _label(''.join(inline))
            else:
                label = _label(value) if value is not None else False
            nonblank = bool(label) or formula
            if budget is not None:
                nonempty |= nonblank
                if row == 3 and nonblank:
                    budget_header_width = max(budget_header_width, col)
            elif name == 'Expenditure':
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
        if event == 'end' and tag == NS + 'row':
            if name == 'Funder Budgets' and all(h in row_values.values() for h in CONTRACT_HEADERS):
                require(all(list(row_values.values()).count(h) == 1 for h in CONTRACT_HEADERS), 'CONTRACT_KEY_HEADER')
                header_rows += 1
        if event == 'end':
            if depth == row_depth:
                row_depth = 0
            depth -= 1
            parents.pop()
    require(sheet_data_seen, 'XML_INVALID')
    if budget is not None:
        if name in budget['required']:
            require(nonempty, 'BUDGET_REQUIRED_SHEET')
        if name == budget['required'][0]:
            require(budget_header_width >= 47, 'BUDGET_HEADER_INVALID')
        budget['cells'] += max_row * max_col
    elif name == 'Expenditure':
        require(all(list(headers.values()).count(h) == 1 for h in LEDGER_HEADERS), 'LEDGER_REQUIRED_HEADER')
        require(extent * header_width <= 4000000, 'LEDGER_CELL_LIMIT')
        require(max_data_col <= header_width, 'LEDGER_DATA_BEYOND_HEADER')
    else:
        require(header_rows == 1, 'CONTRACT_KEY_HEADER')


def _metadata(archive, path):
    require(path in archive.namelist(), 'WORKBOOK_METADATA_INVALID')
    with archive.open(path) as stream:
        data = stream.read(_part_limit(path) + 1)
    require(len(data) <= _part_limit(path), 'PART_SIZE_LIMIT')
    return fromstring(data, forbid_dtd=True, forbid_entities=True, forbid_external=True)


def _canonical_package(archive):
    """Match ExcelReader's selection without duplicating its permissive resolver.

    openpyxl.reader.excel._find_workbook_part searches four override types before
    defaults; read_strings also uses an override, not the conventional filename.
    One canonical override and no fallback/ambiguous selections make both exact.
    """
    ct = '{http://schemas.openxmlformats.org/package/2006/content-types}'
    root = _metadata(archive, '[Content_Types].xml')
    require(root.tag == ct + 'Types', 'WORKBOOK_METADATA_INVALID')
    workbooks, strings, parts = [], [], set()
    for element in root:
        kind = element.get('ContentType')
        require(element.tag in (ct + 'Override', ct + 'Default'), 'WORKBOOK_METADATA_INVALID')
        if element.tag == ct + 'Default':
            require(kind not in (XLSX, XLSM, XLTX, XLTM, SHARED_STRINGS), 'WORKBOOK_METADATA_INVALID')
            continue
        path = element.get('PartName')
        require(path not in parts, 'WORKBOOK_METADATA_INVALID')
        parts.add(path)
        if kind in (XLSX, XLSM, XLTX, XLTM):
            workbooks.append(path)
        if kind == SHARED_STRINGS:
            strings.append(path)
    require(workbooks == ['/xl/workbook.xml'], 'WORKBOOK_METADATA_INVALID')
    require(strings in ([], ['/xl/sharedStrings.xml']), 'WORKBOOK_METADATA_INVALID')
    require(bool(strings) == ('xl/sharedStrings.xml' in archive.namelist()), 'WORKBOOK_METADATA_INVALID')


def _scan_workbook(upload, *, kind='funders', year=None):
    try:
        with zipfile.ZipFile(upload.buffer) as archive:
            if kind == 'budgets':
                _budget_relationships(archive)
            _canonical_package(archive)
            root = _metadata(archive, 'xl/workbook.xml')
            require(root.tag == NS + 'workbook' and len(root.findall(NS + 'sheets')) == 1,
                    'WORKBOOK_METADATA_INVALID')
            sheets = [(sheet.get('name'), sheet.get(RID))
                      for sheet in root.find(NS + 'sheets')]
            require(all(isinstance(name, str) for name, _ in sheets), 'WORKBOOK_METADATA_INVALID')
            required = (f'{year} Budget', 'Codes', f'Actual {year}') if kind == 'budgets' else ('Funder Budgets', 'Expenditure')
            require(all(sum(name == item for name, _ in sheets) == 1 for item in required), 'REQUIRED_SHEETS')
            budget = None
            if kind == 'budgets':
                require(len(sheets) <= 64, 'BUDGET_SHEET_LIMIT')
                budget = dict(cells=0, names={name for name, _ in sheets}, required=required)
            require(len({name.casefold() for name, _ in sheets}) == len(sheets), 'WORKBOOK_METADATA_INVALID')
            rel_ns = '{http://schemas.openxmlformats.org/package/2006/relationships}'
            rels = _metadata(archive, 'xl/_rels/workbook.xml.rels')
            require(rels.tag == rel_ns + 'Relationships', 'WORKBOOK_METADATA_INVALID')
            relationships = {}
            for element in rels:
                require(element.tag == rel_ns + 'Relationship', 'WORKBOOK_METADATA_INVALID')
                key, target = element.get('Id'), element.get('Target', '')
                require(key and key not in relationships, 'WORKBOOK_METADATA_INVALID')
                # Match get_dependents: absolute targets lose one leading slash;
                # relative targets normalize against the source part's directory.
                raw_path = target[1:] if target.startswith('/') else posixpath.join('xl', target)
                path = target[1:] if target.startswith('/') else posixpath.normpath(raw_path)
                require(raw_path == path and not path.endswith('/')
                        and _safe_path(path), 'WORKBOOK_METADATA_INVALID')
                relationships[key] = (path, element.get('Type'), element.get('TargetMode'))
            strings = _shared_strings(archive)
            for name, key in sheets:
                if budget is not None or name in ('Funder Budgets', 'Expenditure'):
                    require(key in relationships, 'WORKBOOK_METADATA_INVALID')
                    path, kind, mode = relationships[key]
                    require(kind == 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet'
                            and mode != 'External', 'WORKBOOK_METADATA_INVALID')
                    _scan_sheet(archive, path, name, strings, budget)
    except (ParseError, DefusedXmlException, zipfile.BadZipFile, KeyError, OSError, ValueError) as error:
        if isinstance(error, WorkbookError):
            raise
        raise WorkbookError('XML_INVALID') from None
    finally:
        upload.buffer.seek(0)


def _budget_formula_references(formula, names):
    # Tokenize formulas, never XML. Unknown tokenizer failures are value-free.
    from openpyxl.formula.tokenizer import Tokenizer
    try:
        tokens = Tokenizer('=' + formula).items
        for token in tokens:
            if token.type == 'OPERAND' and token.subtype == 'RANGE' and '!' in token.value:
                target = token.value.rsplit('!', 1)[0].strip("'").replace("''", "'")
                require('[' not in target and ']' not in target, 'BUDGET_EXTERNAL_REFERENCE')
                require(target in names, 'BUDGET_REFERENCED_SHEET_MISSING')
    except WorkbookError:
        raise
    except Exception:
        raise WorkbookError('WORKBOOK_DECODE_FAILURE') from None


def _budget_relationships(archive):
    for path in archive.namelist():
        require('externalLinks/' not in path and not path.endswith('vbaProject.bin'), 'BUDGET_EXTERNAL_REFERENCE')
        if path.endswith('.rels'):
            _check_declarations(archive, path, 'XML_INVALID')
            for element in _metadata(archive, path):
                # Read-only cell values do not include hyperlinks; never resolve targets.
                worksheet_hyperlink = (
                    posixpath.dirname(path) == 'xl/worksheets/_rels'
                    and element.get('Type') ==
                    'http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink'
                )
                require(element.get('TargetMode') != 'External' or worksheet_hyperlink,
                        'BUDGET_EXTERNAL_REFERENCE')



def scan_workbook(upload, *, kind='funders', year=None):
    if kind == 'funders':
        return _scan_workbook(upload)
    require(kind == 'budgets' and type(year) is int, 'WORKBOOK_METADATA_INVALID')
    from collections import Counter
    from contextlib import redirect_stdout, redirect_stderr
    from io import StringIO
    import warnings
    try:
        with (StringIO() as discarded, redirect_stdout(discarded), redirect_stderr(discarded),
              warnings.catch_warnings(record=True) as recorded):
            warnings.simplefilter('always')
            _scan_workbook(upload, kind=kind, year=year)
            diagnostics = [{'category': category, 'count': count} for category, count in
                           sorted(Counter(w.category.__name__ for w in recorded).items())]
            recorded.clear()
            return diagnostics
    except WorkbookError:
        raise
    except Exception:
        raise WorkbookError('WORKBOOK_DECODE_FAILURE') from None
