"""Authenticated import regressions for Excel metadata and actionable subtotals."""
from urllib.parse import urlencode
from unittest.mock import patch
from xml.etree import ElementTree as ET
from django.test import TestCase
from rest_framework.test import APIClient
from api.finance_budget_test_utils import budget_workbook, budget_ledger
from api.finance_run_test_utils import actor, approve
from api.models import FinanceRun
from api.parsers.finance_workbook import MIME, NS
from api.tests_finance_upload_safety import NAME, rewrite, workbook_bytes

class ImportGuidanceTests(TestCase):
    def setUp(self):
        self.user=actor(); self.dep=budget_ledger(self.user)
        self.client=APIClient(); self.client.force_authenticate(self.user)
    def upload(self, kind, data):
        query=dict(kind=kind,year=2026,source_name=NAME)
        if kind=='budgets': query['ledger_run_id']=str(self.dep.pk)
        return self.client.post('/api/finance/runs/?'+urlencode(query),data,content_type=MIME)
    def test_excel_worksheet_phonetics_pass_both_http_imports(self):
        for kind in ('funders','budgets'):
            def metadata(xml):
                root=ET.fromstring(xml); ET.SubElement(root,NS+'phoneticPr',fontId='108',type='noConversion')
                return ET.tostring(root)
            data=budget_workbook() if kind=='budgets' else workbook_bytes()
            response=self.upload(kind,rewrite(data,{'xl/worksheets/sheet1.xml':metadata}))
            self.assertEqual(response.status_code,201)
            self.assertEqual(response.json()['status'],'candidate',response.json().get('failure'))
    def test_failed_budget_has_safe_repair_cells_and_preserves_approved_source(self):
        before=self.upload('budgets',budget_workbook(half=True))
        self.assertEqual(before.status_code,201)
        approved=approve(FinanceRun.objects.get(pk=before.json()['id']),self.user)
        def omit(xml):
            root=ET.fromstring(xml)
            for col in ('F','G','L'):
                root.find(f'.//{NS}c[@r="{col}5"]/{NS}f').text=f'SUM({col}6:{col}6)'
            return ET.tostring(root)
        data=rewrite(budget_workbook(half=True),{'xl/worksheets/sheet1.xml':omit})
        response=self.upload('budgets',data)
        self.assertEqual(response.status_code,201)
        body=response.json(); self.assertEqual(body['status'],'failed')
        self.assertEqual(body['failure']['diagnostics'],[dict(sheet='2026 Budget',cell=f'{c}5',expected_cells=[f'{c}6',f'{c}7']) for c in ('F','G','L')])
        self.assertEqual(body['allowed_actions'],[])
        failed=FinanceRun.objects.get(pk=body['id']); self.assertIsNone(failed.payload)
        self.assertFalse(failed.ledger_rows.exists())
        approved.refresh_from_db(); self.assertEqual(approved.status,'approved')
        self.assertEqual(self.client.get('/api/finance/runs/'+body['id']+'/').json()['failure'],body['failure'])
    def test_untrusted_exception_diagnostics_are_not_serialized(self):
        from masi_finance.publish.budget_run import BudgetRunError
        error=BudgetRunError('BUDGET_HIERARCHY_INVALID',diagnostics=[{'sheet':'private label','cell':'F5','expected_cells':['secret']}])
        with patch('api.services.finance_runs.build_budget_run_artifact',side_effect=error):
            response=self.upload('budgets',budget_workbook())
        self.assertEqual(response.status_code,201)
        self.assertNotIn('diagnostics',response.json()['failure'])
        self.assertNotIn('private label',response.content.decode())
