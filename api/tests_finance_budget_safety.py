from io import BytesIO
from unittest.mock import patch
from django.test import TestCase
from api.finance_budget_test_utils import budget_workbook
from api.tests_finance_upload_safety import rewrite, NAME
from api.parsers import finance_workbook as parser


class BudgetSafetyTests(TestCase):
    def setUp(self):
        from api.finance_run_test_utils import actor
        from api.finance_budget_test_utils import budget_ledger
        self.user = actor()
        self.dependency = budget_ledger(self.user)

    def upload(self, data):
        from api.services.finance_runs import upload_workbook
        return upload_workbook(BytesIO(data), self.user, kind='budgets', year=2026,
                               source_name=NAME, content_type=parser.MIME,
                               ledger_run_id=self.dependency.pk)

    def scan(self,data):
        with parser.preflight(BytesIO(data),source_name=NAME,content_type=parser.MIME) as upload:
            parser.scan_workbook(upload,kind='budgets',year=2026)

    def test_31_sheet_unsized_export_reaches_producer(self):
        data = budget_workbook(sheets=31,unsized=True)
        self.scan(data)
        from api.services import finance_runs
        with patch.object(finance_runs, 'build_budget_run_artifact', wraps=finance_runs.build_budget_run_artifact) as producer:
            run, status = self.upload(data)
        producer.assert_called_once()
        self.assertEqual((status, run.status), (201, 'candidate'))

    def test_stream_cap_and_unsafe_zip_create_no_history(self):
        with patch.object(parser,'MAX_COMPRESSED',32):
            with self.assertRaises(parser.WorkbookError): self.scan(budget_workbook())
        with self.assertRaises(parser.WorkbookError): self.scan(b'unsafe')
        from api.models import FinanceRun
        from api.services import finance_runs
        with patch.object(finance_runs, 'build_budget_run_artifact') as producer:
            for data in (b'unsafe', budget_workbook()):
                with patch.object(parser, 'MAX_COMPRESSED', 32):
                    with self.assertRaises(finance_runs.FinanceRunError): self.upload(data)
        producer.assert_not_called()
        self.assertFalse(FinanceRun.objects.filter(kind='budgets').exists())

    def test_dimension_spoof_duplicate_nodes_and_shared_strings_reject_early(self):
        data=budget_workbook()
        for extra in (b'<row r="5001"/>',b'<row r="3"/>',b'<row r="9"><c r="A9"/><c r="A9"/></row>'):
            with self.assertRaises(parser.WorkbookError):
                self.scan(rewrite(data,{'xl/worksheets/sheet1.xml':lambda x:x.replace(b'</sheetData>',extra+b'</sheetData>')}))
        with patch.object(parser,'MAX_SHEET_RETAINED_NODES',2):
            with self.assertRaises(parser.WorkbookError): self.scan(data)

    def test_external_link_and_missing_referenced_sheet_refuse(self):
        data=budget_workbook()
        for formula in (b"'Missing'!A1",b"'[external.xlsx]Sheet'!A1"):
            with self.assertRaises(parser.WorkbookError):
                self.scan(rewrite(data,{'xl/worksheets/sheet1.xml':lambda x:x.replace(b'</sheetData>',b'<row r="10"><c r="F10"><f>'+formula+b'</f></c></row></sheetData>')}))
        with self.assertRaises(parser.WorkbookError):
            self.scan(rewrite(data,extra=[('xl/worksheets/_rels/sheet1.xml.rels',b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="https://example.invalid" TargetMode="External" Type="hyperlink"/></Relationships>')]))

    def test_empty_ancillary_is_not_empty_required_sheet(self):
        self.scan(budget_workbook(sheets=31,unsized=True))
        with self.assertRaises(parser.WorkbookError):
            self.scan(rewrite(budget_workbook(),{'xl/worksheets/sheet3.xml':lambda x:b'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData/></worksheet>'}))

    def test_parser_diagnostics_never_leak_auxiliary_values(self):
        data=rewrite(budget_workbook(),{'xl/worksheets/sheet1.xml':lambda x:x.replace(b'</sheetData>',b'<row r="5001"><c r="F5001" t="inlineStr"><is><t>PRIVATE_DIAGNOSTIC</t></is></c></row></sheetData>')})
        with self.assertRaises(parser.WorkbookError) as caught: self.scan(data)
        self.assertEqual(caught.exception.code, 'SHEET_BOUNDS')
        self.assertNotIn('PRIVATE',str(caught.exception))

    def test_scanner_unknown_decode_and_warning_channels_are_value_free(self):
        import sys, warnings
        from contextlib import redirect_stdout, redirect_stderr
        from io import StringIO
        original=parser._scan_sheet
        def noisy(*args,**kwargs):
            print('PRIVATE_STDOUT');print('PRIVATE_STDERR',file=sys.stderr)
            warnings.warn('PRIVATE_WARNING',UserWarning)
            return original(*args,**kwargs)
        stdout,stderr=StringIO(),StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr), patch.object(parser,'_scan_sheet',side_effect=noisy):
            with parser.preflight(BytesIO(budget_workbook()),source_name=NAME,content_type=parser.MIME) as upload:
                diagnostics=parser.scan_workbook(upload,kind='budgets',year=2026)
        self.assertEqual(stdout.getvalue()+stderr.getvalue(),'')
        self.assertEqual(diagnostics,[{'category':'UserWarning','count':3}])
        with patch.object(parser,'_scan_sheet',side_effect=RuntimeError('PRIVATE_UNKNOWN')):
            with self.assertRaisesRegex(parser.WorkbookError,'^WORKBOOK_DECODE_FAILURE$'):
                self.scan(budget_workbook())

    def test_sheet_aggregate_and_header_limits_are_incremental(self):
        data=budget_workbook(sheets=7)
        sparse=b'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="5000"><c r="IV5000"><v>1</v></c></row></sheetData></worksheet>'
        changes={f'xl/worksheets/sheet{i}.xml':lambda x:sparse for i in range(4,8)}
        with self.assertRaisesRegex(parser.WorkbookError,'BUDGET_SHEET_LIMIT'):
            self.scan(rewrite(data,changes))
        with self.assertRaisesRegex(parser.WorkbookError,'BUDGET_SHEET_LIMIT'):
            self.scan(budget_workbook(sheets=65))
        with self.assertRaisesRegex(parser.WorkbookError,'BUDGET_HEADER_INVALID'):
            self.scan(rewrite(budget_workbook(),{'xl/worksheets/sheet1.xml':lambda x:x.replace(b'AU3',b'AT3')}))

    def test_budget_shared_string_structure_rejects_before_openpyxl(self):
        data=budget_workbook()
        def content_types(x):
            return x.replace(b'</Types>',b'<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/></Types>')
        bad=rewrite(data,{'[Content_Types].xml':content_types},extra=[('xl/sharedStrings.xml',b'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><r><t>Synthetic hostile value</t></r></sst>')])
        from api.services import finance_runs
        from api.models import FinanceRun
        with patch('openpyxl.load_workbook') as load:
            with self.assertRaisesRegex(finance_runs.FinanceRunError,'SHARED_STRING_LIMIT'):
                self.upload(bad)
        load.assert_not_called()
        self.assertFalse(FinanceRun.objects.filter(kind='budgets').exists())

    def test_producer_decode_schema_and_warning_boundaries(self):
        import sys,warnings
        from contextlib import redirect_stdout,redirect_stderr
        from io import StringIO
        from api.services import finance_runs
        from api.models import FinanceRun
        from masi_finance.publish import budget_run
        original=budget_run.read_org_budget
        def noisy(*args,**kwargs):
            print('Synthetic private stdout');print('Synthetic private stderr',file=sys.stderr)
            warnings.warn('Synthetic private warning',UserWarning)
            return original(*args,**kwargs)
        stdout,stderr=StringIO(),StringIO()
        with redirect_stdout(stdout),redirect_stderr(stderr),patch.object(budget_run,'read_org_budget',side_effect=noisy):
            run,_=self.upload(budget_workbook())
        self.assertEqual(stdout.getvalue()+stderr.getvalue(),'')
        self.assertEqual([f['message'] for f in run.payload['findings'] if f['code']=='PARSER_WARNING'],['UserWarning: 1'])
        for raised,expected in [(RuntimeError('Synthetic private unknown'),'WORKBOOK_DECODE_FAILURE'),
                                (budget_run.RunSchemaError('RUN_SCHEMA_INVALID'),'RUN_SCHEMA_INVALID')]:
            with patch.object(budget_run,'read_org_budget',side_effect=raised):
                with self.assertRaisesRegex(finance_runs.FinanceRunError,expected):
                    self.upload(budget_workbook(sheets=4))
        self.assertEqual(FinanceRun.objects.filter(kind='budgets').count(),1)
