from django.test import TestCase
from api.models import LiteracyAssessment2026, CanonicalChild
from api.management.commands.sync_airtable_literacy_assessments_2026 import (
    Command, _uid, _num, _clean_status, _dt,
)


def _record(rid, child_uid, term, year=2026, letter_sounds=44,
            dup="✅ Unique", created="2026-06-01T10:00:00.000Z"):
    return {"id": rid, "createdTime": created, "fields": {
        "Child UID": [child_uid], "Assessment UID": f"ENR-{child_uid}-{year}",
        "Term": term, "Year": year, "Grade": "Grade 1", "Language": "IsiXhosa",
        "Letter Sounds": letter_sounds, "Total": 205,
        "Programme Belonging": ["Literacy Child"], "Duplicate?": dup,
    }}


class HelperTests(TestCase):
    def test_uid_unwraps_list(self):
        self.assertEqual(_uid(["CH-1"]), "CH-1")
        self.assertEqual(_uid("CH-2"), "CH-2")
        self.assertIsNone(_uid([]))

    def test_num_coerces(self):
        self.assertEqual(_num(44), 44.0)
        self.assertIsNone(_num(None))
        self.assertIsNone(_num({"specialValue": "NaN"}))

    def test_clean_status_strips_emoji_and_space(self):
        self.assertEqual(_clean_status("✅ Unique"), "Unique")
        self.assertEqual(_clean_status("Duplicate"), "Duplicate")
        self.assertIsNone(_clean_status(None))

    def test_dt_parses_airtable_iso(self):
        self.assertIsNotNone(_dt("2026-06-01T10:00:00.000Z"))
        self.assertIsNone(_dt(None))
        self.assertIsNone(_dt("not-a-date"))


class SyncLiteracyAssessments2026Tests(TestCase):
    def setUp(self):
        self.cmd = Command()

    def test_extract_row_maps_fields_and_unwraps_uid(self):
        row = self.cmd.extract_row(_record("recA", "CH-1", "Jun"))
        self.assertEqual(row["child_uid"], "CH-1")
        self.assertEqual(row["term"], "Jun")
        self.assertEqual(row["year"], 2026)
        self.assertEqual(row["letter_sounds"], 44.0)
        self.assertEqual(row["duplicate_status"], "Unique")   # emoji stripped
        self.assertIsNotNone(row["source_created_time"])

    def test_extract_row_returns_none_without_child_uid(self):
        rec = _record("recB", "CH-9", "Jan")
        rec["fields"]["Child UID"] = []
        self.assertIsNone(self.cmd.extract_row(rec))

    def test_bulk_upsert_creates_and_resolves_child_fk(self):
        child = CanonicalChild.objects.create(source_airtable_id="c1", child_uid="CH-1", mcode=1)
        stats = self.cmd.bulk_upsert([_record("recA", "CH-1", "Jun")], {"CH-1": child.id})
        self.assertEqual(stats["created"], 1)
        self.assertEqual(stats["orphans"], 0)
        a = LiteracyAssessment2026.objects.get(source_airtable_id="recA")
        self.assertEqual(a.child_id, child.id)
        self.assertTrue(a.is_active)
        self.assertIsNotNone(a.last_seen_at)

    def test_bulk_upsert_counts_orphans_when_child_uid_unmapped(self):
        stats = self.cmd.bulk_upsert([_record("recA", "CH-404", "Jun")], child_map={})
        self.assertEqual(stats["orphans"], 1)
        self.assertIsNone(LiteracyAssessment2026.objects.get(source_airtable_id="recA").child_id)

    def test_bulk_upsert_is_idempotent(self):
        self.cmd.bulk_upsert([_record("recA", "CH-1", "Jun")], {})
        stats = self.cmd.bulk_upsert([_record("recA", "CH-1", "Jun", letter_sounds=50)], {})
        self.assertEqual(LiteracyAssessment2026.objects.count(), 1)
        self.assertEqual(stats["updated"], 1)
        self.assertEqual(LiteracyAssessment2026.objects.get().letter_sounds, 50.0)

    def test_bulk_upsert_retires_rows_absent_from_pull(self):
        self.cmd.bulk_upsert([_record("recA", "CH-1", "Jun"), _record("recB", "CH-2", "Jun")], {})
        stats = self.cmd.bulk_upsert([_record("recA", "CH-1", "Jun")], {}, retire_floor=1)
        self.assertEqual(stats["retired"], 1)
        self.assertFalse(LiteracyAssessment2026.objects.get(source_airtable_id="recB").is_active)
        self.assertTrue(LiteracyAssessment2026.objects.get(source_airtable_id="recA").is_active)
        self.assertEqual(LiteracyAssessment2026.objects.filter(is_active=True).count(), 1)

    def test_bulk_upsert_reactivates_returning_row(self):
        self.cmd.bulk_upsert([_record("recA", "CH-1", "Jun"), _record("recB", "CH-2", "Jun")], {})
        self.cmd.bulk_upsert([_record("recA", "CH-1", "Jun")], {}, retire_floor=1)
        self.cmd.bulk_upsert([_record("recA", "CH-1", "Jun"), _record("recB", "CH-2", "Jun")], {})
        self.assertTrue(LiteracyAssessment2026.objects.get(source_airtable_id="recB").is_active)

    def test_retire_guard_skips_suspicious_short_pull(self):
        self.cmd.bulk_upsert([_record("recA", "CH-1", "Jun"),
                              _record("recB", "CH-2", "Jun"),
                              _record("recC", "CH-3", "Jun")], {})
        # A truncated pull returns only 1 of 3 rows -> would retire 2 (> floor=1, > 10%).
        stats = self.cmd.bulk_upsert([_record("recA", "CH-1", "Jun")], {}, retire_floor=1)
        self.assertEqual(stats["retired"], 0)
        self.assertEqual(stats["retire_skipped"], 2)
        self.assertTrue(LiteracyAssessment2026.objects.get(source_airtable_id="recB").is_active)

    def test_allow_retire_overrides_guard(self):
        self.cmd.bulk_upsert([_record("recA", "CH-1", "Jun"),
                              _record("recB", "CH-2", "Jun"),
                              _record("recC", "CH-3", "Jun")], {})
        stats = self.cmd.bulk_upsert([_record("recA", "CH-1", "Jun")], {}, retire_floor=1, allow_retire=True)
        self.assertEqual(stats["retired"], 2)

    def test_would_retire_ignores_already_inactive_rows(self):
        # R3: dead history must not inflate would_retire / trip the guard.
        self.cmd.bulk_upsert([_record("recA", "CH-1", "Jun"), _record("recB", "CH-2", "Jun")], {})
        self.cmd.bulk_upsert([_record("recA", "CH-1", "Jun")], {}, retire_floor=1)   # recB -> inactive
        stats = self.cmd.bulk_upsert([_record("recA", "CH-1", "Jun")], {}, retire_floor=1)
        self.assertEqual(stats["retired"], 0)        # recB already inactive, not re-counted
        self.assertEqual(stats["retire_skipped"], 0)

    def test_qa_report_counts_duplicates_and_orphans(self):
        recs = [_record("recA", "CH-1", "Jun"), _record("recB", "CH-1", "Jun")]  # same child/term = dup pair
        report = self.cmd.qa_report(recs, child_map={})
        self.assertEqual(report["total"], 2)
        self.assertEqual(report["duplicate_pairs"], 1)
        self.assertEqual(report["null_child_fk"], 2)

    def test_qa_report_same_term_different_years_is_not_a_duplicate(self):
        # The Assessments DB holds cross-year history: same child/term across
        # different years is a legitimate re-assessment, not a duplicate pair.
        recs = [_record("recA", "CH-1", "Jun", year=2025),
                _record("recB", "CH-1", "Jun", year=2026)]
        report = self.cmd.qa_report(recs, child_map={})
        self.assertEqual(report["total"], 2)
        self.assertEqual(report["duplicate_pairs"], 0)
