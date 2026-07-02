from django.test import TestCase
from api.models import OnTheProgramme2026
from api.management.commands.sync_airtable_on_the_programme_2026 import Command


def _record(rid, child_uid, mentor="Faith Bolothi"):
    return {"id": rid, "fields": {
        "Child UID": child_uid, "Mentor": [mentor], "2026 On The Programme": "Yes",
        "All Sessions Count v2": 31, "Valid Learning Records Count v2": 22,
        "School": "Coega Primary School", "Actual Grade": ["Grade 1"],
    }}


class SyncOnTheProgramme2026Tests(TestCase):
    def setUp(self):
        self.cmd = Command()

    def test_extract_row_unwraps_mentor_and_grade(self):
        row = self.cmd.extract_row(_record("recR1", "CH-1"))
        self.assertEqual(row["child_uid"], "CH-1")
        self.assertEqual(row["mentor"], "Faith Bolothi")
        self.assertEqual(row["grade"], "Grade 1")
        self.assertTrue(row["on_the_programme"])
        self.assertEqual(row["all_sessions_count"], 31)

    def test_extract_row_none_without_child_uid(self):
        rec = _record("recR2", "CH-9"); rec["fields"]["Child UID"] = ""
        self.assertIsNone(self.cmd.extract_row(rec))

    def test_bulk_upsert_idempotent(self):
        self.cmd.bulk_upsert([_record("recR1", "CH-1")])
        stats = self.cmd.bulk_upsert([_record("recR1", "CH-1", mentor="New Mentor")])
        self.assertEqual(OnTheProgramme2026.objects.count(), 1)
        self.assertEqual(stats["updated"], 1)
        self.assertEqual(OnTheProgramme2026.objects.get().mentor, "New Mentor")

    def test_bulk_upsert_adopts_recreated_record_same_child_uid(self):
        # R2-3: Airtable deletes recR1 and recreates as recR2 with the SAME child_uid.
        self.cmd.bulk_upsert([_record("recR1", "CH-1")])
        stats = self.cmd.bulk_upsert([_record("recR2", "CH-1", mentor="New")])  # must NOT raise IntegrityError
        self.assertEqual(OnTheProgramme2026.objects.count(), 1)
        row = OnTheProgramme2026.objects.get(child_uid="CH-1")
        self.assertEqual(row.source_airtable_id, "recR2")   # adopted the new record id
        self.assertEqual(row.mentor, "New")
        self.assertTrue(row.is_active)

    def test_bulk_upsert_skips_within_batch_duplicate_child_uid(self):
        stats = self.cmd.bulk_upsert([_record("recR1", "CH-1"), _record("recR2", "CH-1")])
        self.assertEqual(OnTheProgramme2026.objects.count(), 1)   # no unique-constraint crash
        self.assertEqual(stats["skipped"], 1)
        self.assertEqual(stats["dup_uid_skipped"], 1)             # R4: surfaced for the export fail-closed gate

    def test_bulk_upsert_retires_rows_absent_from_pull(self):
        self.cmd.bulk_upsert([_record("recR1", "CH-1"), _record("recR2", "CH-2")])
        stats = self.cmd.bulk_upsert([_record("recR1", "CH-1")], retire_floor=1)  # CH-2 left the roster
        self.assertEqual(stats["retired"], 1)
        self.assertFalse(OnTheProgramme2026.objects.get(source_airtable_id="recR2").is_active)
        self.assertEqual(OnTheProgramme2026.objects.filter(is_active=True).count(), 1)

    def test_retire_guard_skips_suspicious_short_pull(self):
        self.cmd.bulk_upsert([_record("recR1", "CH-1"), _record("recR2", "CH-2"), _record("recR3", "CH-3")])
        stats = self.cmd.bulk_upsert([_record("recR1", "CH-1")], retire_floor=1)  # 2 of 3 gone -> guard
        self.assertEqual(stats["retired"], 0)
        self.assertEqual(stats["retire_skipped"], 2)

    def test_within_batch_dup_uid_is_order_independent(self):
        # R3-5: same child_uid on two record ids -> deterministic (sorted-id) winner regardless of input order.
        a = self.cmd.bulk_upsert([_record("recR2", "CH-1", mentor="B"), _record("recR1", "CH-1", mentor="A")])
        self.assertEqual(OnTheProgramme2026.objects.get(child_uid="CH-1").source_airtable_id, "recR1")
        self.assertEqual(a["skipped"], 1)

    def test_adoption_collision_on_same_row_is_skipped_not_crashed(self):
        # An existing row (recR1/CH-1); an incoming new id recRX also claims CH-1 by adoption while
        # recR1 is re-sent -> both resolve to the same row; the second is skipped, no duplicate PK.
        self.cmd.bulk_upsert([_record("recR1", "CH-1")])
        stats = self.cmd.bulk_upsert([_record("recR1", "CH-1"), _record("recRX", "CH-1")])
        self.assertEqual(OnTheProgramme2026.objects.count(), 1)
        self.assertEqual(stats["skipped"], 1)

    def test_would_retire_ignores_already_inactive_rows(self):
        self.cmd.bulk_upsert([_record("recR1", "CH-1"), _record("recR2", "CH-2")])
        self.cmd.bulk_upsert([_record("recR1", "CH-1")], retire_floor=1)   # recR2 -> inactive
        stats = self.cmd.bulk_upsert([_record("recR1", "CH-1")], retire_floor=1)
        self.assertEqual(stats["retired"], 0)
        self.assertEqual(stats["retire_skipped"], 0)
