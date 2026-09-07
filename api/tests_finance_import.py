from io import StringIO
from unittest.mock import patch
from django.test import TestCase
from django.core.management import call_command
from django.core.management.base import CommandError
from rest_framework.test import APIClient
from api.finance_run_test_utils import actor, candidate, legacy


class LegacyImportTests(TestCase):
    def setUp(self):
        from api.services import finance_runs
        self.service=finance_runs
        self.user=actor()
        self.row=legacy()
        self.row.refresh_from_db()
        self.client=APIClient(); self.client.force_authenticate(self.user)

    def test_import_verbatim_provenance_actor_and_replay_after_overwrite(self):
        expected=dict(accounting_year=self.row.accounting_year,run_id=self.row.run_id,workbook_name=self.row.workbook_name,
            workbook_date=self.row.workbook_date.isoformat(),workbook_modified_at=self.row.workbook_modified_at.isoformat().replace('+00:00','Z'),
            workbook_sha256=self.row.workbook_sha256,published_at=self.row.published_at.isoformat().replace('+00:00','Z'),
            loaded_at=self.row.loaded_at.isoformat(),available_years=[2026],snapshot=self.row.payload)
        result=self.service.import_legacy_snapshots(self.user, year=2026, legacy_row_id=self.row.pk)[0]
        self.assertEqual(self.client.get('/api/finance/snapshot/').json(),expected)
        self.assertEqual(result.uploaded_by,self.user); self.assertEqual(result.approved_by,self.user)
        self.assertIsNone(result.producer_version); self.assertIsNone(result.facts_sha256)
        self.assertEqual(result.payload,self.row.payload); self.assertEqual(result.payload_sha256,self.row.payload_sha256)
        self.assertEqual(result.fact_row_count,0)
        original=(result.pk,result.uploaded_at,result.approved_at)
        type(self.row).objects.filter(pk=self.row.pk).update(payload={},workbook_sha256='f'*64)
        replay=self.service.import_legacy_snapshots(self.user, year=2026, legacy_row_id=self.row.pk)[0]
        self.assertEqual((replay.pk,replay.uploaded_at,replay.approved_at),original)
        self.assertEqual(self.client.get('/api/finance/snapshot/').json(),expected)
        with self.assertNumQueries(0): self.assertEqual(replay.payload,expected['snapshot'])

    def test_existing_run_refuses_import(self):
        candidate(self.user)
        with self.assertRaisesRegex(self.service.FinanceRunError,'RUN_EXISTS'):
            self.service.import_legacy_snapshots(self.user, year=2026, legacy_row_id=self.row.pk)

    def test_invalid_provenance_digest_and_insert_failure_write_nothing(self):
        from api.models import FinanceRun
        type(self.row).objects.filter(pk=self.row.pk).update(workbook_sha256='f'*64)
        with self.assertRaises(self.service.FinanceRunError): self.service.import_legacy_snapshots(self.user, year=2026, legacy_row_id=self.row.pk)
        self.assertFalse(FinanceRun.objects.exists())
        type(self.row).objects.filter(pk=self.row.pk).update(workbook_sha256=self.row.workbook_sha256)
        with patch.object(FinanceRun.objects,'create',side_effect=RuntimeError('injected')),self.assertRaises(RuntimeError):
            self.service.import_legacy_snapshots(self.user, year=2026, legacy_row_id=self.row.pk)
        self.assertFalse(FinanceRun.objects.exists())

    def test_command_actor_required_and_active(self):
        with self.assertRaises(CommandError): call_command('import_legacy_finance_snapshot',stdout=StringIO())
        self.user.is_active=False; self.user.save()
        with self.assertRaises(CommandError): call_command('import_legacy_finance_snapshot',actor_user_id=self.user.pk,stdout=StringIO())

    def test_command_imports_and_exact_preview_writes_nothing(self):
        from api.models import FinanceRun
        options=dict(actor_user_id=self.user.pk,year=2026,legacy_row_id=self.row.pk,note='Import reviewed',stdout=StringIO())
        call_command('import_legacy_finance_snapshot',**options)
        self.assertFalse(FinanceRun.objects.exists())
        call_command('import_legacy_finance_snapshot',apply=True,**options)
        self.assertEqual(FinanceRun.objects.get().approval_note,'Import reviewed')

    def test_snapshot_view_never_reads_legacy_table(self):
        self.service.import_legacy_snapshots(self.user, year=2026, legacy_row_id=self.row.pk)
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        with CaptureQueriesContext(connection) as queries:
            self.assertEqual(self.client.get('/api/finance/snapshot/').status_code,200)
            self.assertEqual(self.client.get('/api/finance/current/?year=2026').status_code,200)
        self.assertFalse(any('api_financesnapshot' in q['sql'].lower() for q in queries))

    def test_exact_replay_never_queries_legacy_even_after_row_deletion(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        imported = self.service.import_legacy_snapshots(self.user, year=2026, legacy_row_id=self.row.pk)[0]
        row_id = self.row.pk
        self.row.delete()
        with CaptureQueriesContext(connection) as queries:
            replay = self.service.import_legacy_snapshots(self.user, year=2026, legacy_row_id=row_id)[0]
        self.assertEqual(replay.pk, imported.pk)
        self.assertFalse(any('api_financesnapshot' in q['sql'].lower() for q in queries))

    def test_exact_target_and_year_required_and_mismatch_refused(self):
        for kwargs in ({}, {'year': 2026}, {'year': 2025, 'legacy_row_id': self.row.pk},
                       {'year': 2026, 'legacy_row_id': self.row.pk + 1},
                       {'year': 2026, 'legacy_row_id': self.row.pk, 'note': ' '}):
            with self.subTest(kwargs=kwargs), self.assertRaises(self.service.FinanceRunError):
                self.service.import_legacy_snapshots(self.user, **kwargs)
        self.service.import_legacy_snapshots(self.user, year=2026, legacy_row_id=self.row.pk)
        with self.assertRaisesRegex(self.service.FinanceRunError, 'IMPORT_TARGET_MISMATCH'):
            self.service.import_legacy_snapshots(self.user, year=2025, legacy_row_id=self.row.pk)

    def test_every_existing_status_refuses_import(self):
        from api.finance_run_test_utils import approve
        from api.models import FinanceRun
        run = candidate(self.user)
        for status in ('candidate', 'approved', 'superseded', 'failed'):
            if status == 'approved':
                run = approve(run, self.user)
            elif status == 'superseded':
                FinanceRun.objects.filter(pk=run.pk).update(status='superseded')
            elif status == 'failed':
                run.ledger_rows.all().delete()
                FinanceRun.objects.filter(pk=run.pk).update(status='failed', approved_by=None, approved_at=None,
                    payload=None, payload_sha256=None, facts_sha256=None, fact_row_count=0, allocation_count=0,
                    failure={'code': 'INVALID', 'phase': 'parse', 'message': 'Invalid'})
            with self.subTest(status=status), self.assertRaisesRegex(self.service.FinanceRunError, 'RUN_EXISTS'):
                self.service.import_legacy_snapshots(self.user, year=2026, legacy_row_id=self.row.pk)

    def test_stale_pre_wp2_loader_cannot_change_serving_or_recovery(self):
        import importlib.util
        import json
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from api.finance_run_test_utils import approve
        from api.finance_snapshot import payload_digest
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        path = Path(__file__).parent / 'tests_data/legacy_load_finance_snapshot.py'
        spec = importlib.util.spec_from_file_location('stale_finance_loader', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        imported = self.service.import_legacy_snapshots(self.user, year=2026, legacy_row_id=self.row.pk)[0]
        expected = self.client.get('/api/finance/snapshot/').json()
        replacement = dict(self.row.payload)
        replacement['source'] = {**replacement['source'], 'sha256': 'f' * 64}
        replacement['payload_sha256'] = payload_digest(replacement)
        with TemporaryDirectory(dir='venv') as directory:
            changed = Path(directory) / 'changed.json'
            changed.write_text(json.dumps(replacement))
            module.Command(stdout=StringIO()).handle(path=str(changed), apply=True, force=True)
        self.row.refresh_from_db()
        self.assertEqual(self.row.workbook_sha256, 'f' * 64)
        self.assertEqual(self.client.get('/api/finance/snapshot/').json(), expected)
        run = candidate(self.user, sha=imported.source_sha256)
        with CaptureQueriesContext(connection) as queries:
            approve(run, self.user)
            self.assertEqual(self.client.get('/api/finance/snapshot/').json()['snapshot']['schema_version'], '1.1.0')
            restored = self.service.demote_run(run.pk, self.user, note='Restore approved import', acknowledge_findings=True)
            self.assertEqual(restored.pk, imported.pk)
            self.assertEqual(self.client.get('/api/finance/snapshot/').json(), expected)
            self.assertEqual(self.client.get('/api/finance/current/?year=2026').json()['runs']['funders']['id'], str(imported.pk))
        self.assertFalse(any('api_financesnapshot' in q['sql'].lower() for q in queries))
