from django.test import TestCase
from api.models import OnTheProgramme2026


class OnTheProgramme2026ModelTests(TestCase):
    def test_create_and_unique_child_uid(self):
        OnTheProgramme2026.objects.create(
            source_airtable_id="recR1", child_uid="CH-1", on_the_programme=True,
            mentor="Faith Bolothi", school="Coega Primary School", grade="Grade 1",
            all_sessions_count=31,
        )
        r = OnTheProgramme2026.objects.get(child_uid="CH-1")
        self.assertEqual(r.mentor, "Faith Bolothi")
        self.assertTrue(r.is_active)
