"""Tests for sync_airtable_schools.bulk_upsert -- specifically that it does NOT
create duplicate School rows for a school already in Postgres.

The old bug: matching incoming Airtable records ONLY by airtable_id meant a
record whose airtable_id wasn't already in PG created a NEW row, orphaning the
existing row (the source of the duplicate school rows cleaned on 2026-06-19).
The fix matches on the stable school_uid as a fallback.
"""
from django.test import TestCase

from api.models import School
from api.management.commands.sync_airtable_schools import Command


def _record(airtable_id, name, school_uid, type_="Primary"):
    return {"id": airtable_id, "fields": {
        "School": name, "School UID": school_uid, "Type": [type_],
    }}


class BulkUpsertNoDuplicatesTests(TestCase):
    def setUp(self):
        self.cmd = Command()

    def test_matches_existing_by_airtable_id(self):
        School.objects.create(airtable_id="recA", school_uid="SCH-1", name="Old Name")
        stats = self.cmd.bulk_upsert([_record("recA", "New Name", "SCH-1")])
        self.assertEqual(School.objects.count(), 1)  # updated, not duplicated
        self.assertEqual(stats["created"], 0)
        self.assertEqual(School.objects.get().name, "New Name")

    def test_matches_by_school_uid_when_airtable_id_changed(self):
        # A school already in PG under a stable school_uid, but its Airtable
        # record was re-created with a new id. Must UPDATE (attach the new
        # airtable_id), not create a duplicate.
        School.objects.create(airtable_id="recOLD", school_uid="SCH-2", name="X")
        stats = self.cmd.bulk_upsert([_record("recNEW", "X", "SCH-2")])
        self.assertEqual(School.objects.count(), 1)  # NO duplicate
        self.assertEqual(stats["created"], 0)
        self.assertEqual(stats["updated"], 1)
        self.assertEqual(School.objects.get().airtable_id, "recNEW")  # id attached

    def test_matches_by_school_uid_when_existing_row_has_no_airtable_id(self):
        # The legacy case: a CSV-imported row with a school_uid but no airtable_id.
        School.objects.create(airtable_id=None, school_uid="SCH-3", name="Legacy")
        stats = self.cmd.bulk_upsert([_record("recC", "Legacy", "SCH-3")])
        self.assertEqual(School.objects.count(), 1)  # NO duplicate
        self.assertEqual(stats["created"], 0)
        self.assertEqual(School.objects.get().airtable_id, "recC")

    def test_creates_genuinely_new_school(self):
        stats = self.cmd.bulk_upsert([_record("recZ", "Brand New", "SCH-9")])
        self.assertEqual(School.objects.count(), 1)
        self.assertEqual(stats["created"], 1)

    def test_two_records_never_target_the_same_row(self):
        # Defensive: two records that would resolve to the same existing row
        # must not both update it (one updates, the other is skipped).
        School.objects.create(airtable_id="recA", school_uid="SCH-1", name="X")
        stats = self.cmd.bulk_upsert([
            _record("recA", "First", "SCH-1"),
            _record("recB", "Second", "SCH-1"),  # same uid -> would collide
        ])
        self.assertEqual(School.objects.count(), 1)
