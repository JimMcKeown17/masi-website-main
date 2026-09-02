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
# Restored in Task 2 when the model lands.
# from api.models import FinanceSnapshot

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
