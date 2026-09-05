from unittest.mock import patch
from django.test import TestCase
from api.finance_run_test_utils import actor, candidate, approve, golden


class ApprovalTests(TestCase):
    def setUp(self):
        from api.services import finance_runs
        self.service = finance_runs
        self.user = actor()
        self.a = candidate(self.user)

    def test_candidate_approval_records_actor(self):
        result = approve(self.a, self.user)
        self.assertEqual(result.status, 'approved')
        self.assertEqual(result.approved_by, self.user)
        self.assertIsNone(result.previous_approved_id)
        self.assertEqual(result.uploaded_by, self.user)

    def test_current_cannot_be_approved_again(self):
        approve(self.a, self.user)
        with self.assertRaisesRegex(self.service.FinanceRunError, 'INVALID_TRANSITION'):
            approve(self.a, self.user)

    def test_findings_require_acknowledgement_and_nonblank_note(self):
        for kwargs in ({}, {'acknowledge_findings':True}, {'acknowledge_findings':True, 'note':'  '}):
            with self.subTest(kwargs=kwargs), self.assertRaises(self.service.FinanceRunError):
                self.service.approve_run(self.a.pk, self.user, **kwargs)
        approve(self.a, self.user)

    def test_all_three_rollback_guards_and_override_notes(self):
        approve(self.a, self.user)
        for index, kwargs in enumerate(({'source_date':'2026-08-30'}, {}, {'same_source':True})):
            a = golden()
            if kwargs.pop('same_source', False):
                # Distinct supported producer identity is simulated below only for this guard.
                a['derived']['findings'][0]['message'] += ' reviewed'
            b = candidate(self.user, sha=str(index+1)*64, artifact=a, **kwargs)
            if index == 2:
                type(b).objects.filter(pk=b.pk).update(source_sha256=self.a.source_sha256, producer_version='0.2.1')
                b.refresh_from_db()
                b.manifest['source']['sha256'] = b.source_sha256
                b.manifest['producer']['version'] = '0.2.1'
                b.save(update_fields=['manifest'])
            with patch.dict(self.service.SUPPORTED_PAIRS, {('2.0.0','0.2.1'): '2.0.0'}):
                with self.assertRaisesRegex(self.service.FinanceRunError, 'ANTI_ROLLBACK'):
                    self.service.approve_run(b.pk, self.user, acknowledge_findings=True, note='Reviewed')
                for options in ({}, {'override_anti_rollback':True}):
                    with self.assertRaises(self.service.FinanceRunError):
                        self.service.approve_run(b.pk, self.user, acknowledge_findings=True, **options)
                approved = approve(b, self.user, override_anti_rollback=True)
                self.assertTrue(approved.approval_overrode_rollback)
                approve(self.a, self.user, override_anti_rollback=True)

    def test_digest_count_pair_and_structural_corruption_refused(self):
        for changes in ({'payload_sha256':'f'*64}, {'facts_sha256':'f'*64}, {'fact_row_count':999}, {'producer_version':'99.0.0'}, {'in_scope_error_count':0}):
            with self.subTest(changes=changes):
                old = {k:getattr(self.a,k) for k in changes}
                type(self.a).objects.filter(pk=self.a.pk).update(**changes)
                with self.assertRaises(self.service.FinanceRunError):
                    approve(self.a, self.user)
                type(self.a).objects.filter(pk=self.a.pk).update(**old)
        self.a.ledger_rows.first().delete()
        with self.assertRaises(self.service.FinanceRunError):
            approve(self.a, self.user)

    def test_failure_injection_keeps_old_current(self):
        approve(self.a, self.user)
        b = candidate(self.user, sha='b'*64, source_date='2026-09-01')
        for point in ('after_lock', 'after_supersede', 'before_promote'):
            with self.subTest(point=point):
                def fail(stage):
                    if stage == point:
                        raise RuntimeError('injected')
                with patch.object(self.service, '_transition_checkpoint', side_effect=fail), self.assertRaises(RuntimeError):
                    approve(b, self.user)
                self.a.refresh_from_db(); b.refresh_from_db()
                self.assertEqual((self.a.status,b.status), ('approved','candidate'))

    def test_reapproval_sequence_preserves_uploader_and_acyclic_chain(self):
        approve(self.a, self.user)
        b = candidate(self.user, sha='b'*64, source_date='2026-09-01')
        approve(b, self.user)
        other = actor('second')
        self.service.demote_run(b.pk, other, note='Restore', override_anti_rollback=True, acknowledge_findings=True)
        replay = type(b).objects.get(kind=b.kind, accounting_year=b.accounting_year, source_sha256=b.source_sha256, producer_version=b.producer_version)
        self.assertEqual(replay.pk,b.pk)
        result = approve(replay, other)
        self.a.refresh_from_db()
        self.assertEqual(result.previous_approved_id,self.a.pk)
        self.assertIsNone(self.a.previous_approved_id)
        self.assertEqual(result.uploaded_by,self.user)
        self.assertEqual(result.approved_by,other)

    def test_failed_and_never_approved_superseded_refuse(self):
        from api.models import FinanceRun
        failed = FinanceRun.objects.create(kind='funders', accounting_year=2025, status='failed',
            source_name='20260831 - Failed.xlsx', source_date='2026-08-31', source_sha256='f'*64,
            source_size_bytes=1, schema_version='2.0.0', producer_version='0.2.0', manifest={},
            uploaded_by=self.user, failure={'code':'BAD','phase':'parse','message':'Invalid'})
        with self.assertRaises(self.service.FinanceRunError):
            approve(failed,self.user)
        # Database rejects superseded without a previous approval as well.
        self.assertEqual(self.a.status,'candidate')

    def test_self_cross_tuple_and_existing_cycles_refuse(self):
        approve(self.a,self.user)
        b = candidate(self.user, sha='b'*64, source_date='2026-09-01')
        for target in (self.a, b):
            type(self.a).objects.filter(pk=self.a.pk).update(previous_approved=target)
            with self.assertRaises(self.service.FinanceRunError):
                approve(b,self.user)
        type(self.a).objects.filter(pk=self.a.pk).update(previous_approved=None)
        from api.finance_run_test_utils import legacy
        row=legacy(2025)
        other=self.service.import_legacy_snapshots(self.user, year=2025, legacy_row_id=row.pk)[0]
        type(self.a).objects.filter(pk=self.a.pk).update(previous_approved=other)
        with self.assertRaises(self.service.FinanceRunError):
            approve(b,self.user)
