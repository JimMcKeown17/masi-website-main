"""Formula definition fidelity and external dependencies at raw upload admission."""
from xml.etree import ElementTree as ET
from unittest.mock import patch
from django.test import TestCase
from api import tests_finance_cell_payloads as payload_tests
from api.tests_finance_upload_safety import rewrite, workbook_bytes
from api.finance_budget_test_utils import budget_workbook
from api.finance_run_test_utils import approve
from api.parsers import finance_workbook as parser
from api.services import finance_runs
from api.models import FinanceRun

BASE = 'IFERROR(VLOOKUP(E6,\'Actual 2026\'!A:B,2,0),"")'


def formulas(xml, cells):
    root = ET.fromstring(xml)
    rows = root.find(parser.NS + 'sheetData')
    for coordinate, text, attrs, cache in cells:
        number = str(parser._coordinate(coordinate)[0])
        row = rows.find(parser.NS + f"row[@r='{number}']")
        if row is None:
            row = ET.SubElement(rows, parser.NS + 'row', r=number)
        cell = row.find(parser.NS + f"c[@r='{coordinate}']")
        if cell is None:
            cell = ET.SubElement(row, parser.NS + 'c', r=coordinate)
        cell.clear(); cell.set('r', coordinate); cell.set('t', 'n')
        ET.SubElement(cell, parser.NS + 'f', attrs).text = text
        if cache is not None:
            ET.SubElement(cell, parser.NS + 'v').text = cache
        row[:] = sorted(row, key=lambda c: parser._coordinate(c.get('r'))[1])
    rows[:] = sorted(rows, key=lambda r: int(r.get('r')))
    return ET.tostring(root)


class FormulaPayloadUploadTests(TestCase):
    setUp = payload_tests.CellPayloadUploadTests.setUp
    upload = payload_tests.CellPayloadUploadTests.upload

    def exercise(self, kind, data, code=None, failure=None):
        before = set(FinanceRun.objects.values_list('pk', flat=True))
        name = 'build_budget_run_artifact' if kind == 'budgets' else 'build_run_artifact'
        with patch.object(finance_runs, name, wraps=getattr(finance_runs, name)) as producer:
            response = self.upload(kind, data)
        if code:
            self.assertEqual(response.status_code, 400, response.data)
            self.assertEqual(response.data['code'], code)
            producer.assert_not_called()
            self.assertEqual(set(FinanceRun.objects.values_list('pk', flat=True)), before)
        else:
            self.assertEqual(response.status_code, 201, response.data)
            producer.assert_called_once()
            run = FinanceRun.objects.get(pk=response.data['id'])
            if failure:
                self.assertEqual(run.status, 'failed')
                self.assertEqual(run.failure['code'], failure)
            else:
                self.assertEqual(run.status, 'candidate', run.failure)
                self.assertEqual(approve(run, self.user, override_anti_rollback=True).status, 'approved')

    def test_budget_adjacent_explicit_shared_follower_refused(self):
        cells = [('G6', BASE+'/2', dict(t='shared', si='1', ref='G6:G7'), None),
                 ('G7', BASE.replace('E6', 'E7'), dict(t='shared', si='1'), None)]
        data = rewrite(budget_workbook(half=True), {'xl/worksheets/sheet1.xml': lambda x: formulas(x, cells)})
        self.exercise('budgets', data, 'XML_INVALID')

    def test_budget_ordinary_half_full_control_fails_in_producer(self):
        data = rewrite(budget_workbook(half=True), {'xl/worksheets/sheet1.xml': lambda x: formulas(x, [('G7', BASE.replace('E6','E7'), {}, None)])})
        self.exercise('budgets', data, failure='BUDGET_BC_BINDING_INVALID')

    def test_budget_empty_shared_follower_candidate_and_approval(self):
        cells = [('G6', BASE+'/2', dict(t='shared', si='1', ref='G6:G7'), None),
                 ('G7', None, dict(t='shared', si='1'), None)]
        data = rewrite(budget_workbook(half=True), {'xl/worksheets/sheet1.xml': lambda x: formulas(x, cells)})
        self.exercise('budgets', data)

    def external_fixture(self, formula, defined=None):
        changes = {'xl/worksheets/sheet1.xml': lambda x: formulas(x, [('F6', formula, {}, '17')])}
        if defined is not None:
            def names(xml):
                root = ET.fromstring(xml)
                defs = root.find(parser.NS + 'definedNames')
                if defs is None: defs = ET.SubElement(root, parser.NS + 'definedNames')
                ET.SubElement(defs, parser.NS + 'definedName', name='SyntheticBudget').text = defined
                return ET.tostring(root)
            changes['xl/workbook.xml'] = names
        return rewrite(budget_workbook(), changes)


BAD = {
    'explicit_shared_follower': [('Z1','1',dict(t='shared',si='1',ref='Z1:Z2'),'1'),('Z2','999',dict(t='shared',si='1'),'1')],
    'shared_missing_si': [('Z1','1',dict(t='shared',ref='Z1:Z2'),'1')],
    'shared_missing_master': [('Z1',None,dict(t='shared',si='1'),'1')],
    'shared_missing_ref': [('Z1','1',dict(t='shared',si='1'),'1')],
    'shared_outside_ref': [('Z1','1',dict(t='shared',si='1',ref='Z1:Z1'),'1'),('Z2',None,dict(t='shared',si='1'),'1')],
    'shared_redefined_ref': [('Z1','1',dict(t='shared',si='1',ref='Z1:Z2'),'1'),('Z2',None,dict(t='shared',si='1',ref='Z2:Z3'),'1')],
    'normal_datatable_inputs': [('Z1','1',dict(r1='A1',dt2D='1'),'1')],
    'array_datatable_inputs': [('Z1','1',dict(t='array',ref='Z1:Z2',r1='A1'),'1')],
    'shared_datatable_inputs': [('Z1','1',dict(t='shared',si='1',ref='Z1:Z2',r1='A1'),'1')],
    'unknown_formula_type': [('Z1','1',dict(t='unknown'),'1')],
    'normal_shared_index': [('Z1','1',dict(si='1'),'1')],
    'datatable_ignored_text': [('Z1','999',dict(t='dataTable',ref='Z1:Z2',r1='A1'),'1')],
}
GOOD = {
    'shared': [('Z1','1',dict(t='shared',si='1',ref='Z1:Z2'),'1'),('Z2',None,dict(t='shared',si='1'),'1')],
    'array': [('Z1','1+2',dict(t='array',ref='Z1:Z2'),'3')],
    'datatable': [('Z1',None,dict(t='dataTable',ref='Z1:Z2',r1='A1'),'1')],
    'normal_flags': [('Z1','1',dict(t='normal',ca='1',bx='0'),'1')],
}


def shape_test(kind, cells, bad):
    def test(self):
        data = budget_workbook() if kind == 'budgets' else workbook_bytes()
        sheet = 1 if kind == 'budgets' else 2
        data = rewrite(data, {f'xl/worksheets/sheet{sheet}.xml': lambda x: formulas(x, cells)})
        self.exercise(kind, data, 'XML_INVALID' if bad else None)
    return test


for kind in ('budgets','funders'):
    for name, cells in BAD.items():
        setattr(FormulaPayloadUploadTests, f'test_{kind}_{name}_refused', shape_test(kind,cells,True))
    for name, cells in GOOD.items():
        setattr(FormulaPayloadUploadTests, f'test_{kind}_{name}_control', shape_test(kind,cells,False))


EXTERNAL = {
    'sheet': ("'[1]Actual 2026'!B1", None),
    'bare_name': ('[1]SyntheticName', None),
    'defined_sheet': ('SyntheticBudget', "'[1]Actual 2026'!$B$1"),
    'defined_external_name': ('SyntheticBudget', '[1]SyntheticName'),
    'defined_formula': ('SyntheticBudget', "SUM('[1]Actual 2026'!$B$1,1)"),
    'unused_defined_external': ('1+2', "'[1]Actual 2026'!$B$1"),
}
INTERNAL = {
    'defined_range': ('SyntheticBudget', "'Actual 2026'!$B$1"),
    'defined_formula': ('SyntheticBudget', "SUM('Actual 2026'!$B$1,1)"),
    'structured': ('SyntheticTable[Budget]', None),
    'nested_structured': ('SUM([[#This Row],[Budget]])', None),
    'defined_leading_equals': ('SyntheticBudget', "=SUM('Actual 2026'!$B$1,1)"),
    'local_structured': ('SUM([Budget])', None),
    'literal_brackets': ('"[1]SyntheticName"', None),
    'defined_constant': ('SyntheticBudget', '17'),
}


def dependency_test(formula, defined, bad):
    def test(self):
        self.exercise('budgets', self.external_fixture(formula, defined),
                      'BUDGET_EXTERNAL_REFERENCE' if bad else None)
    return test


for name, args in EXTERNAL.items():
    setattr(FormulaPayloadUploadTests, f'test_budget_external_{name}_refused', dependency_test(*args, True))
for name, args in INTERNAL.items():
    setattr(FormulaPayloadUploadTests, f'test_budget_internal_{name}_control', dependency_test(*args, False))
