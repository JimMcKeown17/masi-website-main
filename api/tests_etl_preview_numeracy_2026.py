from django.test import TestCase

from api.views.etl_preview import TABLE_CONFIG, _numeracy_assessment_quality_stats, _numeracy_roster_quality_stats


class NumeracyEtlPreviewTests(TestCase):
    def test_tables_registered(self):
        self.assertIn("numeracy-assessments-2026", TABLE_CONFIG)
        self.assertIn("numeracy-on-the-programme-2026", TABLE_CONFIG)

    def test_empty_stats_are_aggregate_only(self):
        assessment = _numeracy_assessment_quality_stats()
        roster = _numeracy_roster_quality_stats()
        self.assertEqual(assessment["active_rows"], 0)
        self.assertEqual(roster["active_rows"], 0)
        self.assertNotIn("sample_rows", assessment)
