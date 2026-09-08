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

    def structural_workbook(self, kind, shape, part='xl/worksheets/sheet1.xml'):
        def change(xml):
            root = ET.fromstring(xml)
            sheet = root.find(NS + 'sheetData')
            if kind == 'budgets' and part.endswith('sheet1.xml'):
                row = ET.SubElement(sheet, NS + 'row', r='8')
                cell = ET.SubElement(row, NS + 'c', r='F8')
                ET.SubElement(cell, NS + 'v').text = '999'
                next_row = '9'
            else:
                row = sheet.findall(NS + 'row')[-1]
                cell = row[-1]
                next_row = str(int(row.get('r')) + 1)
            number = row.get('r')
            if shape == 'nested_row':
                ET.SubElement(row, NS + 'row', r=next_row)
            elif shape in ('non_cell', 'foreign_child'):
                cell.tag = NS + 'x' if shape == 'non_cell' else '{urn:foreign}c'
                if kind == 'budgets' and part.endswith('sheet1.xml'):
                    ET.SubElement(row, NS + 'c', r='E8')
            elif shape == 'missing_cell_coordinate':
                del cell.attrib['r']
            elif shape == 'malformed_cell_coordinate':
                cell.set('r', 'f' + number)
            elif shape == 'missing_row_coordinate':
                del row.attrib['r']
            elif shape == 'malformed_row_coordinate':
                row.set('r', number + '.0')
            elif shape == 'second_sheet_data':
                ET.SubElement(root, NS + 'sheetData')
            elif shape == 'missing_sheet_data':
                root.remove(sheet)
            elif shape == 'nested_sheet_data':
                root.remove(sheet)
                ET.SubElement(root, NS + 'extLst').append(sheet)
            elif shape == 'foreign_sheet_data':
                sheet.tag = '{urn:foreign}sheetData'
            elif shape == 'row_outside_sheet_data':
                sheet.remove(row)
                root.append(row)
            elif shape == 'row_in_cell':
                ET.SubElement(cell, NS + 'row', r=next_row)
            elif shape == 'foreign_row':
                row.tag = '{urn:foreign}row'
            elif shape == 'cell_outside_row':
                row.remove(cell)
                sheet.append(cell)
            elif shape == 'cell_in_cell':
                ET.SubElement(cell, NS + 'c', r='Z' + number)
            elif shape == 'wrapped_cell':
                row.remove(cell)
                ET.SubElement(row, NS + 'wrapper').append(cell)
            else:
                raise AssertionError(shape)
            return ET.tostring(root)
        data = budget_workbook() if kind == 'budgets' else workbook_bytes()
        return rewrite(data, {part: change})

    def assert_structures_refused(self, kind):
        shapes = (
            'nested_row', 'non_cell', 'foreign_child', 'missing_cell_coordinate',
            'malformed_cell_coordinate', 'missing_row_coordinate',
            'malformed_row_coordinate', 'second_sheet_data', 'missing_sheet_data',
            'nested_sheet_data', 'foreign_sheet_data', 'row_outside_sheet_data',
            'row_in_cell', 'foreign_row', 'cell_outside_row', 'cell_in_cell',
            'wrapped_cell',
        )
        # Exercise every scanned part, including budget Codes/Actual and the
        # released Funder Budgets sheet, with the same pre-producer guarantee.
        for part_number in range(1, 4 if kind == 'budgets' else 3):
            for shape in shapes:
                with self.subTest(kind=kind, part=part_number, shape=shape):
                    self.assert_refused(kind, self.structural_workbook(
                        kind, shape, f'xl/worksheets/sheet{part_number}.xml'), 'XML_INVALID')

    def test_budget_noncanonical_structure_refuses_before_producer(self):
        self.assert_structures_refused('budgets')

    def test_funders_noncanonical_structure_refuses_before_producer(self):
        self.assert_structures_refused('funders')

    def assert_canonical_variety(self, kind):
        def change(xml):
            root = ET.fromstring(xml)
            sheet = root.find(NS + 'sheetData')
            number = '6' if kind == 'budgets' else '2'
            row = sheet.find(NS + 'row' + f"[@r='{number}']")
            # The row already contains an inline string. Make both supported
            # forms explicit, including a styled, empty, self-closing cell.
            inline_cell = next(cell for cell in row if cell.get('t') == 'inlineStr')
            self.assertIsNotNone(inline_cell.find(NS + 'is/' + NS + 't'))
            ET.SubElement(row, NS + 'c', r='AU' + number, s='0', t='n')
            result = ET.tostring(root)
            self.assertIn(f'r="AU{number}" s="0" t="n" />'.encode(), result)
            return result
        data = budget_workbook() if kind == 'budgets' else workbook_bytes()
        name = 'build_budget_run_artifact' if kind == 'budgets' else 'build_run_artifact'
        with patch.object(finance_runs, name, wraps=getattr(finance_runs, name)) as producer:
            response = self.upload(kind, rewrite(data, {'xl/worksheets/sheet1.xml': change}))
        self.assertEqual(response.status_code, 201, response.data)
        producer.assert_called_once()
        run = FinanceRun.objects.get(pk=response.data['id'])
        self.assertEqual(run.status, 'candidate', run.failure)
        if kind == 'funders':
            self.assertEqual(run.ledger_rows.count(), 1)

    def test_budget_canonical_inline_string_and_empty_styled_cell(self):
        self.assert_canonical_variety('budgets')

    def test_funders_canonical_inline_string_and_empty_styled_cell(self):
        self.assert_canonical_variety('funders')
