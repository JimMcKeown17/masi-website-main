from django.db import IntegrityError
from django.test import TestCase
from api.models import LiteracyAssessment2026


class LiteracyAssessment2026ModelTests(TestCase):
    def test_create_and_fields(self):
        a = LiteracyAssessment2026.objects.create(
            source_airtable_id="recA1", assessment_uid="ENR-CH-1-2026",
            child_uid="CH-1", year=2026, term="Jun", grade="Grade 1",
            language="IsiXhosa", letter_sounds=44, total=205,
        )
        self.assertEqual(LiteracyAssessment2026.objects.count(), 1)
        self.assertEqual(a.letter_sounds, 44)
        self.assertTrue(a.is_active)
        self.assertIsNone(a.last_seen_at)

    def test_source_airtable_id_unique(self):
        LiteracyAssessment2026.objects.create(source_airtable_id="recDup", child_uid="CH-2", year=2026, term="Jan")
        with self.assertRaises(IntegrityError):
            LiteracyAssessment2026.objects.create(source_airtable_id="recDup", child_uid="CH-3", year=2026, term="Jan")
