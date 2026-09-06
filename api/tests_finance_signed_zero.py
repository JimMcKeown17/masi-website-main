"""D33 real-workbook persistence and value-free canonical money validation."""
from copy import deepcopy
from datetime import date
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.db import transaction
from django.test import TestCase
from openpyxl import Workbook
from masi_finance.publish.run_artifact import build_run_artifact, facts_digest, payload_digest

from api.finance_run_test_utils import actor, approve, candidate
from api.models import FinanceRun, LedgerRow, LedgerAllocation
from api.services import finance_runs as service


def negative_subcent_artifact(amount=-0.004):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Expenditure'
    sheet.append(['Date', 'Year', 'Name', 'Amount', 'Paid By', 'Category 1',
                  'Category 2', 'Category 3', 'BC', 'Allocation', 'Budget Key'])
    sheet.append([date(2026, 1, 2), 2026, 'Synthetic private name', amount,
                  'Bank', 'Programme', 'Supplies', None, None, amount, 'TEST'])
    budgets = workbook.create_sheet('Funder Budgets')
    budgets.append(['TEST', 'Synthetic funder'])
    budgets.append([None, 'Category', 'Budget', 'Spent'])
    budgets.append([None, 'Supplies', 100,
                    '=SUM(SUMIFS(Expenditure!J:J,Expenditure!G:G,B3,Expenditure!K:K,"TEST"))'])
    budgets.append([None, 'Total'])
    budgets.append([])
    budgets.append(['Budget Key', 'Funder', 'Start Date', 'End Date', 'Description'])
    budgets.append(['TEST', 'Synthetic funder', date(2026, 1, 1), date(2026, 12, 31), 'Synthetic'])
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    return build_run_artifact(stream.getvalue(), source_name='20260901 - Synthetic.xlsx', accounting_year=2026)


class SignedZeroTests(TestCase):
    def test_negative_subcent_amount_materialises_with_identical_digests(self):
        artifact = negative_subcent_artifact()
        expected_facts = facts_digest(artifact['ledger'])
        expected_payload = payload_digest(artifact)
        self.assertEqual(artifact['ledger']['rows'][0]['amount'], '0.00')
        self.assertEqual(artifact['ledger']['rows'][0]['coverage_amount'], '0.00')
        # Matching sub-cent allocation rounds to zero and is omitted by the publisher.
        self.assertEqual(artifact['ledger']['allocations'], [])
        user = actor()
        run = candidate(user, artifact=artifact, facts=False)
        service.materialise_facts(run, artifact)
        ledger = service.reconstruct_ledger(run)
        self.assertEqual(ledger, artifact['ledger'])
        self.assertEqual(facts_digest(ledger), expected_facts)
        self.assertEqual(payload_digest({**artifact, 'ledger': ledger}), expected_payload)
        self.assertEqual(approve(run, user).status, 'approved')
        run.refresh_from_db()
        self.assertEqual((run.facts_sha256, run.payload_sha256), (expected_facts, expected_payload))
        self.assertEqual(payload_digest({'derived': run.payload, 'ledger': service.reconstruct_ledger(run)}), expected_payload)
        # D21 identity still receives the raw cell, independently of D33 money.
        self.assertNotEqual(artifact['ledger']['rows'][0]['row_key'],
                            negative_subcent_artifact(0)['ledger']['rows'][0]['row_key'])

    def test_non_canonical_zero_payload_is_refused_value_free(self):
        user = actor()
        original = negative_subcent_artifact()
        paths = [('ledger', 'rows', 0, 'amount'),
                 ('ledger', 'rows', 0, 'coverage_amount'),
                 ('derived', 'allocation_coverage', 0, 'spend'),
                 ('derived', 'funder_contracts', 0, 'allocated_total_in_year'),
                 ('derived', 'funder_contracts', 0, 'lines', 0, 'allocated_in_year')]
        for path in paths:
            with self.subTest(path=path), transaction.atomic():
                artifact = deepcopy(original)
                target = artifact
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = '-0.00'
                with self.assertNoLogs(level='DEBUG'), self.assertRaises(service.FinanceRunError) as caught:
                    with transaction.atomic():
                        # Candidate fixture computes fresh digests: refusal cannot be a stale hash.
                        run = candidate(user, artifact=artifact, facts=False)
                        service.materialise_facts(run, artifact)
                self.assertEqual(str(caught.exception), 'SCHEMA_INVALID')
                self.assertEqual(caught.exception.code, 'SCHEMA_INVALID')
                self.assertEqual(caught.exception.status, 409)
                self.assertFalse(FinanceRun.objects.exists())
                self.assertFalse(LedgerRow.objects.exists())
                self.assertFalse(LedgerAllocation.objects.exists())

    def test_reconstruction_normalises_signed_decimal_zero_in_every_money_field(self):
        # Exercise sign-preserving values without depending on either DB losing the sign.
        from unittest.mock import Mock
        run = Mock()
        run.ledger_rows.order_by.return_value.values.return_value = [
            {'date': date(2026, 1, 2), 'amount': Decimal('-0.00'), 'coverage_amount': Decimal('-0.00')}]
        with patch.object(LedgerAllocation.objects, 'filter') as allocations:
            allocations.return_value.order_by.return_value.values.return_value = [
                {'ledger_row__row_key': 'synthetic', 'amount': Decimal('-0.00')}]
            ledger = service.reconstruct_ledger(run)
        self.assertEqual(ledger['rows'][0]['amount'], '0.00')
        self.assertEqual(ledger['rows'][0]['coverage_amount'], '0.00')
        self.assertEqual(ledger['allocations'][0]['amount'], '0.00')

    def test_money_pattern_refuses_noncanonical_strings(self):
        original = negative_subcent_artifact()
        user = actor()
        for value in ('00.00', '-00.01', '+0.00', '0.0', '0.000', '0.00\n'):
            with self.subTest(value=value):
                artifact = deepcopy(original)
                artifact['ledger']['rows'][0]['amount'] = value
                with self.assertRaises(service.FinanceRunError) as caught, transaction.atomic():
                    run = candidate(user, artifact=artifact, facts=False)
                    service.materialise_facts(run, artifact)
                self.assertEqual(caught.exception.code, 'SCHEMA_INVALID')
