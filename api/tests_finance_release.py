"""Release compatibility through HTTP, without modifying historical artifacts."""
from copy import deepcopy
from io import BytesIO
from urllib.parse import urlencode
from django.test import TestCase
from django.contrib.auth.models import Group
from rest_framework.test import APIClient
from masi_finance.publish.budget_run import build_budget_run_artifact, budget_payload_digest
from api.finance_run_test_utils import actor, approve
from api.finance_budget_test_utils import budget_ledger, budget_workbook
from api.models import FinanceRun
from api.parsers.finance_workbook import MIME
from api.services import finance_runs as service


class PublisherReleaseTests(TestCase):
    def setUp(self):
        self.user = actor()
        self.ledger = budget_ledger(self.user)  # Immutable historical 0.2.0 fixture.
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.data = budget_workbook()

    def legacy_budget(self):
        a = build_budget_run_artifact(BytesIO(self.data), source_name='20260907 - Synthetic.xlsx',
            accounting_year=2026, ledger_dependency=dict(service.budget_dependency_metadata(self.ledger),accounting_year=2026),
            ledger_rows=service.reconstruct_ledger(self.ledger)['rows'])
        a['manifest']['producer']['version'] = '0.2.0'
        source = a['manifest']['source']
        findings = a['derived']['findings']
        run = FinanceRun.objects.create(kind='budgets', accounting_year=2026, status='candidate',
            source_name=source['name'], source_date=source['date'], source_sha256=source['sha256'],
            source_size_bytes=source['size_bytes'], schema_version='1.0.0', producer_version='0.2.0',
            uploaded_by=self.user, manifest=a['manifest'], payload=a['derived'],
            payload_sha256=budget_payload_digest(a), dependency_run=self.ledger,
            finding_count=len(findings), in_scope_error_count=sum(f['severity']=='error' and f['in_scope_year'] for f in findings))
        return approve(run,self.user)

    def upload(self, ledger):
        query = urlencode(dict(kind='budgets',year=2026,source_name='20260907 - Synthetic.xlsx',ledger_run_id=str(ledger.pk)))
        return self.client.post('/api/finance/runs/?'+query,self.data,content_type=MIME)

    def test_current_release_keeps_old_runs_and_creates_distinct_replayable_candidate(self):
        old = self.legacy_budget()
        before = deepcopy(self.client.get(f'/api/finance/runs/{old.pk}/').json())
        response = self.upload(self.ledger)
        self.assertEqual(response.status_code,201,response.data.get('code'))
        new = response.json()
        self.assertEqual(new['producer_version'],'0.3.1')
        self.assertNotEqual(new['id'],str(old.pk))
        self.assertEqual(new['source_sha256'],old.source_sha256)
        self.assertNotEqual(new['payload_sha256'],old.payload_sha256)
        self.assertEqual(self.upload(self.ledger).json(),new)
        self.assertEqual(self.client.get(f'/api/finance/runs/{old.pk}/').json(),before)
        path=f"/api/finance/runs/{new['id']}/approve/"
        denied=self.client.post(path,{'acknowledge_findings':True,'note':'Review'},format='json')
        self.assertEqual(denied.json()['code'],'ANTI_ROLLBACK')
        accepted=self.client.post(path,{'acknowledge_findings':True,'override_anti_rollback':True,'note':'Reviewed new producer'},format='json')
        self.assertEqual(accepted.status_code,200,accepted.data.get('code'))
        demoted=self.client.post(f"/api/finance/runs/{new['id']}/demote/",{'note':'Restore historical budget'},format='json')
        self.assertEqual(demoted.status_code,409,demoted.data.get('code'))
        self.assertEqual(demoted.json()['code'],'ANTI_ROLLBACK')
        self.assertEqual(self.client.get(f"/api/finance/runs/{new['id']}/").json()['status'],'approved')
        demoted=self.client.post(f"/api/finance/runs/{new['id']}/demote/",{'note':'Reviewed restoration of historical producer','override_anti_rollback':True,'acknowledge_findings':True},format='json')
        self.assertEqual(demoted.status_code,200,demoted.data.get('code'))
        self.assertEqual(self.client.get(f'/api/finance/runs/{old.pk}/').json()['status'],'approved')
        self.assertEqual(self.client.get(f'/api/finance/runs/{self.ledger.pk}/').status_code,200)

        from api.tests_finance_upload_safety import workbook_bytes, NAME
        query=urlencode(dict(kind='funders',year=2026,source_name=NAME))
        response=self.client.post('/api/finance/runs/?'+query,workbook_bytes(),content_type=MIME)
        self.assertEqual(response.status_code,201,response.data.get('code'))
        ledger=FinanceRun.objects.get(pk=response.json()['id'])
        self.assertEqual(ledger.producer_version,'0.3.1')
        approve(ledger,self.user,override_anti_rollback=True)
        response=self.upload(ledger)
        self.assertEqual(response.status_code,201,response.data.get('code'))
        self.assertEqual(response.json()['manifest']['dependencies'][0]['producer_version'],'0.3.1')
        self.assertEqual(self.client.get(f'/api/finance/runs/{old.pk}/').status_code,200)

    def test_finance_manager_can_read_approved_runs_but_cannot_pull_or_read_candidates(self):
        old=self.legacy_budget()
        new=self.upload(self.ledger)
        self.assertEqual(new.status_code,201)
        reader=actor('finance-manager',role='STAFF')
        reader.groups.add(Group.objects.get(name='Finance Managers'))
        self.client.force_authenticate(reader)
        self.assertEqual(self.client.get(f'/api/finance/runs/{old.pk}/').status_code,200)
        self.assertEqual(self.client.get(f'/api/finance/runs/{self.ledger.pk}/').status_code,200)
        self.assertEqual(self.client.get(f"/api/finance/runs/{new.json()['id']}/").status_code,404)
        self.assertEqual(self.client.post('/api/finance/runs/pull-budget/',{'year':2026,'ledger_run_id':str(self.ledger.pk)},format='json').status_code,403)
