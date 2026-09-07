# api/tests_finance_snapshot.py
"""Finance snapshot: contract reader, loader command, and the role-gated endpoint.

The golden fixture in api/test_data/ is the same file masi-finance's
publisher reproduces from a synthetic workbook; if it changes there it is
copied here and these tests are the first to notice a drift.
"""

import json
from datetime import date, datetime, timezone
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from api.finance_snapshot import (
    SCHEMA_PATH,
    SCHEMA_VERSION,
    FinanceSnapshotError,
    canonical_digest,
    load_snapshot_file,
    parse_date,
    parse_timestamp,
    payload_digest,
    validate_snapshot,
)
from api.models import FinanceSnapshot

FIXTURE = Path(__file__).resolve().parent / "test_data" / "finance-snapshot-example.json"
CONTRACT_SCHEMA_DIGEST = "4c87e0c550a711c20b9088ff062f4aa0fb91908d559d67992878c53e5ceb630e"
CONTRACT_FIXTURE_DIGEST = "9cd8555f04b3b0b2143b4a44f6443f64187ace6d00f06736b38be632ccffd7a7"


def fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class FinanceSnapshotContractTests(SimpleTestCase):
    def test_fixture_validates(self):
        validate_snapshot(fixture())

    def test_schema_copy_matches_the_installed_publisher(self):
        from masi_finance.publish.run_schema import load_schema
        self.assertEqual(json.loads(SCHEMA_PATH.read_text()), load_schema('finance-snapshot-1.0.0.json'))

    def test_contract_digests_pin_schema_and_fixture_without_a_sibling_checkout(self):
        # Overview section 3.25: constants shared by all three repositories.
        self.assertEqual(canonical_digest(json.loads(SCHEMA_PATH.read_text())), CONTRACT_SCHEMA_DIGEST)
        self.assertEqual(canonical_digest(fixture()), CONTRACT_FIXTURE_DIGEST)

    def test_payload_digest_mismatch_is_refused(self):
        payload = fixture()
        payload["funder_contracts"][0]["budget_total"] = "7001.00"
        with self.assertRaisesRegex(FinanceSnapshotError, "payload_sha256"):
            validate_snapshot(payload)

    def test_unknown_schema_version_is_refused(self):
        payload = fixture()
        payload["schema_version"] = "1.1.0"
        with self.assertRaisesRegex(FinanceSnapshotError, "schema_version '1.1.0'"):
            validate_snapshot(payload)

    def test_missing_field_is_refused_with_its_path(self):
        payload = fixture()
        del payload["funder_contracts"][0]["remaining"]
        with self.assertRaisesRegex(FinanceSnapshotError, "remaining"):
            validate_snapshot(payload)

    def test_json_number_where_money_string_expected_is_refused(self):
        payload = fixture()
        payload["funder_contracts"][0]["budget_total"] = 7000
        with self.assertRaisesRegex(FinanceSnapshotError, "budget_total"):
            validate_snapshot(payload)

    def test_load_snapshot_file_reads_and_validates(self):
        self.assertEqual(load_snapshot_file(FIXTURE)["schema_version"], SCHEMA_VERSION)

    def test_load_snapshot_file_refuses_missing_or_malformed_files(self):
        with TemporaryDirectory() as directory:
            missing = Path(directory) / "nope.json"
            with self.assertRaisesRegex(FinanceSnapshotError, "does not exist"):
                load_snapshot_file(missing)
            broken = Path(directory) / "broken.json"
            broken.write_text("{not json")
            with self.assertRaisesRegex(FinanceSnapshotError, "not valid JSON"):
                load_snapshot_file(broken)

    def test_timestamp_and_date_parsing(self):
        self.assertEqual(parse_timestamp("2026-09-01T12:00:00Z"), datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc))
        self.assertEqual(parse_date("2026-08-31"), date(2026, 8, 31))

# api/tests_finance_snapshot.py (append)

class FinanceSnapshotModelTests(TestCase):
    def test_one_row_per_accounting_year_with_provenance(self):
        row = FinanceSnapshot.objects.create(
            accounting_year=2026, schema_version="1.0.0", run_id="2026-09-01T12:00:00Z-0a1b2c",
            workbook_name="20260831 - Fixture Management Accounts.xlsx", workbook_date=date(2026, 8, 31),
            workbook_modified_at=datetime(2026, 9, 1, 11, 59, tzinfo=timezone.utc),
            workbook_sha256="0" * 64, payload_sha256="f" * 64,
            published_at=datetime(2026, 9, 1, 12, tzinfo=timezone.utc), payload=fixture(),
        )
        self.assertIsNotNone(row.loaded_at)
        self.assertEqual(str(row), "Finance snapshot 2026 from 20260831 - Fixture Management Accounts.xlsx (2026-09-01T12:00:00Z-0a1b2c)")
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            FinanceSnapshot.objects.create(
                accounting_year=2026, schema_version="1.0.0", run_id="x", workbook_name="y",
                workbook_date=date(2026, 8, 31), workbook_modified_at=datetime(2026, 9, 1, 11, 59, tzinfo=timezone.utc),
                workbook_sha256="1" * 64, payload_sha256="f" * 64,
                published_at=datetime(2026, 9, 1, 12, tzinfo=timezone.utc), payload={},
            )

# api/tests_finance_snapshot.py (append)

def write_snapshot(directory: Path, name: str = "finance-snapshot-test.json", **overrides) -> Path:
    payload = fixture()
    for key, value in overrides.items():
        if key in ("workbook_date", "modified_at", "sha256"):
            payload["source"][key] = value
        else:
            payload[key] = value
    if "published_at" in overrides:
        payload["run_id"] = f"{overrides['published_at']}-{payload['source']['sha256'][:6]}"
    payload["payload_sha256"] = payload_digest(payload)
    path = directory / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class LoadFinanceSnapshotCommandTests(TestCase):
    def test_every_invocation_refuses_before_io_or_database(self):
        from unittest.mock import patch
        for args, options in (([], {}), (['missing.json'], {}), (['missing.json'], {'apply':True,'force':True})):
            with self.subTest(args=args,options=options), self.assertNumQueries(0), patch('pathlib.Path.read_text',side_effect=AssertionError('input read')):
                with self.assertRaisesRegex(CommandError,'retired; use the Upload page'):
                    call_command('load_finance_snapshot',*args,**options)

# api/tests_finance_snapshot.py (append)

def _make_user(username, role):
    """Use the existing profile signal so permission tests match production."""
    user = User.objects.create_user(username=username, password="x")
    user.profile.role = role
    user.profile.save()
    return user


def _publish(year=2026, workbook_date=date(2026, 8, 31), run_id="2026-09-01T12:00:00Z-0a1b2c"):
    from api.finance_run_test_utils import actor, legacy
    from api.services.finance_runs import import_legacy_snapshots
    row = legacy(year)
    return import_legacy_snapshots(actor(f'importer_{year}'), year=year, legacy_row_id=row.pk)[0]


class FinanceSnapshotEndpointTests(TestCase):
    URL = "/api/finance/snapshot/"

    def setUp(self):
        self.client = APIClient()
        _publish()

    def _auth(self, role):
        user = _make_user(f"fin_{role.replace(' ', '_').lower()}_{User.objects.count()}", role)
        self.client.force_authenticate(user=user)
        return user

    def test_anonymous_is_rejected(self):
        self.assertIn(self.client.get(self.URL).status_code, (401, 403))

    def test_project_manager_is_forbidden(self):
        self._auth("PROJECT MANAGER")
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 403)
        self.assertIn("Finance", response.json()["detail"])

    def test_every_other_role_is_forbidden(self):
        for role in ("VIEWER", "FUNDER", "STAFF", "MENTOR", "YOUTH"):
            with self.subTest(role=role):
                self._auth(role)
                response = self.client.get(self.URL)
                self.assertEqual(response.status_code, 403)
                self.assertIn("Finance", response.json()["detail"])

    def test_user_without_profile_is_forbidden(self):
        user = User.objects.create_user(username="orphan", password="x")
        user.profile.delete()
        user = User.objects.get(pk=user.pk)
        self.client.force_authenticate(user=user)
        self.assertEqual(self.client.get(self.URL).status_code, 403)

    def test_non_admin_django_superuser_is_forbidden_without_an_explicit_grant(self):
        user = self._auth("STAFF")
        user.is_superuser = True
        user.save(update_fields=["is_superuser"])

        self.assertEqual(self.client.get(self.URL).status_code, 403)

    def test_admin_gets_the_snapshot(self):
        self._auth("ADMIN")
        response = self.client.get(self.URL + "?year=2026")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(set(body), {
            "accounting_year", "run_id", "workbook_name", "workbook_date", "workbook_modified_at",
            "workbook_sha256", "published_at", "loaded_at", "available_years", "snapshot",
        })
        self.assertEqual(body["accounting_year"], 2026)
        self.assertEqual(body["workbook_date"], "2026-08-31")
        self.assertEqual(body["available_years"], [2026])
        self.assertEqual(body["snapshot"]["funder_contracts"][0]["id"], "1f5047ecae02")
        self.assertEqual(body["snapshot"]["funder_contracts"][0]["budget_total"], "7000.00")

    def test_finance_managers_group_member_gets_the_snapshot(self):
        user = self._auth("STAFF")
        user.groups.add(Group.objects.get(name="Finance Managers"))

        response = self.client.get(self.URL + "?year=2026")

        self.assertEqual(response.status_code, 200)

    def test_year_defaults_to_the_latest_published(self):
        _publish(year=2025, run_id="2026-09-01T12:00:00Z-000000")
        self._auth("ADMIN")
        body = self.client.get(self.URL).json()
        self.assertEqual(body["accounting_year"], 2026)
        self.assertEqual(body["available_years"], [2026, 2025])
        self.assertEqual(self.client.get(self.URL + "?year=2025").json()["accounting_year"], 2025)

    def test_unpublished_year_is_404_and_bad_year_is_400(self):
        self._auth("ADMIN")
        self.assertEqual(self.client.get(self.URL + "?year=2024").status_code, 404)
        self.assertEqual(self.client.get(self.URL + "?year=abc").status_code, 400)

    def test_nothing_published_at_all_is_404(self):
        from api.models import FinanceRun
        FinanceRun.objects.all().delete()
        self._auth("ADMIN")
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 404)
        self.assertIn("No finance snapshot", response.json()["detail"])
