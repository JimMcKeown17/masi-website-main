"""Tests for sync_airtable_youth -- specifically that an Airtable computed/formula
field returning the {'specialValue': 'NaN'} sentinel (Age derived from a blank or
invalid DOB) does NOT crash the sync.

The bug (2026-06-22): Age is an Airtable formula field. When DOB is blank/invalid
the API returns {'specialValue': 'NaN'} (a truthy dict) instead of a number; it was
passed straight to Youth.age (an IntegerField) and exploded at bulk_create time
with "Field 'age' expected a number but got {'specialValue': 'NaN'}".
"""
from django.test import TestCase

from api.models import Youth
from api.management.commands.sync_airtable_youth import Command, _coerce_int


def _record(emp_id, age, airtable_id="rec1"):
    return {"id": airtable_id, "fields": {
        "Employee ID": emp_id, "Full Name": "Test Youth", "Age": age,
    }}


class CoerceIntTests(TestCase):
    def test_passes_real_numbers(self):
        self.assertEqual(_coerce_int(30), 30)
        self.assertEqual(_coerce_int(30.0), 30)
        self.assertEqual(_coerce_int("30"), 30)

    def test_special_value_nan_dict_becomes_none(self):
        self.assertIsNone(_coerce_int({"specialValue": "NaN"}))
        self.assertIsNone(_coerce_int({"specialValue": "Infinity"}))

    def test_nan_and_inf_strings_become_none(self):
        self.assertIsNone(_coerce_int("NaN"))
        self.assertIsNone(_coerce_int(float("inf")))

    def test_blank_and_junk_become_none(self):
        self.assertIsNone(_coerce_int(None))
        self.assertIsNone(_coerce_int(""))
        self.assertIsNone(_coerce_int("not a number"))


class SyncYouthNanAgeTests(TestCase):
    def setUp(self):
        self.cmd = Command()

    def test_nan_age_does_not_crash_sync(self):
        # The exact production failure: one record with a specialValue NaN age.
        stats = self.cmd.bulk_upsert(
            [_record(101, {"specialValue": "NaN"})], school_map={}, mentor_map={})
        self.assertEqual(stats["created"], 1)
        youth = Youth.objects.get(employee_id=101)
        self.assertIsNone(youth.age)  # coerced, not crashed

    def test_nan_age_is_reported_for_followup(self):
        # A NaN age means a bad DOB in Airtable -- surface the employee_id so
        # staff can fix the source, rather than silently nulling it.
        stats = self.cmd.bulk_upsert(
            [_record(101, {"specialValue": "NaN"})], school_map={}, mentor_map={})
        self.assertEqual(stats["age_unparseable_ids"], [101])

    def test_genuinely_blank_age_is_not_reported_as_bad(self):
        stats = self.cmd.bulk_upsert(
            [_record(102, None)], school_map={}, mentor_map={})
        self.assertEqual(stats["age_unparseable_ids"], [])
        self.assertIsNone(Youth.objects.get(employee_id=102).age)

    def test_valid_age_is_stored(self):
        stats = self.cmd.bulk_upsert(
            [_record(103, 27)], school_map={}, mentor_map={})
        self.assertEqual(Youth.objects.get(employee_id=103).age, 27)
        self.assertEqual(stats["age_unparseable_ids"], [])


class BuildSchoolMapTests(TestCase):
    """The school FK map must prefer canonical School rows over legacy duplicates.

    The bug (2026-07-27): School has legacy duplicate rows (same name, but
    is_active=False and no school_uid). The old dict comprehension let whichever
    row the unordered queryset yielded last win, so youth were attached to dead
    rows the grid never reads -- Lingelethu showed 0/8 in post while 7 literacy
    coaches worked there.
    """

    def test_canonical_row_beats_legacy_duplicate(self):
        from api.models import School
        from api.management.commands.sync_airtable_youth import build_school_map

        canonical = School.objects.create(
            name="Lingelethu", school_uid="SCH-00322", is_active=True)
        # Legacy dup created SECOND (higher id): a naive last-wins dict would
        # pick it; the preference rank must pick the canonical row instead.
        School.objects.create(name="Lingelethu", is_active=False)

        self.assertEqual(build_school_map()["lingelethu"], canonical.id)

    def test_trailing_space_names_collapse_to_one_key(self):
        from api.models import School
        from api.management.commands.sync_airtable_youth import build_school_map

        canonical = School.objects.create(
            name="Nceduluntu Edu-care", school_uid="SCH-00293", is_active=True)
        School.objects.create(name="Nceduluntu Edu-care ", is_active=False)

        school_map = build_school_map()
        self.assertEqual(school_map["nceduluntu edu-care"], canonical.id)
        self.assertNotIn("nceduluntu edu-care ", school_map)

    def test_active_without_uid_beats_inactive_with_uid(self):
        from api.models import School
        from api.management.commands.sync_airtable_youth import build_school_map

        School.objects.create(name="Odd One", school_uid="SCH-09999", is_active=False)
        active = School.objects.create(name="Odd One", is_active=True)

        self.assertEqual(build_school_map()["odd one"], active.id)

    def test_name_existing_only_as_inactive_still_maps(self):
        # Better a legacy FK than a null one; the grid-health flag surfaces it.
        from api.models import School
        from api.management.commands.sync_airtable_youth import build_school_map

        legacy = School.objects.create(name="Old Site", is_active=False)

        self.assertEqual(build_school_map()["old site"], legacy.id)

    def test_blank_names_are_skipped(self):
        from api.models import School
        from api.management.commands.sync_airtable_youth import build_school_map

        School.objects.create(name="", is_active=True)
        School.objects.create(name="   ", is_active=True)

        self.assertEqual(build_school_map(), {})
