"""Raw upload regressions for rows/cells read by the installed producer."""
from urllib.parse import urlencode
from unittest.mock import patch
from xml.etree import ElementTree as ET

from django.test import TestCase
from rest_framework.test import APIClient

from api.finance_budget_test_utils import budget_workbook, budget_ledger
from api.finance_run_test_utils import actor
from api.models import FinanceRun
from api.parsers.finance_workbook import MIME, NS
from api.services import finance_runs
from api.tests_finance_upload_safety import NAME, rewrite, workbook_bytes


class SheetOrderUploadTests(TestCase):
    def setUp(self):
        self.user = actor()
        self.dependency = budget_ledger(self.user)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def upload(self, kind, data):
        query = dict(kind=kind, year=2026, source_name=NAME)
        if kind == 'budgets':
            query['ledger_run_id'] = str(self.dependency.pk)
        return self.client.post('/api/finance/runs/?' + urlencode(query),
                                data, content_type=MIME)

    def rows(self, kind, *, reversed_order=False):
        def change(xml):
            root = ET.fromstring(xml)
            sheet = root.find(NS + 'sheetData')
            if kind == 'budgets':
                populated = ET.SubElement(sheet, NS + 'row', r='8')
                cell = ET.SubElement(populated, NS + 'c', r='F8')
                ET.SubElement(cell, NS + 'v').text = '999'
                empty = ET.SubElement(sheet, NS + 'row', r='9')
            else:
                populated = sheet.find(NS + 'row' + "[@r='2']")
                empty = ET.SubElement(sheet, NS + 'row', r='3')
            if reversed_order:
                sheet.remove(populated)
                sheet.append(populated)
            # Include both rows in the producer's declared iteration bounds.
            root.find(NS + 'dimension').set('ref', 'A1:AU9' if kind == 'budgets' else 'A1:K3')
            return ET.tostring(root)
        data = budget_workbook() if kind == 'budgets' else workbook_bytes()
        return rewrite(data, {'xl/worksheets/sheet1.xml': change})

    def assert_refused(self, kind, data, code):
        before = set(FinanceRun.objects.values_list('pk', flat=True))
        name = 'build_budget_run_artifact' if kind == 'budgets' else 'build_run_artifact'
        with patch.object(finance_runs, name, wraps=getattr(finance_runs, name)) as producer:
            response = self.upload(kind, data)
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(response.data['code'], code)
        producer.assert_not_called()
        self.assertEqual(set(FinanceRun.objects.values_list('pk', flat=True)), before)

    def test_budget_populated_row_8_after_row_9_refuses_before_producer(self):
        self.assert_refused('budgets', self.rows('budgets', reversed_order=True), 'XML_INVALID')

    def test_budget_ordered_row_8_reaches_hierarchy_failure(self):
        with patch.object(finance_runs, 'build_budget_run_artifact',
                          wraps=finance_runs.build_budget_run_artifact) as producer:
            response = self.upload('budgets', self.rows('budgets'))
        self.assertEqual(response.status_code, 201, response.data)
        producer.assert_called_once()
        run = FinanceRun.objects.get(pk=response.data['id'])
        self.assertEqual(run.status, 'failed')
        self.assertIn('BUDGET_HIERARCHY_INVALID', str(run.failure))

    def test_funders_populated_expenditure_row_after_higher_row_refuses_before_producer(self):
        self.assert_refused('funders', self.rows('funders', reversed_order=True), 'XML_INVALID')

    def test_funders_ordered_expenditure_reaches_candidate_with_ledger_row(self):
        with patch.object(finance_runs, 'build_run_artifact',
                          wraps=finance_runs.build_run_artifact) as producer:
            response = self.upload('funders', self.rows('funders'))
        self.assertEqual(response.status_code, 201, response.data)
        producer.assert_called_once()
        run = FinanceRun.objects.get(pk=response.data['id'])
        self.assertEqual(run.status, 'candidate')
        self.assertEqual(run.ledger_rows.count(), 1)

    def test_decreasing_cells_refuse_before_producer_for_both_kinds(self):
        for kind in ('budgets', 'funders'):
            with self.subTest(kind=kind):
                def change(xml):
                    root = ET.fromstring(xml)
                    number = '6' if kind == 'budgets' else '2'
                    row = root.find(NS + 'sheetData').find(NS + 'row' + f"[@r='{number}']")
                    cell = row[0]
                    row.remove(cell)
                    row.append(cell)
                    return ET.tostring(root)
                data = budget_workbook() if kind == 'budgets' else workbook_bytes()
                self.assert_refused(kind, rewrite(data, {'xl/worksheets/sheet1.xml': change}), 'XML_INVALID')
