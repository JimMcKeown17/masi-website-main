"""Release-order and approval servability regressions from review round 1."""
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from api.finance_run_test_utils import actor, approve, candidate, golden, legacy


class DependencyReleaseTests(SimpleTestCase):
    def test_publisher_pin_is_in_deployment_requirements(self):
        requirements = (Path(__file__).resolve().parents[1] / 'requirements.txt').read_text()
        pin = 'masi-finance @ git+https://JimMcKeown17:${MASI_FINANCE_GITHUB_TOKEN}@github.com/JimMcKeown17/masi-finance-app.git@v0.2.0'
        self.assertIn(pin, requirements.splitlines(), 'Missing pinned publisher deployment dependency')

    def test_build_checks_publisher_immediately_after_install(self):
        lines = (Path(__file__).resolve().parents[1] / 'build.sh').read_text().splitlines()
        check = "python -c \"from importlib.metadata import version; from masi_finance.publish.run_artifact import build_run_artifact; assert version('masi-finance') == '0.2.0'\""
        self.assertEqual(lines[lines.index('pip install -r requirements.txt') + 1], check)


class FoundationSnapshotTests(TestCase):
    def test_legacy_endpoint_is_unchanged_before_and_after_import(self):
        from api.services.finance_runs import import_legacy_snapshots
        from api.finance_snapshot_compat import snapshot_response
        user = actor()
        row = legacy()
        client = APIClient()
        client.force_authenticate(user)
        before = client.get('/api/finance/snapshot/')
        self.assertEqual(before.status_code, 200)
        self.assertEqual(before.json()['snapshot'], row.payload)
        imported = import_legacy_snapshots(user, year=2026, legacy_row_id=row.pk)[0]
        self.assertEqual(client.get('/api/finance/snapshot/').json(), before.json())
        self.assertEqual(snapshot_response(imported, [2026]), before.json())
        # Foundation keeps serving the legacy row even if the imported run is absent.
        imported.delete()
        self.assertEqual(client.get('/api/finance/snapshot/').json(), before.json())


class ApprovalServabilityTests(TestCase):
    def test_lowercase_timestamp_approves_and_projects(self):
        from api.finance_snapshot_compat import project_snapshot
        user = actor()
        artifact = golden()
        artifact['manifest']['source']['client_modified_at'] = '2026-09-01t10:00:00z'
        run = approve(candidate(user, artifact=artifact), user)
        self.assertEqual(project_snapshot(run)['source']['modified_at'], '2026-09-01T10:00:00Z')

    def test_projection_failure_refuses_before_superseding_with_value_free_code(self):
        self._assert_projection_refusal('timestamp')

    def test_projection_schema_failure_refuses_before_superseding(self):
        self._assert_projection_refusal('schema')

    def _assert_projection_refusal(self, failure):
        user = actor()
        current = approve(candidate(user), user)
        target = candidate(user, sha='b' * 64, source_date='2026-09-01')
        before = (current.approved_at, current.approved_by_id, current.approval_note)
        client = APIClient()
        client.force_authenticate(user)
        # An unrepresentable timestamp and a failed compatibility schema both
        # must be caught by the real projection before any transition writes.
        mock = (patch('api.finance_snapshot_compat.utc_seconds', side_effect=ValueError('private source value'))
                if failure == 'timestamp' else
                patch('api.finance_snapshot_compat.load_schema', return_value={'not': {}}))
        with mock:
            response = client.post(f'/api/finance/runs/{target.pk}/approve/',
                {'acknowledge_findings': True, 'note': 'Reviewed'}, format='json')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json(), {'code': 'SNAPSHOT_PROJECTION_INVALID', 'detail': 'SNAPSHOT_PROJECTION_INVALID'})
        current.refresh_from_db()
        target.refresh_from_db()
        self.assertEqual((current.status, target.status), ('approved', 'candidate'))
        self.assertEqual((current.approved_at, current.approved_by_id, current.approval_note), before)
        self.assertIsNone(target.approved_at)
        self.assertIsNone(target.previous_approved_id)
