"""Tests for the persisted grid-health report (build_grid_health) and its
read-only serve path (build_grid attaches the latest refresh's report).

The classification is the point: reach_without_identities is dominated by Zazi
schools whose sessions live in a SEPARATE backend, so those are 'expected', not a
data error -- the report must bucket them apart from genuine Masi staffing gaps.
"""
from datetime import datetime, timezone as dt_timezone

from django.test import TestCase

from api import school_programme as sp
from api.models import AirtableSyncLog

NOW = datetime(2026, 6, 22, 2, 14, tzinfo=dt_timezone.utc)


def _result():
    return {
        "year": 2026,
        "schools_processed": 282,
        "rows_created": 3,
        "rows_updated": 306,
        "integrity": {
            "unmatched_schools": ["Bright Suns", "Charlotte Educare"],
            "unmapped_titles": {"": 1},
            "site_assigned_no_school": {"Numeracy Coach": 3},
            "unknown_site_type_tokens": [],
            "reach_without_identities": [
                {"school": "Adolph Schauder", "school_uid": "SCH-00123", "programmes": ["zazi_izandi"]},
                {"school": "Bright Suns", "school_uid": "SCH-00330", "programmes": ["numeracy"]},
                {"school": "Lonely 1000", "school_uid": "SCH-1", "programmes": ["thousand_stories"]},
                {"school": "Alpha", "school_uid": "SCH-00115", "programmes": ["zazi_izandi"]},
            ],
            "unmapped_zazi_schools": ["Malukhanye ECD"],
            "unresolved_zazi_participants": 1269,
        },
        "roster": {"Assessor": 12},
    }


ROLLUP = {"children": 8145, "sites_total": 179, "schools_primary": 79, "schools_ecd": 100}


class BuildGridHealthTests(TestCase):
    def setUp(self):
        self.health = sp.build_grid_health(_result(), ROLLUP, NOW)

    def test_reach_total(self):
        self.assertEqual(self.health["reach_without_identities"]["total"], 4)

    def test_zazi_schools_bucketed_as_expected_not_attention(self):
        buckets = self.health["reach_without_identities"]["buckets"]
        self.assertEqual({e["school"] for e in buckets["zazi_sourced"]},
                         {"Adolph Schauder", "Alpha"})

    def test_masi_coach_without_sessions_bucketed_separately(self):
        buckets = self.health["reach_without_identities"]["buckets"]
        self.assertEqual([e["school"] for e in buckets["masi_staffing"]], ["Bright Suns"])

    def test_manual_count_bucket(self):
        buckets = self.health["reach_without_identities"]["buckets"]
        self.assertEqual([e["school"] for e in buckets["manual_count"]], ["Lonely 1000"])

    def test_by_programme_set_sorted_by_count_then_name(self):
        sets = self.health["reach_without_identities"]["by_programme_set"]
        self.assertEqual(sets, [
            {"programmes": ["zazi_izandi"], "count": 2},
            {"programmes": ["numeracy"], "count": 1},
            {"programmes": ["thousand_stories"], "count": 1},
        ])

    def test_passthrough_flags_and_meta(self):
        self.assertEqual(self.health["schools_missing_uid"], ["Bright Suns", "Charlotte Educare"])
        self.assertEqual(self.health["unresolved_zazi_participants"], 1269)
        self.assertEqual(self.health["unmapped_zazi_schools"], ["Malukhanye ECD"])
        self.assertEqual(self.health["off_grid_roster"], {"Assessor": 12})
        self.assertEqual(self.health["year"], 2026)
        self.assertEqual(self.health["summary"]["rows_updated"], 306)
        self.assertEqual(self.health["rollup"], ROLLUP)
        self.assertEqual(self.health["as_of"], sp._iso(NOW))


class GridHealthServeTests(TestCase):
    def test_build_grid_health_is_none_with_no_refresh(self):
        self.assertIsNone(sp.build_grid(2026)["health"])

    def test_build_grid_serves_latest_successful_report(self):
        AirtableSyncLog.objects.create(
            sync_type="school_programme_grid", success=True, details={"as_of": "old"})
        AirtableSyncLog.objects.create(
            sync_type="school_programme_grid", success=True, details={"as_of": "new"})
        self.assertEqual(sp.build_grid(2026)["health"], {"as_of": "new"})

    def test_failed_refresh_is_ignored(self):
        AirtableSyncLog.objects.create(
            sync_type="school_programme_grid", success=False, details={"as_of": "failed"})
        self.assertIsNone(sp.build_grid(2026)["health"])
