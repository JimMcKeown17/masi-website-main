from django.db import IntegrityError
from django.test import TestCase

from api.models import NumeracyOnTheProgramme2026


class NumeracyOnTheProgramme2026ModelTests(TestCase):
    def test_roster_fields_and_lifecycle(self):
        row = NumeracyOnTheProgramme2026.objects.create(
            source_airtable_id="recR",
            child_uid="CH-1",
            programme_status="Yes",
            programme_belonging=["Numeracy Child"],
            school="A School",
            mentor="A Mentor",
            numeracy_coach="A Coach",
            total_sessions=12,
        )
        self.assertTrue(row.is_active)
        self.assertEqual(row.numeracy_coach, "A Coach")

    def test_child_uid_is_unique(self):
        NumeracyOnTheProgramme2026.objects.create(source_airtable_id="recA", child_uid="CH-1")
        with self.assertRaises(IntegrityError):
            NumeracyOnTheProgramme2026.objects.create(source_airtable_id="recB", child_uid="CH-1")

