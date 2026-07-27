import os
import tempfile

import pandas as pd
from django.core.management.base import CommandError
from django.test import TestCase
from django.utils import timezone

from api.management.commands.export_numeracy_2026_parquet import (
    Command,
    DEFAULT_OUT,
    REQUIRED_COLUMNS,
    build_quality_summary,
    build_wide_frame,
)
from api.models import AirtableSyncLog
from api.numeracy_2026 import COMPONENTS


def assessment(rid, uid, term, value=1, year=2026):
    return {
        "source_airtable_id": rid,
        "child_uid": uid,
        "year": year,
        "term": term,
        "total_raw": value * 9,
        **{component.model_field: value for component in COMPONENTS},
    }


class WideExportTests(TestCase):
    def setUp(self):
        self.roster = {
            "CH-1": {"school": "A", "mentor": "M", "numeracy_coach": "C", "grade": "PreR", "programme_status": "Yes", "programme_belonging": ["Numeracy Child"]},
            "CH-2": {"school": "B", "mentor": "N", "numeracy_coach": "D", "grade": "PreR", "programme_status": "Yes", "programme_belonging": ["Numeracy Child"]},
        }
        self.children = {
            uid: {"full_name": uid, "mcode": i, "first_name": "First", "surname": "Last", "gender": "F"}
            for i, uid in enumerate(self.roster, 1)
        }

    def test_roster_shape_null_missing_june_and_complete_flags(self):
        frame, meta = build_wide_frame(
            [assessment("rec1", "CH-1", "Jan"), assessment("off", "CH-9", "Jun")],
            self.roster,
            self.children,
        )
        self.assertEqual(set(frame.child_uid), {"CH-1", "CH-2"})
        first = frame.set_index("child_uid").loc["CH-1"]
        self.assertTrue(first["Jan - Assessment Complete"])
        self.assertFalse(first["June - Assessment Complete"])
        self.assertTrue(pd.isna(first["June - Counting Aloud"]))
        self.assertEqual(meta["off_roster_assessments"], 1)
        self.assertEqual(list(frame.columns), REQUIRED_COLUMNS)

    def test_conflicts_ranges_and_missing_uid_are_quarantined(self):
        rows = [assessment("a", "CH-1", "Jan"), assessment("b", "CH-1", "Jan"), assessment("c", None, "Jun")]
        rows[1][COMPONENTS[0].model_field] = 2
        rows[0][COMPONENTS[2].model_field] = 3
        frame, meta = build_wide_frame(rows, self.roster, self.children)
        self.assertGreater(meta["blocking_issue_count"], 0)
        self.assertIn("CONFLICTING_DUPLICATE", {i["issue_code"] for i in meta["issues"]})
        row = frame.set_index("child_uid").loc["CH-1"]
        self.assertTrue(row["Jan - Assessment Excluded"])
        self.assertFalse(row["Jan - Assessment Complete"])
        self.assertTrue(pd.isna(row["Jan - Counting Aloud"]))
        self.assertIn("CONFLICTING_DUPLICATE", row["Jan - Exclusion Reasons"])

    def test_unresolved_roster_identity_quarantines_scores_but_keeps_roster_row(self):
        children = {"CH-2": self.children["CH-2"]}
        frame, _meta = build_wide_frame(
            [assessment("rec1", "CH-1", "Jan")], self.roster, children
        )
        row = frame.set_index("child_uid").loc["CH-1"]
        self.assertFalse(row["Identity Resolved"])
        self.assertTrue(row["Jan - Assessment Excluded"])
        self.assertTrue(pd.isna(row["Jan - Total"]))

    def test_quality_summary_counts_excluded_rows_and_issue_records(self):
        rows = [assessment("a", "CH-1", "Jan"), assessment("b", "CH-1", "Jan")]
        rows[1][COMPONENTS[0].model_field] = 2
        frame, meta = build_wide_frame(rows, self.roster, self.children)
        summary = build_quality_summary(frame, meta)
        self.assertEqual(summary["roster_rows"], 2)
        self.assertEqual(summary["january_assessments_excluded"], 1)
        self.assertEqual(summary["children_with_excluded_assessments"], 1)
        self.assertEqual(summary["conflicting_duplicate_groups"], 1)

    def test_quality_summary_does_not_count_roster_issue_as_quarantined_assessment(self):
        frame, meta = build_wide_frame([], self.roster, self.children)
        meta["issues"].append(
            {
                "source_airtable_id": "roster-rec",
                "child_uid": "CH-1",
                "year": 2026,
                "term": "roster",
                "issue_code": "UNRESOLVED_ROSTER_UID",
                "component": "",
                "value": "",
                "maximum": "",
            }
        )
        summary = build_quality_summary(frame, meta)
        self.assertEqual(summary["source_records_with_issues"], 1)
        self.assertEqual(summary["assessment_records_quarantined"], 0)

    def test_default_path_targets_sibling_streamlit_repo(self):
        self.assertTrue(str(DEFAULT_OUT).endswith("Masi_Data_Site/masi_data_streamlit/data/parquet/raw/2026_numeracy_midline.parquet"))


class FreshnessGateTests(TestCase):
    def log(self, sync_type, success=True, **details):
        return AirtableSyncLog.objects.create(
            sync_type=sync_type,
            success=success,
            completed_at=timezone.now(),
            details=details,
        )

    def test_latest_failed_attempt_is_not_masked(self):
        for sync_type in Command.required_syncs:
            self.log(sync_type)
        self.log("numeracy_assessments_2026", success=False)
        with self.assertRaises(CommandError):
            Command().assert_clean_syncs()

    def test_data_quality_flags_do_not_block_publication(self):
        self.log("numeracy_assessments_2026", conflicting_duplicate_groups=1)
        self.log("numeracy_on_the_programme_2026")
        Command().assert_clean_syncs()

    def test_operational_retirement_guard_still_blocks(self):
        self.log("numeracy_assessments_2026", retire_skipped=5)
        self.log("numeracy_on_the_programme_2026")
        with self.assertRaises(CommandError):
            Command().assert_clean_syncs()
