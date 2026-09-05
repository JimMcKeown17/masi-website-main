from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest import skipUnless
from unittest.mock import patch
from django.db import connection, connections, transaction
from django.test import TransactionTestCase
from api.finance_run_test_utils import actor, candidate, approve, legacy


@skipUnless(connection.vendor == "postgresql", "Requires PostgreSQL advisory locks and separate connections.")
class FinanceConcurrencyTests(TransactionTestCase):
    def setUp(self):
        from api.services import finance_runs
        self.service=finance_runs
        self.user=actor()

    def worker(self, fn):
        connections.close_all()
        try: return fn()
        finally: connections.close_all()

    def test_two_concurrent_approvals_one_wins_one_refuses(self):
        a=candidate(self.user); b=candidate(self.user,sha='b'*64)
        locked=Event(); release=Event()
        def checkpoint(stage):
            if stage=='after_lock':
                locked.set()
                if not release.wait(10): raise RuntimeError('thread timeout')
        with ThreadPoolExecutor(2) as pool, patch.object(self.service,'_transition_checkpoint',side_effect=checkpoint):
            first=pool.submit(self.worker,lambda: approve(a,self.user))
            try:
                self.assertTrue(locked.wait(10))
                second=pool.submit(self.worker,lambda: approve(b,self.user))
                with self.assertRaisesRegex(self.service.FinanceRunError,'UPLOAD_IN_PROGRESS'): second.result(10)
            finally: release.set()
            first.result(10)
        a.refresh_from_db(); b.refresh_from_db()
        self.assertEqual((a.status,b.status),('approved','candidate'))

    def test_different_tuples_do_not_share_lock(self):
        with transaction.atomic():
            self.service.acquire_tuple_lock('funders',2026)
            def other():
                with transaction.atomic(): self.service.acquire_tuple_lock('funders',2025)
                return True
            with ThreadPoolExecutor(1) as pool:
                self.assertTrue(pool.submit(self.worker,other).result(10))

    def test_import_uses_same_lock_and_replays_after_release(self):
        row = legacy()
        with transaction.atomic():
            self.service.acquire_tuple_lock('funders',2026)
            with ThreadPoolExecutor(1) as pool:
                with self.assertRaisesRegex(self.service.FinanceRunError,'UPLOAD_IN_PROGRESS'):
                    pool.submit(self.worker,lambda: self.service.import_legacy_snapshots(self.user, year=2026, legacy_row_id=row.pk)).result(10)
        first=self.service.import_legacy_snapshots(self.user, year=2026, legacy_row_id=row.pk)[0]
        self.assertEqual(self.service.import_legacy_snapshots(self.user, year=2026, legacy_row_id=row.pk)[0].pk,first.pk)

    def test_transition_select_for_update_locks_existing_rows(self):
        from django.db import DatabaseError
        from api.models import FinanceRun
        run = candidate(self.user)
        locked = Event()
        release = Event()
        def checkpoint(stage):
            if stage == 'after_lock':
                locked.set()
                if not release.wait(10):
                    raise RuntimeError('thread timeout')
        def contender():
            with transaction.atomic():
                FinanceRun.objects.select_for_update(nowait=True).get(pk=run.pk)
        with ThreadPoolExecutor(2) as pool, patch.object(self.service, '_transition_checkpoint', side_effect=checkpoint):
            first = pool.submit(self.worker, lambda: approve(run, self.user))
            try:
                self.assertTrue(locked.wait(10))
                with self.assertRaises(DatabaseError):
                    pool.submit(self.worker, contender).result(10)
            finally:
                release.set()
            first.result(10)

    def test_concurrent_imports_serialize_before_first_insert(self):
        from api.models import FinanceRun
        row = legacy()
        locked = Event()
        release = Event()
        create = FinanceRun.objects.create
        def paused_create(**fields):
            locked.set()
            if not release.wait(10):
                raise RuntimeError('thread timeout')
            return create(**fields)
        def do_import():
            return self.service.import_legacy_snapshots(self.user, year=2026, legacy_row_id=row.pk)[0]
        with ThreadPoolExecutor(2) as pool, patch.object(FinanceRun.objects, 'create', side_effect=paused_create):
            first = pool.submit(self.worker, do_import)
            try:
                self.assertTrue(locked.wait(10))
                with self.assertRaisesRegex(self.service.FinanceRunError, 'UPLOAD_IN_PROGRESS'):
                    pool.submit(self.worker, do_import).result(10)
            finally:
                release.set()
            imported = first.result(10)
        self.assertEqual(do_import().pk, imported.pk)
        self.assertEqual(FinanceRun.objects.count(), 1)
