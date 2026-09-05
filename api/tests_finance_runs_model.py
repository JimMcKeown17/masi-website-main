from unittest import skipUnless
from django.test import TestCase
from django.db import IntegrityError, transaction, connection
from django.db.models.deletion import ProtectedError
from api.finance_run_test_utils import actor, candidate, approve


class FinanceRunModelTests(TestCase):
    def setUp(self):
        self.user = actor()
        self.run = candidate(self.user)

    def reject(self, **changes):
        with self.assertRaises(IntegrityError), transaction.atomic():
            type(self.run).objects.filter(pk=self.run.pk).update(**changes)

    def test_success_requires_payload_and_digests(self):
        for field in ('payload', 'payload_sha256', 'facts_sha256'):
            with self.subTest(field=field):
                self.reject(**{field: None})

    def test_status_kind_and_year_are_closed(self):
        for changes in ({'status':'other'}, {'kind':'budget'}, {'accounting_year':0}):
            self.reject(**changes)

    def test_failed_requires_failure_and_zero_facts(self):
        self.reject(status='failed')
        self.reject(failure={'code':'oops'})

    def test_approval_audit_is_paired_and_required(self):
        self.reject(approved_by=self.user)
        self.reject(status='approved')
        self.reject(status='superseded')

    def test_upload_identity(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            candidate(self.user)
    @skipUnless(connection.vendor == "postgresql", "Requires PostgreSQL conditional unique constraint release evidence.")
    def test_partial_unique_current(self):
        approve(self.run, self.user)
        other = candidate(self.user, sha='b'*64)
        with self.assertRaises(IntegrityError), transaction.atomic():
            type(other).objects.filter(pk=other.pk).update(status='approved', approved_by=self.user, approved_at=self.run.uploaded_at)

    def test_actor_and_predecessor_are_protected(self):
        approve(self.run, self.user)
        other = candidate(self.user, sha='b'*64, source_date='2026-09-01')
        approve(other, self.user)
        with self.assertRaises(ProtectedError):
            self.run.delete()
        with self.assertRaises(ProtectedError):
            self.user.delete()

    def test_legacy_cannot_be_a_candidate_or_have_producer(self):
        self.reject(schema_version='1.0.0', facts_sha256=None, fact_row_count=0, allocation_count=0)
