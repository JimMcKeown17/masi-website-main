"""Synthetic XLSX and adversarial ZIP tests; no real financial workbooks."""
from datetime import date
from io import BytesIO
import os
import re
import struct
import zipfile
import warnings
from unittest.mock import patch
from django.test import SimpleTestCase
from openpyxl import Workbook

MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
NAME = '20260901 - Synthetic.xlsx'


def workbook_bytes():
    wb = Workbook()
    ws = wb.active
    ws.title = 'Expenditure'
    ws.append(['Date', 'Year', 'Name', 'Amount', 'Paid By', 'Category 1',
               'Category 2', 'Category 3', 'BC', 'Allocation', 'Budget Key'])
    ws.append([date(2026, 1, 2), 2026, 'Synthetic', 10, 'Bank', 'Programme',
               'Supplies', None, None, 10, 'TEST'])
    ws = wb.create_sheet('Funder Budgets')
    ws.append(['TEST', 'Synthetic funder'])
    ws.append([None, 'Category', 'Budget', 'Spent'])
    ws.append([None, 'Supplies', 100,
               '=SUM(SUMIFS(Expenditure!J:J,Expenditure!G:G,B3,Expenditure!K:K,"TEST"))'])
    ws.append([None, 'Total'])
    ws.append([])
    ws.append(['Budget Key', 'Funder', 'Start Date', 'End Date', 'Description'])
    ws.append(['TEST', 'Synthetic funder', date(2026, 1, 1), date(2026, 12, 31), 'Synthetic'])
    with BytesIO() as output:
        wb.save(output)
        wb.close()
        return output.getvalue()


def rewrite(data, changes=None, extra=()):
    with BytesIO() as output, zipfile.ZipFile(BytesIO(data)) as source:
        with warnings.catch_warnings(), zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as target:
            warnings.filterwarnings('ignore', message='Duplicate name:', category=UserWarning)
            for entry in source.infolist():
                value = source.read(entry)
                if changes and entry.filename in changes:
                    value = changes[entry.filename](value)
                target.writestr(entry.filename, value)
            for name, value in extra:
                target.writestr(name, value)
        return output.getvalue()


class BodyForbidden(BytesIO):
    @property
    def body(self):
        raise AssertionError('request.body is forbidden')


class WorkbookSafetyTests(SimpleTestCase):
    def setUp(self):
        from api.parsers import finance_workbook
        self.p = finance_workbook
        self.data = workbook_bytes()

    def preflight(self, data=None, **kwargs):
        return self.p.preflight(BodyForbidden(data if data is not None else self.data),
                                source_name=NAME, content_type=MIME, **kwargs)

    def reject(self, data, code, *, sheet=False, **kwargs):
        with self.assertRaises(self.p.WorkbookError) as caught:
            with self.preflight(data, **kwargs) as upload:
                if sheet:
                    self.p.scan_workbook(upload)
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(str(caught.exception), code)

    def test_valid_body_never_accesses_body_and_buffer_closes(self):
        with self.preflight() as upload:
            self.p.scan_workbook(upload)
            buffer = upload.buffer
        self.assertTrue(buffer.closed)

    def test_compressed_cap_missing_lying_and_true_length_stops_at_plus_one(self):
        for length in (None, '1', '1024'):
            with self.subTest(length=length), patch.object(self.p, 'MAX_COMPRESSED', 1024):
                stream = BodyForbidden(b'x' * 4096)
                with self.assertRaises(self.p.WorkbookError) as caught:
                    with self.p.preflight(stream, source_name=NAME, content_type=MIME, content_length=length):
                        pass
                self.assertEqual(caught.exception.code, 'UPLOAD_TOO_LARGE')
                self.assertEqual(stream.tell(), 1025)

    def test_declared_length_invalid_before_read(self):
        for length in ('0', '-1', 'bad', str(32 * 1024 * 1024 + 1)):
            with self.subTest(length=length):
                self.reject(b'', 'CONTENT_LENGTH_INVALID', content_length=length)

    def test_envelope_type_and_basename(self):
        for field, value, code in [('content_type', 'multipart/form-data', 'CONTENT_TYPE_INVALID'),
                                   ('source_name', '../20260901 - Private.xlsx', 'SOURCE_INVALID'),
                                   ('source_name', '20260230 - Private.xlsx', 'SOURCE_INVALID')]:
            options = dict(source_name=NAME, content_type=MIME)
            options[field] = value
            with self.assertRaises(self.p.WorkbookError) as caught:
                with self.p.preflight(BodyForbidden(self.data), **options):
                    pass
            self.assertEqual(caught.exception.code, code)

    def test_zip_entry_count(self):
        self.reject(rewrite(self.data, extra=[(f'extra/{n}', b'x') for n in range(257)]), 'ZIP_ENTRY_LIMIT')

    def test_zip_duplicate_and_paths(self):
        for name, code in [('xl/workbook.xml', 'ZIP_DUPLICATE_ENTRY'), ('../x', 'ZIP_PATH_INVALID'),
                           ('/x', 'ZIP_PATH_INVALID'), ('a\\x', 'ZIP_PATH_INVALID'),
                           ('C:/x', 'ZIP_PATH_INVALID')]:
            with self.subTest(name=name):
                self.reject(rewrite(self.data, extra=[(name, b'x')]), code)

    def test_zip_encrypted(self):
        data = bytearray(self.data)
        for signature, offset in [(b'PK\x03\x04', 6), (b'PK\x01\x02', 8)]:
            index = data.find(signature)
            flags = struct.unpack_from('<H', data, index + offset)[0]
            struct.pack_into('<H', data, index + offset, flags | 1)
        self.reject(bytes(data), 'ZIP_ENCRYPTED')

    def test_zip_expanded_and_ratio_limits(self):
        with patch.object(self.p, 'MAX_ENTRY_EXPANDED', 100):
            self.reject(self.data, 'ZIP_ENTRY_EXPANDED_LIMIT')
        with patch.object(self.p, 'MAX_TOTAL_EXPANDED', 100):
            self.reject(self.data, 'ZIP_TOTAL_EXPANDED_LIMIT')
        self.reject(rewrite(self.data, extra=[('bomb', b'x' * 100000)]), 'ZIP_RATIO_LIMIT')

    def test_missing_duplicate_sheets_and_headers(self):
        for old, new, code in [(b'name="Expenditure"', b'name="Other"', 'REQUIRED_SHEETS'),
                               (b'name="Funder Budgets"', b'name="Expenditure"', 'REQUIRED_SHEETS')]:
            self.reject(rewrite(self.data, {'xl/workbook.xml': lambda x: x.replace(old, new)}), code, sheet=True)
        for path, old, code in [('xl/worksheets/sheet1.xml', b'>Paid By<', 'LEDGER_REQUIRED_HEADER'),
                                ('xl/worksheets/sheet2.xml', b'>Start Date<', 'CONTRACT_KEY_HEADER')]:
            self.reject(rewrite(self.data, {path: lambda x: x.replace(old, b'>Other<')}), code, sheet=True)

    def test_declared_rows_columns_and_product(self):
        for extent, code in [('A1:K50001', 'SHEET_BOUNDS'), ('A1:IW2', 'SHEET_BOUNDS'),
                              ('A1:DX50000', 'LEDGER_CELL_LIMIT')]:
            def change(x):
                x = re.sub(rb'<dimension ref="[^"]+"', f'<dimension ref="{extent}"'.encode(), x)
                if extent == 'A1:DX50000':
                    x = x.replace(b'</row>', b'<c r="DX1" t="inlineStr"><is><t>Extra</t></is></c></row>', 1)
                return x
            self.reject(rewrite(self.data, {'xl/worksheets/sheet1.xml': change}), code, sheet=True)

    def test_spoofed_dimensions_sparse_headers_and_data_beyond_header(self):
        for cell, code in [('A50001', 'SHEET_BOUNDS'), ('L2', 'LEDGER_DATA_BEYOND_HEADER'),
                           ('DY1', 'LEDGER_HEADER_LIMIT'), ('LCV1', 'SHEET_BOUNDS')]:
            def change(x):
                row = re.search(r'\d+', cell).group()
                extra = f'<row r="{row}"><c r="{cell}" t="inlineStr"><is><t>Private</t></is></c></row>'.encode()
                return x.replace(b'</sheetData>', extra + b'</sheetData>')
            self.reject(rewrite(self.data, {'xl/worksheets/sheet1.xml': change}), code, sheet=True)

    def test_defused_xml_rejects_entities(self):
        data = rewrite(self.data, {'xl/workbook.xml': lambda x: b'<!DOCTYPE x [<!ENTITY secret "private">]>' + x})
        self.reject(data, 'XML_INVALID', sheet=True)

    def test_valid_body_above_default_django_memory_limit(self):
        data = rewrite(self.data, extra=[('padding.bin', os.urandom(2700000))])
        self.assertGreater(len(data), 2621440)
        with self.preflight(data) as upload:
            self.p.scan_workbook(upload)

    def test_four_million_cell_boundary_and_budget_bounds(self):
        def boundary(x):
            x = re.sub(rb'<dimension ref="[^"]+"', b'<dimension ref="A1:DX31250"', x)
            return x.replace(b'</row>', b'<c r="DX1" t="inlineStr"><is><t>Extra</t></is></c></row>', 1)
        data = rewrite(self.data, {'xl/worksheets/sheet1.xml': boundary})
        with self.preflight(data) as upload:
            self.p.scan_workbook(upload)
        self.reject(rewrite(data, {'xl/worksheets/sheet1.xml': lambda x: x.replace(b'DX31250', b'DX31251')}), 'LEDGER_CELL_LIMIT', sheet=True)
        self.reject(rewrite(self.data, {'xl/worksheets/sheet2.xml': lambda x: re.sub(rb'<dimension ref="[^"]+"', b'<dimension ref="A1:E5001"', x)}), 'SHEET_BOUNDS', sheet=True)

    def test_understated_zip_size_does_not_hide_expansion(self):
        data = bytearray(rewrite(self.data, extra=[('bomb', b'x' * 100000)]))
        start = 0
        while True:
            start = data.find(b'PK\x01\x02', start)
            if start < 0:
                break
            name_length = struct.unpack_from('<H', data, start + 28)[0]
            if data[start + 46:start + 46 + name_length] == b'bomb':
                struct.pack_into('<I', data, start + 24, 1)
                break
            start += 4
        self.reject(bytes(data), 'ZIP_RATIO_LIMIT')

    def test_buffer_closed_when_sheet_scan_fails(self):
        data = rewrite(self.data, {'xl/workbook.xml': lambda x: b'invalid'})
        with self.assertRaises(self.p.WorkbookError):
            with self.preflight(data) as upload:
                self.p.scan_workbook(upload)
        self.assertTrue(upload.buffer.closed)

    def test_actual_32_mib_cap_reads_only_one_excess_byte(self):
        class GeneratedStream:
            consumed = 0
            def read(self, count):
                self.consumed += count
                return b'x' * count
        stream = GeneratedStream()
        with self.assertRaises(self.p.WorkbookError) as caught:
            with self.p.preflight(stream, source_name=NAME, content_type=MIME):
                pass
        self.assertEqual(caught.exception.code, 'UPLOAD_TOO_LARGE')
        self.assertEqual(stream.consumed, 32 * 1024 * 1024 + 1)

    def test_streamed_product_cannot_hide_behind_small_dimensions(self):
        def change(x):
            x = x.replace(b'</row>', b'<c r="DX1" t="inlineStr"><is><t>Extra</t></is></c></row>', 1)
            return x.replace(b'</sheetData>', b'<row r="31251"><c r="A31251"><v>1</v></c></row></sheetData>')
        self.reject(rewrite(self.data, {'xl/worksheets/sheet1.xml': change}), 'LEDGER_CELL_LIMIT', sheet=True)
