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

from django.contrib.auth.models import User
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
MASI_FINANCE_SCHEMA = Path("/Users/jimmckeown/Development/masi-finance/src/publish/schema/finance-snapshot-1.0.0.json")
CONTRACT_SCHEMA_DIGEST = "4c87e0c550a711c20b9088ff062f4aa0fb91908d559d67992878c53e5ceb630e"
CONTRACT_FIXTURE_DIGEST = "9cd8555f04b3b0b2143b4a44f6443f64187ace6d00f06736b38be632ccffd7a7"


def fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class FinanceSnapshotContractTests(SimpleTestCase):
    def test_fixture_validates(self):
        validate_snapshot(fixture())

    def test_schema_copy_matches_the_publisher_when_available(self):
        if not MASI_FINANCE_SCHEMA.is_file():
            self.skipTest("masi-finance checkout not present")
        self.assertEqual(
            json.loads(SCHEMA_PATH.read_text()),
            json.loads(MASI_FINANCE_SCHEMA.read_text()),
            "api/contracts/finance-snapshot-1.0.0.json drifted from masi-finance",
        )

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
    def setUp(self):
        self.temporary_directory = TemporaryDirectory()
        self.directory = Path(self.temporary_directory.name)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _run(self, path, **options):
        out = StringIO()
        call_command("load_finance_snapshot", str(path), stdout=out, **options)
        return out.getvalue()

    def test_dry_run_prints_provenance_and_writes_nothing(self):
        rendered = self._run(write_snapshot(self.directory))
        self.assertFalse(FinanceSnapshot.objects.exists())
        self.assertIn("DRY RUN", rendered)
        self.assertIn("20260831 - Fixture Management Accounts.xlsx", rendered)
        self.assertIn("2026-09-01T12:00:00Z-0a1b2c", rendered)
        self.assertIn("accounting year 2026", rendered)
        self.assertIn("5 contracts", rendered)
        self.assertIn("no published snapshot for 2026 yet", rendered)

    def test_apply_stores_the_row_with_structured_provenance(self):
        rendered = self._run(write_snapshot(self.directory), apply=True)
        row = FinanceSnapshot.objects.get(accounting_year=2026)
        self.assertEqual(row.run_id, "2026-09-01T12:00:00Z-0a1b2c")
        self.assertEqual(row.workbook_date, date(2026, 8, 31))
        self.assertEqual(row.workbook_sha256, "0" * 64)
        self.assertEqual(row.published_at, datetime(2026, 9, 1, 12, tzinfo=timezone.utc))
        self.assertEqual(row.payload["funder_contracts"][0]["id"], "1f5047ecae02")
        self.assertIn("APPLIED", rendered)

    def test_apply_twice_is_idempotent(self):
        path = write_snapshot(self.directory)
        self._run(path, apply=True)
        self._run(path, apply=True)
        self.assertEqual(FinanceSnapshot.objects.filter(accounting_year=2026).count(), 1)

    def test_newer_workbook_restates_and_preview_shows_contract_deltas(self):
        self._run(write_snapshot(self.directory), apply=True)
        newer = fixture()
        newer["source"]["workbook_date"] = "2026-09-02"
        newer["run_id"] = "2026-09-02T12:00:00Z-ffffff"
        newer["funder_contracts"][0]["allocated_total_lifetime"] = "6000.00"
        newer["funder_contracts"][0]["allocated_total_in_year"] = "2000.00"
        newer["funder_contracts"][0]["remaining"] = "1000.00"
        newer["funder_contracts"][0]["lines"][0]["allocated_lifetime"] = "5600.00"
        newer["funder_contracts"][0]["lines"][0]["allocated_in_year"] = "1600.00"
        newer["allocation_coverage"][4]["by_contract"]["1f5047ecae02"] = "1600.00"
        newer["allocation_coverage"][4]["funded"] = "5250.00"
        newer["allocation_coverage"][4]["unfunded"] = "-300.00"
        newer["findings"][1]["amount"] = "300.00"
        newer["findings"][1]["amount_in_year"] = "300.00"
        newer["findings"][1]["message"] = "Youth: funder allocations R5,250.00 exceed spend R4,950.00 by R300.00."
        del newer["funder_contracts"][4]
        newer["findings"] = [f for f in newer["findings"] if f["contract_id"] != "892d84e8e3c4"]
        newer["payload_sha256"] = payload_digest(newer)
        path = self.directory / "newer.json"
        path.write_text(json.dumps(newer))

        rendered = self._run(path)
        self.assertIn("ALPHA-25-26", rendered)      # contract code leads the row; label when absent
        self.assertIn("Delta", rendered)
        self.assertIn("+100.00", rendered)          # lifetime delta for Alpha 2025-2026
        self.assertIn("removed", rendered)          # Delta contract gone
        self.assertIn("2026-08-31 -> 2026-09-02", rendered)

        self._run(path, apply=True)
        row = FinanceSnapshot.objects.get(accounting_year=2026)
        self.assertEqual(row.workbook_date, date(2026, 9, 2))
        self.assertEqual(len(row.payload["funder_contracts"]), 4)

    def test_older_workbook_is_refused_naming_both_dates_unless_forced(self):
        self._run(write_snapshot(self.directory), apply=True)
        older = write_snapshot(self.directory, "older.json", workbook_date="2026-08-30", run_id="2026-09-02T12:00:00Z-aaaaaa")
        with self.assertRaisesRegex(CommandError, "2026-08-30.*2026-08-31"):
            self._run(older, apply=True)
        self.assertEqual(FinanceSnapshot.objects.get(accounting_year=2026).workbook_date, date(2026, 8, 31))

        rendered = self._run(older, apply=True, force=True)
        self.assertIn("FORCED", rendered)
        self.assertEqual(FinanceSnapshot.objects.get(accounting_year=2026).workbook_date, date(2026, 8, 30))

    def test_same_workbook_date_with_a_different_hash_is_refused_however_new_it_looks(self):
        # A stale copy of a same-date workbook gets a fresh mtime and a later
        # published_at; neither says its CONTENT is newer, so the loader does
        # not guess. --force is the operator saying "this one is newer".
        self._run(write_snapshot(self.directory, modified_at="2026-09-01T11:59:00Z", sha256="a" * 64), apply=True)
        stale = write_snapshot(self.directory, "stale.json", modified_at="2026-09-02T09:00:00Z", sha256="b" * 64,
                               published_at="2026-09-02T10:00:00Z")
        with self.assertRaisesRegex(CommandError, "same workbook date 2026-08-31.*different sha256.*bbbbbbbbbbbb.*aaaaaaaaaaaa"):
            self._run(stale, apply=True)
        self.assertEqual(FinanceSnapshot.objects.get(accounting_year=2026).workbook_sha256, "a" * 64)
        self._run(stale, apply=True, force=True)
        self.assertEqual(FinanceSnapshot.objects.get(accounting_year=2026).workbook_sha256, "b" * 64)

    def test_same_workbook_but_different_figures_is_refused(self):
        self._run(write_snapshot(self.directory, sha256="a" * 64), apply=True)
        edited = fixture()
        edited["source"]["sha256"] = "a" * 64
        edited["funder_contracts"][0]["budget_total"] = "7001.00"
        edited["funder_contracts"][0]["remaining"] = "1101.00"
        edited["payload_sha256"] = payload_digest(edited)   # schema-valid, self-consistent, different figures
        path = self.directory / "edited.json"
        path.write_text(json.dumps(edited))
        with self.assertRaisesRegex(CommandError, "same workbook.*figures differ"):
            self._run(path, apply=True)
        self.assertEqual(FinanceSnapshot.objects.get(accounting_year=2026).payload["funder_contracts"][0]["budget_total"], "7000.00")
        self._run(path, apply=True, force=True)
        self.assertEqual(FinanceSnapshot.objects.get(accounting_year=2026).payload["funder_contracts"][0]["budget_total"], "7001.00")

    def test_same_workbook_date_and_hash_restates_idempotently(self):
        self._run(write_snapshot(self.directory, sha256="a" * 64), apply=True)
        same = write_snapshot(self.directory, "same.json", sha256="a" * 64, published_at="2026-09-02T10:00:00Z",
                              run_id="2026-09-02T10:00:00Z-aaaaaa")
        self._run(same, apply=True)
        row = FinanceSnapshot.objects.get(accounting_year=2026)
        self.assertEqual((row.workbook_sha256, row.run_id), ("a" * 64, "2026-09-02T10:00:00Z-aaaaaa"))

    def test_dry_run_does_not_need_force_to_preview_an_older_workbook(self):
        self._run(write_snapshot(self.directory), apply=True)
        older = write_snapshot(self.directory, "older.json", workbook_date="2026-08-30")
        rendered = self._run(older)
        self.assertIn("would be refused", rendered)

    def test_unknown_schema_version_is_a_command_error(self):
        path = write_snapshot(self.directory, schema_version="2.0.0")
        with self.assertRaisesRegex(CommandError, "schema_version"):
            self._run(path)

    def test_missing_file_is_a_command_error(self):
        with self.assertRaisesRegex(CommandError, "does not exist"):
            self._run(self.directory / "missing.json")

# api/tests_finance_snapshot.py (append)

def _make_user(username, role):
    """Use the existing profile signal so permission tests match production."""
    user = User.objects.create_user(username=username, password="x")
    user.profile.role = role
    user.profile.save()
    return user


def _publish(year=2026, workbook_date=date(2026, 8, 31), run_id="2026-09-01T12:00:00Z-0a1b2c"):
    payload = fixture()
    payload["accounting_year"] = year
    return FinanceSnapshot.objects.create(
        accounting_year=year, schema_version="1.0.0", run_id=run_id,
        workbook_name="20260831 - Fixture Management Accounts.xlsx", workbook_date=workbook_date,
        workbook_modified_at=datetime(2026, 9, 1, 11, 59, tzinfo=timezone.utc),
        workbook_sha256="0" * 64, payload_sha256=payload["payload_sha256"],
        published_at=datetime(2026, 9, 1, 12, tzinfo=timezone.utc), payload=payload,
    )


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
        FinanceSnapshot.objects.all().delete()
        self._auth("ADMIN")
        response = self.client.get(self.URL)
        self.assertEqual(response.status_code, 404)
        self.assertIn("No finance snapshot", response.json()["detail"])
