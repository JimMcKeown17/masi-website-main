from django.test import TestCase
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.core.management.base import CommandError
from io import StringIO
from rest_framework.test import APIClient
from api.finance_run_test_utils import actor, candidate, approve, legacy, golden


class FinanceCurrentTests(TestCase):
    def setUp(self):
        self.user=actor(); self.run=candidate(self.user)
        self.client=APIClient(); self.client.force_authenticate(self.user)

    def test_current_only_approved_and_single_kind_compatible(self):
        response=self.client.get('/api/finance/current/?year=2026')
        self.assertEqual(response.status_code,200); self.assertFalse(response.json()['compatible'])
        approve(self.run,self.user)
        data=self.client.get('/api/finance/current/?year=2026').json()
        self.assertTrue(data['compatible']); self.assertIsNone(data['compatibility_reason'])
        self.assertEqual(data['runs']['funders']['management_accounts_sha256'],self.run.source_sha256)
        self.assertEqual(self.client.get('/api/finance/current/?year=abc').status_code,400)

    def test_compatibility_equal_mismatch_missing_dependency(self):
        from api.views.finance_runs import compatibility_result
        runs={'funders':{'id':'a','management_accounts_sha256':'a'*64}}
        self.assertEqual(compatibility_result(runs),(True,None))
        runs['budget']={'id':'b','management_accounts_sha256':'a'*64}
        self.assertEqual(compatibility_result(runs),(True,None))
        runs['budget']['management_accounts_sha256']='b'*64
        good,reason=compatibility_result(runs)
        self.assertFalse(good); self.assertEqual(reason['code'],'SOURCE_MISMATCH')
        runs['budget']['management_accounts_sha256']=None
        self.assertEqual(compatibility_result(runs)[1]['code'],'DEPENDENCY_UNRESOLVED')

    def test_negative_matrix_api_service_commands_and_candidate_visibility(self):
        from api.services import finance_runs
        legacy()
        for role in ('PROJECT MANAGER','STAFF','reader'):
            user=actor(role,role if role!='reader' else 'STAFF')
            if role=='reader': user.groups.add(Group.objects.get(name='Finance Managers'))
            self.client.force_authenticate(user)
            for suffix in ('approve','demote'):
                self.assertEqual(self.client.post(f'/api/finance/runs/{self.run.pk}/{suffix}/',{'note':'x','override_anti_rollback':True,'acknowledge_findings':True},format='json').status_code,403)
            self.assertIn(self.client.get(f'/api/finance/runs/{self.run.pk}/').status_code,(403,404))
            with self.assertRaises(finance_runs.FinanceRunError): finance_runs.approve_run(self.run.pk,user)
            with self.assertRaises(finance_runs.FinanceRunError): finance_runs.demote_run(self.run.pk,user,note='x')
            with self.assertRaises(finance_runs.FinanceRunError): finance_runs.import_legacy_snapshots(user)
            for cmd,opts in (('import_legacy_finance_snapshot',{}),('demote_finance_run',{'run_id':str(self.run.pk),'note':'x'})):
                with self.assertRaises(CommandError): call_command(cmd,actor_user_id=user.pk,stdout=StringIO(),**opts)
            if role!='reader': self.assertEqual(self.client.get('/api/finance/current/?year=2026').status_code,403)

    def test_audit_unknown_fields_and_unsupported_methods_rejected(self):
        for field in ('uploaded_by','approved_by','approved_at','uploaded_at','status','manifest','payload','producer_version','approval_note','previous_approved','target_run_id'):
            response=self.client.post(f'/api/finance/runs/{self.run.pk}/approve/',{field:'spoof'},format='json')
            self.assertEqual(response.status_code,400,(field,response.data))
        for method,url in (('post','/api/finance/runs/'),('patch',f'/api/finance/runs/{self.run.pk}/'),('delete',f'/api/finance/runs/{self.run.pk}/'),('get',f'/api/finance/runs/{self.run.pk}/approve/'),('post','/api/finance/current/')):
            self.assertEqual(getattr(self.client,method)(url).status_code,405)

    def test_list_visibility_detail_and_cursor(self):
        from api.views.finance_runs import RunPagination
        from unittest.mock import patch
        b=candidate(self.user,sha='b'*64,source_date='2026-09-01')
        approve(self.run,self.user); approve(b,self.user)
        c=candidate(self.user,sha='c'*64,source_date='2026-09-02')
        with patch.object(RunPagination,'page_size',1):
            first=self.client.get('/api/finance/runs/').json()
            self.assertEqual(first['results'][0]['id'],str(c.pk)); self.assertIsNotNone(first['next'])
            second=self.client.get(first['next']).json()
            self.assertEqual(second['results'][0]['id'],str(b.pk))
        detail=self.client.get(f'/api/finance/runs/{c.pk}/').json()
        self.assertIn('manifest',detail); self.assertIn('payload',detail); self.assertIn('approve',detail['allowed_actions'])
        user=actor('reader','STAFF'); user.groups.add(Group.objects.get(name='Finance Managers')); self.client.force_authenticate(user)
        data=self.client.get('/api/finance/runs/').json()
        self.assertEqual({r['status'] for r in data['results']},{'approved','superseded'})
        self.assertEqual(self.client.get(f'/api/finance/runs/{self.run.pk}/').status_code,200)
        self.assertEqual(self.client.get(f'/api/finance/runs/{c.pk}/').status_code,404)

    def test_publish_only_does_not_gain_approved_read(self):
        user=actor('publish_only','STAFF')
        user.user_permissions.add(Permission.objects.get(codename='publish_finance',content_type__model='financerun'))
        self.client.force_authenticate(user)
        self.assertEqual(self.client.get(f'/api/finance/runs/{self.run.pk}/').status_code,200)
        approve(self.run,self.user)
        self.assertIn(self.client.get(f'/api/finance/runs/{self.run.pk}/').status_code,(403,404))
        self.assertEqual(self.client.get('/api/finance/current/?year=2026').status_code,403)

    def test_http_approval_demotion_and_publisher_wide_access(self):
        publisher = actor('another_publisher')
        self.client.force_authenticate(publisher)
        options = {'acknowledge_findings': True, 'note': 'Reviewed'}
        response = self.client.post(f'/api/finance/runs/{self.run.pk}/approve/', options, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['approved_by'], publisher.pk)
        self.assertEqual(response.json()['uploaded_by'], self.user.pk)
        next_run = candidate(self.user, sha='b' * 64, source_date='2026-09-01')
        response = self.client.post(f'/api/finance/runs/{next_run.pk}/approve/', options, format='json')
        self.assertEqual(response.status_code, 200)
        url = f'/api/finance/runs/{next_run.pk}/demote/'
        self.assertEqual(self.client.post(url, options, format='json').status_code, 409)
        response = self.client.post(url, {**options, 'override_anti_rollback': True}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['id'], str(self.run.pk))
        next_run.refresh_from_db()
        self.assertEqual(next_run.demoted_by, publisher)
        self.assertEqual(self.client.post(f'/api/finance/runs/{next_run.pk}/approve/', options, format='json').status_code, 200)

    def test_query_filters_invalid_options_and_approved_years(self):
        for query in ('year=bad', 'kind=budget', 'status=made_up', 'order=id'):
            self.assertEqual(self.client.get('/api/finance/runs/?' + query).status_code, 400)
        for body in ({'override_anti_rollback': 'false'}, {'acknowledge_findings': 1}, {'note': 3}):
            self.assertEqual(self.client.post(f'/api/finance/runs/{self.run.pk}/approve/', body, format='json').status_code, 400)
        self.assertEqual(self.client.get('/api/finance/snapshot/').status_code, 404)
        approve(self.run, self.user)
        artifact = golden()
        artifact['derived'] = {key: [] for key in artifact['derived']}
        artifact['ledger'] = {'rows': [], 'allocations': []}
        candidate(self.user, year=2027, artifact=artifact)
        data = self.client.get('/api/finance/snapshot/').json()
        self.assertEqual(data['available_years'], [2026])
        self.assertEqual(data['accounting_year'], 2026)
        self.assertEqual(self.client.get('/api/finance/snapshot/?year=2027').status_code, 404)
