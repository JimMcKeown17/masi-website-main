from django.test import TestCase
from api.views.etl_preview import TABLE_CONFIG
from api.models import LiteracyAssessment2026, OnTheProgramme2026


class EtlPreviewRegistrationTests(TestCase):
    def test_new_tables_registered(self):
        self.assertIn("literacy-assessments-2026", TABLE_CONFIG)
        self.assertIn("on-the-programme-2026", TABLE_CONFIG)
        self.assertIs(TABLE_CONFIG["literacy-assessments-2026"][0], LiteracyAssessment2026)
        self.assertEqual(TABLE_CONFIG["literacy-assessments-2026"][1], "literacy_assessments_2026")
        self.assertIs(TABLE_CONFIG["on-the-programme-2026"][0], OnTheProgramme2026)
