"""Exact reader projections and authenticated HTTP boundary, synthetic data only."""
from copy import deepcopy
from decimal import localcontext
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient


def sample_run():
    lines = [dict(id=f'line-{i}', parent_id=f'dept-{i}', actual_share='1/2', calc=None, wf=None,
                  calculation_inputs={'budget_assertion': {'coefficient': '12345', 'scale': 4}})
             for i in range(2)]
    return SimpleNamespace(pk='budget-id', dependency_run_id='ledger-id', accounting_year=2026,
        payload=dict(lines=lines, hierarchy=[dict(id=f'dept-{i}', label=f'Department {i}',
            parent_id=None, child_ids=[f'line-{i}'], line_ids=[f'line-{i}']) for i in range(2)],
            lines_by_bc=[dict(line_ids=['line-0', 'line-1'], ledger_actual='0.01')],
            orphan_actuals=[], summary={'year_actual': '0.01'},
            projection={'sheet_as_of': '2026-07-15', 'month_count': 7, 'calculation_precision': 80}))


class BudgetInsightsMathTests(SimpleTestCase):
    def report(self, run):
        from api.services.finance_budget_insights import budget_insights
        return budget_insights(run)

    def test_half_cent_shares_and_exact_budget_assertions_round_only_at_total(self):
        run = sample_run(); before = deepcopy(run.payload)
        with localcontext() as ctx:
            ctx.prec = 6
            report = self.report(run)
        self.assertEqual(run.payload, before)
        metrics = report['organisation']
        self.assertEqual(metrics['actual']['total'], '0.01')
        self.assertEqual(metrics['actual']['residual'], '-0.01')
        self.assertEqual(metrics['budget']['total'], '2.47')
        self.assertEqual(metrics['budget']['residual'], '0.01')
        self.assertEqual(metrics['projected']['total'], '0.02')
        self.assertEqual(metrics['variance_all']['total'], '-2.45')
        self.assertEqual(report['composition']['residual'], '-0.01')
        self.assertEqual([b['percentage'] for b in report['composition']['buckets']], ['50.000000', '50.000000'])

    def test_missing_budget_keeps_actual_composition_and_known_budget_subtotal(self):
        run = sample_run(); run.payload['lines'][0]['calculation_inputs']['budget_assertion'] = None
        report = self.report(run)
        self.assertEqual(report['organisation']['budget']['total'], None)
        self.assertEqual(report['organisation']['budget']['known_subtotal'], '1.23')
        self.assertFalse(report['organisation']['budget']['complete'])
        self.assertTrue(report['composition']['available'])

    def test_missing_actual_keeps_calc_b_projection_and_disables_pie(self):
        run = sample_run(); run.payload['lines_by_bc'] = []
        for line in run.payload['lines']: line['calc'] = 'B'
        report = self.report(run)
        self.assertEqual(report['organisation']['projected']['total'], '2.47')
        self.assertIsNone(report['organisation']['actual']['total'])
        self.assertIn('incomplete_actuals', report['composition']['reasons'])
        self.assertTrue(all(b['amount'] is None and b['percentage'] is None for b in report['composition']['buckets']))

    def test_wf_exclusion_is_known_zero_not_missing_masi_variance(self):
        run = sample_run()
        for line in run.payload['lines']: line['wf'] = 'x'
        report = self.report(run)
        self.assertEqual(report['organisation']['variance_masi']['total'], '0.00')
        self.assertTrue(report['organisation']['variance_masi']['complete'])
        self.assertEqual(report['organisation']['variance_all']['total'], '-2.45')

    def test_orphans_are_included_once_in_annual_partition(self):
        run = sample_run(); run.payload['orphan_actuals'] = [{'actual': '0.03'}, {'actual': '0.01'}]
        run.payload['summary']['year_actual'] = '0.05'
        report = self.report(run)
        self.assertEqual(report['organisation']['actual']['total'], '0.01')
        self.assertEqual(report['composition']['total'], '0.05')
        self.assertEqual(report['composition']['buckets'][-1], {'id': 'unbudgeted',
            'label': 'Unbudgeted / unmapped expenditure', 'amount': '0.04', 'percentage': '80.000000'})

    def test_zero_and_negative_partitions_keep_table_and_disable_pie(self):
        for amount, reason in [('0.00', 'zero_total'), ('-0.01', 'negative_amounts')]:
            with self.subTest(amount=amount):
                run = sample_run(); run.payload['lines_by_bc'][0]['ledger_actual'] = amount
                run.payload['summary']['year_actual'] = amount
                report = self.report(run)
                self.assertFalse(report['composition']['available'])
                self.assertIn(reason, report['composition']['reasons'])
                self.assertTrue(all(b['amount'] is not None and b['percentage'] is None for b in report['composition']['buckets']))


    def test_extreme_retained_precision_does_not_inherit_ambient_context(self):
        run = sample_run()
        run.payload['projection']['calculation_precision'] = 1200
        run.payload['lines'][0]['calculation_inputs']['budget_assertion'] = {'coefficient': '9' * 80, 'scale': 0}
        run.payload['lines'][1]['calculation_inputs']['budget_assertion'] = {'coefficient': '1', 'scale': 1000}
        with localcontext() as context:
            context.prec = 6
            result = self.report(run)
        self.assertEqual(result['organisation']['budget']['total'], '9' * 80 + '.00')
        self.assertEqual(result['organisation']['variance_all']['total'], '-' + '9' * 79 + '8.98')

    def test_incomplete_nested_parent_keeps_known_leaf_subtotal_and_mixed_wf(self):
        run = sample_run()
        run.payload['hierarchy'] = [dict(id='root', label='Root', parent_id=None,
            child_ids=['section'], line_ids=['line-0', 'line-1']), dict(id='section', label='Section',
            parent_id='root', child_ids=['line-0', 'line-1'], line_ids=['line-0', 'line-1'])]
        run.payload['lines'][0]['calculation_inputs']['budget_assertion'] = None
        run.payload['lines'][0]['wf'] = 'X'
        result = self.report(run)['organisation']
        self.assertIsNone(result['budget']['total'])
        self.assertEqual(result['budget']['known_subtotal'], '1.23')
        self.assertTrue(result['variance_masi']['complete'])
        self.assertEqual(result['variance_masi']['total'], '-1.23')


class BudgetInsightsHttpTests(TestCase):
    def setUp(self):
        from api.finance_run_test_utils import actor, approve
        from api.finance_budget_test_utils import budget_ledger, budget_workbook
        from api.services.finance_runs import upload_workbook
        from api.parsers.finance_workbook import MIME
        self.publisher = actor(); self.ledger = budget_ledger(self.publisher)
        self.run, _ = upload_workbook(BytesIO(budget_workbook(half=True)), self.publisher,
            kind='budgets', year=2026, source_name='20260907 - Synthetic.xlsx',
            content_type=MIME, ledger_run_id=self.ledger.pk)
        self.run = approve(self.run, self.publisher)
        self.reader = actor('insights-reader', role='STAFF')
        self.reader.user_permissions.add(Permission.objects.get(content_type__app_label='api',
            content_type__model='financerun', codename='read_finance'))
        self.client = APIClient(); self.client.force_authenticate(self.reader)
        self.url = f'/api/finance/runs/{self.run.pk}/'

    def test_detail_adds_report_without_mutating_payload_or_records(self):
        from api.models import FinanceRun
        original = deepcopy(self.run.payload); count = FinanceRun.objects.count()
        from api.services import finance_runs as service
        with patch.object(service, 'validate_budget_calculations', wraps=service.validate_budget_calculations) as replay:
            response = self.client.get(self.url)
        replay.assert_called_once()
        self.assertEqual(response.status_code, 200)
        report = response.data['budget_insights']
        self.assertEqual(report['version'], '1.0.0')
        self.assertEqual(report['run_id'], str(self.run.pk))
        self.assertEqual(report['ledger_run_id'], str(self.ledger.pk))
        self.assertEqual(response.data['payload'], original)
        self.run.refresh_from_db()
        self.assertEqual(self.run.payload, original)
        self.assertEqual(FinanceRun.objects.count(), count)

    def test_denied_actor_dependency_and_corruption_never_receive_insights(self):
        from api.services.finance_budget_insights import budget_insights
        with patch('api.views.finance_runs.budget_insights', wraps=budget_insights) as projection:
            self.client.force_authenticate(None)
            self.assertIn(self.client.get(self.url).status_code, (401, 403))
            self.reader.user_permissions.clear()
            self.client.force_authenticate(User.objects.get(pk=self.reader.pk))
            self.assertEqual(self.client.get(self.url).status_code, 403)
            self.client.force_authenticate(self.publisher)
            self.ledger.accounting_year = 2025; self.ledger.save(update_fields=['accounting_year'])
            self.assertEqual(self.client.get(self.url).status_code, 409)
            self.ledger.accounting_year = 2026; self.ledger.save(update_fields=['accounting_year'])
            self.run.payload['summary']['year_actual'] = '999.00'; self.run.save(update_fields=['payload'])
            self.assertEqual(self.client.get(self.url).status_code, 409)
            projection.assert_not_called()

    def test_rehashed_arithmetic_and_changed_facts_are_rejected_before_projection(self):
        from api.services.finance_budget_insights import budget_insights
        from masi_finance.publish.budget_run import budget_payload_digest
        original = deepcopy(self.run.payload)
        original_digest = self.run.payload_sha256
        with patch('api.views.finance_runs.budget_insights', wraps=budget_insights) as projection:
            self.run.payload['lines'][0]['projected'] = '12345.00'
            self.run.payload_sha256 = budget_payload_digest(dict(kind='budgets', schema_version='1.0.0',
                manifest=self.run.manifest, derived=self.run.payload))
            self.run.save(update_fields=['payload', 'payload_sha256'])
            self.assertEqual(self.client.get(self.url).status_code, 409)
            self.run.payload = original; self.run.payload_sha256 = original_digest
            self.run.save(update_fields=['payload', 'payload_sha256'])
            self.ledger.ledger_rows.update(amount='999.00')
            self.assertEqual(self.client.get(self.url).status_code, 409)
            projection.assert_not_called()
