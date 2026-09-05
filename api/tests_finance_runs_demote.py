from django.test import TestCase
from django.core.management import call_command
from django.core.management.base import CommandError
from io import StringIO
from api.finance_run_test_utils import actor, candidate, approve, legacy


class DemoteTests(TestCase):
    def setUp(self):
        from api.services import finance_runs
        self.service=finance_runs
        self.user=actor()

    def test_missing_predecessor_candidate_and_blank_note_refuse(self):
        run=candidate(self.user)
        with self.assertRaises(self.service.FinanceRunError): self.service.demote_run(run.pk,self.user,note='Restore')
        approve(run,self.user)
        with self.assertRaises(self.service.FinanceRunError): self.service.demote_run(run.pk,self.user,note='Restore')
        b=candidate(self.user,sha='b'*64,source_date='2026-09-01'); approve(b,self.user)
        with self.assertRaises(self.service.FinanceRunError): self.service.demote_run(b.pk,self.user,note='  ',override_anti_rollback=True)

    def test_first_real_run_restores_import_and_reapproves(self):
        row = legacy()
        a=self.service.import_legacy_snapshots(self.user, year=2026, legacy_row_id=row.pk)[0]
        b=candidate(self.user,sha=a.source_sha256)
        # Same source/date, different schema major: no digest rollback guard.
        approve(b,self.user)
        restored=self.service.demote_run(b.pk,self.user,note='Restore legacy',acknowledge_findings=True)
        self.assertEqual(restored.pk,a.pk)
        b.refresh_from_db()
        self.assertEqual(b.demotion_note,'Restore legacy')
        self.assertEqual(b.demoted_by,self.user)
        self.assertIsNotNone(b.demoted_at)
        approve(b,self.user)
        a.refresh_from_db(); b.refresh_from_db()
        self.assertIsNone(a.previous_approved_id)
        self.assertEqual(b.previous_approved_id,a.pk)

    def test_command_uses_same_guards_and_audit(self):
        a=candidate(self.user); approve(a,self.user)
        b=candidate(self.user,sha='b'*64,source_date='2026-09-01'); approve(b,self.user)
        options=dict(run_id=str(b.pk),actor_user_id=self.user.pk,note='Restore',stdout=StringIO())
        with self.assertRaises(CommandError): call_command('demote_finance_run',**options)
        call_command('demote_finance_run',override_anti_rollback=True,acknowledge_findings=True,**options)
        a.refresh_from_db(); b.refresh_from_db()
        self.assertEqual((a.status,b.status),('approved','superseded'))

    def test_demote_integrity_failure_is_atomic(self):
        a=candidate(self.user); approve(a,self.user)
        b=candidate(self.user,sha='b'*64,source_date='2026-09-01'); approve(b,self.user)
        type(a).objects.filter(pk=a.pk).update(payload_sha256='f'*64)
        with self.assertRaises(self.service.FinanceRunError):
            self.service.demote_run(b.pk,self.user,note='Restore',override_anti_rollback=True,acknowledge_findings=True)
        b.refresh_from_db()
        self.assertEqual(b.status,'approved')
