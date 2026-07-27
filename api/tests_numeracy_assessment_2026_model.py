from django.db import IntegrityError
from django.test import TestCase

from api.models import NumeracyAssessment2026


class NumeracyAssessment2026ModelTests(TestCase):
    def test_preserves_null_uid_and_raw_scores(self):
        row = NumeracyAssessment2026.objects.create(
            source_airtable_id="recA",
            assessment_uid="CH-1-2026",
            child_uid=None,
            year=2026,
            term="Jan",
            counting_aloud=42,
            addition_subtraction=7,
            total_raw=99,
        )
        self.assertIsNone(row.child_uid)
        self.assertEqual(row.addition_subtraction, 7)
        self.assertTrue(row.is_active)

    def test_source_id_is_unique_but_business_group_is_not(self):
        common = dict(child_uid="CH-1", year=2026, term="Jun")
        NumeracyAssessment2026.objects.create(source_airtable_id="recA", **common)
        NumeracyAssessment2026.objects.create(source_airtable_id="recB", **common)
        self.assertEqual(NumeracyAssessment2026.objects.count(), 2)
        with self.assertRaises(IntegrityError):
            NumeracyAssessment2026.objects.create(source_airtable_id="recA", **common)

