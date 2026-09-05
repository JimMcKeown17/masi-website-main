from copy import deepcopy
from decimal import Decimal
from django.test import TestCase
from django.db import IntegrityError, transaction
from api.finance_run_test_utils import actor, candidate, golden
from masi_finance.publish.run_artifact import facts_digest


class FactsTests(TestCase):
    def setUp(self):
        from api.services import finance_runs
        self.service=finance_runs
        self.user=actor()

    def test_golden_counts_order_digest_and_attribution(self):
        run=candidate(self.user)
        ledger=self.service.reconstruct_ledger(run)
        self.assertEqual(ledger,golden()['ledger'])
        self.assertEqual((run.fact_row_count,run.allocation_count),(len(ledger['rows']),len(ledger['allocations'])))
        self.assertEqual(facts_digest(ledger),run.facts_sha256)
        cases={(a['contract_code'] is not None,a['budget_line_id'] is not None) for a in ledger['allocations']}
        self.assertEqual(cases,{(True,True),(True,False),(False,False)})
        self.assertTrue(all(isinstance(r['coverage_amount'],str) for r in ledger['rows']))

    def test_duplicate_row_and_stream_constraints(self):
        run=candidate(self.user)
        row=run.ledger_rows.first()
        row.pk=None
        with self.assertRaises(IntegrityError),transaction.atomic(): row.save()
        allocation=run.ledger_rows.first().allocations.first()
        allocation.pk=None
        with self.assertRaises(IntegrityError),transaction.atomic(): allocation.save()

    def test_nonzero_and_owned_line_constraints(self):
        run=candidate(self.user)
        allocation=run.ledger_rows.first().allocations.first()
        for change in ({'amount':Decimal(0)},{'ordinal':0},{'contract_code':None,'budget_line_id':'line'}):
            with self.assertRaises(IntegrityError),transaction.atomic():
                type(allocation).objects.filter(pk=allocation.pk).update(**change)

    def test_bad_attribution_rolls_back_all_inserts(self):
        run=candidate(self.user,facts=False)
        artifact=golden()
        artifact['ledger']['allocations'][0]['contract_code']=None
        with self.assertRaises(self.service.FinanceRunError):
            self.service.materialise_facts(run,artifact)
        self.assertFalse(run.ledger_rows.exists())

    def test_insert_failure_rolls_back_rows(self):
        from unittest.mock import patch
        from api.models import LedgerAllocation
        run=candidate(self.user,facts=False)
        with patch.object(LedgerAllocation.objects,'bulk_create',side_effect=RuntimeError('injected')), self.assertRaises(RuntimeError):
            self.service.materialise_facts(run,golden())
        self.assertFalse(run.ledger_rows.exists())

    def test_materialisation_refuses_failed_and_existing_facts(self):
        run=candidate(self.user)
        with self.assertRaises(self.service.FinanceRunError): self.service.materialise_facts(run,golden())
        run.status='failed'
        with self.assertRaises(self.service.FinanceRunError): self.service.materialise_facts(run,golden())

    def test_rehashed_bad_line_unbound_and_coverage_totals_still_refuse(self):
        from masi_finance.publish.run_artifact import payload_digest
        for mutate in ('line', 'unbound', 'coverage'):
            artifact = golden()
            if mutate == 'line':
                artifact['ledger']['allocations'][0]['amount'] = '1.00'
            elif mutate == 'unbound':
                owned = next(a for a in artifact['ledger']['allocations'] if a['contract_code'] and a['budget_line_id'] is None)
                owned['contract_code'] = None
            else:
                next(r for r in artifact['ledger']['rows'] if r['year'] == artifact['manifest']['accounting_year'])['coverage_amount'] = '1.00'
            run = candidate(self.user, facts=False, artifact=artifact, sha={'line':'a','unbound':'b','coverage':'c'}[mutate]*64)
            artifact['manifest'] = run.manifest
            self.assertEqual(run.payload_sha256, payload_digest(artifact))
            with self.subTest(mutate=mutate), self.assertRaises(self.service.FinanceRunError):
                self.service.materialise_facts(run, artifact)
            self.assertFalse(run.ledger_rows.exists())

    def test_valid_empty_ledger_is_verified_and_approvable(self):
        from api.finance_run_test_utils import approve
        artifact = golden()
        artifact['derived'] = {key: [] for key in artifact['derived']}
        artifact['ledger'] = {'rows': [], 'allocations': []}
        run = candidate(self.user, artifact=artifact)
        self.assertEqual(self.service.reconstruct_ledger(run), artifact['ledger'])
        self.assertEqual(approve(run, self.user).status, 'approved')

    def test_golden_artifact_matches_installed_resource_bytes(self):
        from importlib import resources
        from pathlib import Path
        installed = resources.files('masi_finance.publish').joinpath('schema', 'fixture-finance-run-2.0.0.json').read_bytes()
        self.assertEqual((Path(__file__).parent / 'tests_data/finance-run-2.0.0.json').read_bytes(), installed)
