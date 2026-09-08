"""Release-order and approval servability regressions from review round 1."""
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from api.finance_run_test_utils import actor, approve, candidate, golden, legacy


class DependencyReleaseTests(SimpleTestCase):
    def test_publisher_pin_is_in_deployment_requirements(self):
        requirements = (Path(__file__).resolve().parents[1] / 'requirements.txt').read_text()
        pin = 'masi-finance @ git+https://JimMcKeown17:${MASI_FINANCE_GITHUB_TOKEN}@github.com/JimMcKeown17/masi-finance-app.git@v0.3.0'
        self.assertIn(pin, requirements.splitlines(), 'Missing pinned publisher deployment dependency')

    def test_build_checks_publisher_immediately_after_install(self):
        lines = (Path(__file__).resolve().parents[1] / 'build.sh').read_text().splitlines()
        check = ("python -c \"from importlib.metadata import version; "
                 "from masi_finance.publish.run_schema import verify_installed_contracts; "
                 "assert version('masi-finance') == '0.3.0'; print(verify_installed_contracts())\"")
        install = lines.index('pip install -r requirements.txt')
        self.assertEqual(lines[install + 1], check)
        self.assertLess(install + 1, lines.index('python manage.py migrate'), 'contract check must precede migrate')

    def test_installed_contract_verifier_fails_closed_before_migrate(self):
        """Plan 3.2: the release build verifies packaged schemas and fixtures, not just an import."""
        import subprocess
        import sys
        from unittest import mock
        from masi_finance.publish import run_schema
        digests = run_schema.verify_installed_contracts()
        self.assertEqual(set(digests), {'finance-run-2.0.0.json', 'finance-snapshot-1.0.0.json', 'finance-snapshot-1.1.0.json', 'budget-run-1.0.0.json'})
        altered = {name: dict(value, schema_sha256='0' * 64) for name, value in run_schema.RESOURCE_DIGESTS.items()}
        with mock.patch.dict(run_schema.RESOURCE_DIGESTS, altered, clear=True):
            with self.assertRaises(ValueError) as caught:
                run_schema.verify_installed_contracts()
        self.assertEqual(str(caught.exception), 'CONTRACT_RESOURCE_DIGEST_MISMATCH')
        lines = (Path(__file__).resolve().parents[1] / 'build.sh').read_text().splitlines()
        check_line = lines[lines.index('pip install -r requirements.txt') + 1]
        command = check_line[len('python -c "'):-1]
        result = subprocess.run([sys.executable, '-c', command], capture_output=True, text=True, timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('finance-run-2.0.0.json', result.stdout)


class CutoverSnapshotTests(TestCase):
    def test_legacy_only_rows_do_not_serve_and_imported_endpoint_has_parity(self):
        from api.services.finance_runs import import_legacy_snapshots
        from api.finance_snapshot_compat import snapshot_response
        user = actor()
        row = legacy()
        client = APIClient()
        client.force_authenticate(user)
        self.assertEqual(client.get('/api/finance/snapshot/').status_code, 404)
        imported = import_legacy_snapshots(user, year=2026, legacy_row_id=row.pk)[0]
        expected = snapshot_response(imported, [2026])
        response = client.get('/api/finance/snapshot/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected)
        row.delete()
        self.assertEqual(client.get('/api/finance/snapshot/').json(), expected)


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


class CutoverTimestampTests(TestCase):
    def test_lowercase_timestamp_approve_then_snapshot_get_200(self):
        user = actor()
        artifact = golden()
        artifact['manifest']['source']['client_modified_at'] = '2026-09-01t10:00:00z'
        run = candidate(user, artifact=artifact)
        client = APIClient()
        client.force_authenticate(user)
        response = client.post(f'/api/finance/runs/{run.pk}/approve/',
            {'acknowledge_findings': True, 'note': 'Reviewed'}, format='json')
        self.assertEqual(response.status_code, 200)
        client.raise_request_exception = False
        response = client.get('/api/finance/snapshot/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['snapshot']['source']['modified_at'], '2026-09-01T10:00:00Z')
