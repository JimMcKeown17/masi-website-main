import os
from datetime import datetime, timezone
import pandas as pd
from django.test import TestCase
from django.utils import timezone as dj_timezone
from django.core.management.base import CommandError
from api.models import AirtableSyncLog
from api.literacy_2026_grades import SKILLS, normalize_grade
from api.management.commands.export_literacy_2026_parquet import (
    build_wide_frame, pick_winner, dedupe, DEFAULT_OUT, REQUIRED_SYNCS, Command as ExportCmd,
)


def _t(day):
    return datetime(2026, 6, day, tzinfo=timezone.utc)


def _assessment(child_uid, term, year=2026, letter_sounds=40, total=100, dup="Unique",
                src="rec1", created=_t(1), modified=None, grade="Grade 1"):
    scores = {s: None for s in SKILLS}
    scores["Letter Sounds"] = letter_sounds
    return dict(child_uid=child_uid, year=year, term=term, grade=grade, language="IsiXhosa",
                scores=scores, total=total, duplicate_status=dup, source_airtable_id=src,
                source_created_time=created, source_modified_time=modified)


class DefaultOutPathTests(TestCase):
    def test_default_out_targets_sibling_streamlit_repo(self):
        p = str(DEFAULT_OUT)
        tail = os.path.join("Masi_Data_Site", "masi_data_streamlit", "data",
                            "parquet", "raw", "2026_literacy_midline.parquet")
        self.assertTrue(p.endswith(tail), p)
        self.assertNotIn(os.path.join("Masi_Website_2026", "Masi_Data_Site"), p)  # the R2-1 bug


class FreshnessGateTests(TestCase):
    """R3-4 / R4: the export freshness gate uses the LATEST attempt and rejects retire/dup flags."""
    def _log(self, sync_type, success, **details):
        return AirtableSyncLog.objects.create(
            sync_type=sync_type, success=success, completed_at=dj_timezone.now(), details=details)

    def test_passes_with_clean_latest_success(self):
        for st in REQUIRED_SYNCS:
            self._log(st, True)
        ExportCmd()._assert_synced()      # no raise

    def test_rejects_when_newer_sync_failed(self):   # R4: newer failure masks older success
        for st in REQUIRED_SYNCS:
            self._log(st, True)
        self._log("literacy_assessments_2026", False)
        with self.assertRaises(CommandError):
            ExportCmd()._assert_synced()

    def test_rejects_retire_or_dup_flags(self):
        self._log("literacy_assessments_2026", True, retire_skipped=5)
        self._log("on_the_programme_2026", True, dup_uid_skipped=1)
        with self.assertRaises(CommandError):
            ExportCmd()._assert_synced()


class PickWinnerTests(TestCase):
    def test_unique_beats_more_complete_duplicate(self):
        unique = _assessment("CH-1", "Jun", letter_sounds=10, dup="Unique", src="a")
        dup_full = _assessment("CH-1", "Jun", letter_sounds=99, dup="Duplicate", src="b")
        dup_full["scores"]["Read Words"] = 5   # strictly more complete
        self.assertEqual(pick_winner([dup_full, unique])["source_airtable_id"], "a")

    def test_single_beats_more_complete_duplicate(self):
        # Verified live Airtable vocabulary (Task 3 dry-run): 'Single' is the confirmed-unique
        # value ('Unique' from the plan never appears in real data). Mirrors
        # test_unique_beats_more_complete_duplicate but with dup="Single".
        single = _assessment("CH-1", "Jun", letter_sounds=10, dup="Single", src="a")
        dup_full = _assessment("CH-1", "Jun", letter_sounds=99, dup="Duplicate", src="b")
        dup_full["scores"]["Read Words"] = 5   # strictly more complete
        self.assertEqual(pick_winner([dup_full, single])["source_airtable_id"], "a")

    def test_completeness_breaks_equal_status(self):
        sparse = _assessment("CH-1", "Jun", letter_sounds=None, dup="Unique", src="a")
        full = _assessment("CH-1", "Jun", letter_sounds=40, dup="Unique", src="b")
        self.assertEqual(pick_winner([sparse, full])["source_airtable_id"], "b")

    def test_modified_time_preferred_over_created(self):
        older = _assessment("CH-1", "Jun", dup="Unique", src="a", created=_t(9), modified=_t(2))
        newer = _assessment("CH-1", "Jun", dup="Unique", src="b", created=_t(1), modified=_t(8))
        self.assertEqual(pick_winner([older, newer])["source_airtable_id"], "b")  # modified wins

    def test_recid_is_last_resort_and_flags_hard_tie(self):
        a = _assessment("CH-1", "Jun", dup="Unique", src="aaa", created=_t(1))
        b = _assessment("CH-1", "Jun", dup="Unique", src="bbb", created=_t(1))
        winners, exceptions = dedupe([a, b])
        self.assertEqual(winners[("CH-1", "Jun")]["source_airtable_id"], "aaa")
        self.assertIn(("CH-1", "Jun"), [e["key"] for e in exceptions if e["reason"] == "unresolved_tie"])


class BuildWideFrameTests(TestCase):
    def setUp(self):
        self.roster = {"CH-1": dict(mentor="Faith", school="Coega PS", grade="Grade 1", on_programme=True)}
        self.children = {"CH-1": dict(full_name="Child One", mcode=1, first_name="Child", surname="One", gender="M")}

    def test_pivots_jan_and_jun_to_wide_june_columns(self):
        asm = [_assessment("CH-1", "Jan", letter_sounds=10, src="a"),
               _assessment("CH-1", "Jun", letter_sounds=40, src="b")]
        df, meta = build_wide_frame(asm, self.roster, self.children)
        self.assertEqual(len(df), 1)
        r = df.iloc[0]
        self.assertEqual(r["Jan - Letter Sounds"], 10)
        self.assertEqual(r["June - Letter Sounds"], 40)   # 'Jun' -> 'June'
        self.assertEqual(r["School"], "Coega PS")
        self.assertEqual(r["Mentor"], "Faith")
        self.assertEqual(r["On the Programme"], "Yes")
        self.assertEqual(r["Full Name"], "Child One")
        self.assertNotIn("Nov - Letter Sounds", df.columns)
        self.assertEqual(meta["identity_coverage"], 1.0)

    def test_filters_non_2026(self):
        asm = [_assessment("CH-1", "Jun", year=2025)]
        df, _meta = build_wide_frame(asm, self.roster, self.children)
        # NaN-or-None: a lone roster row with no in-scope (2026) assessment leaves this column
        # holding a bare Python None (object dtype, pandas 2.2.3) rather than float NaN, since
        # there's no other numeric value in the column to force an upcast. pd.isna() covers both;
        # the brief's original self-inequality NaN idiom (x != x) does not catch a Python None.
        self.assertTrue(df.empty or pd.isna(df.iloc[0]["June - Letter Sounds"]))

    def test_only_roster_children_included(self):
        asm = [_assessment("CH-1", "Jun"), _assessment("CH-999", "Jun", src="z")]
        df, _meta = build_wide_frame(asm, self.roster, self.children)
        self.assertEqual(set(df["child_uid"]), {"CH-1"})

    def test_identity_coverage_drops_when_child_missing(self):
        asm = [_assessment("CH-1", "Jun")]
        df, meta = build_wide_frame(asm, self.roster, child_by_uid={})
        self.assertEqual(len(df), 1)
        self.assertIsNone(df.iloc[0]["Full Name"])
        self.assertEqual(meta["identity_coverage"], 0.0)

    def test_unassessed_roster_child_included_with_null_scores(self):
        # R3-1: the parquet is roster-shaped — a roster child with NO 2026 assessment still gets a row.
        roster = {**self.roster, "CH-2": dict(mentor="M", school="S", grade="Grade R", on_programme=True)}
        children = {**self.children, "CH-2": dict(full_name="Two", mcode=2, first_name="T", surname="Wo", gender="F")}
        asm = [_assessment("CH-1", "Jun", letter_sounds=40)]   # CH-2 unassessed
        df, meta = build_wide_frame(asm, roster, children)
        self.assertEqual(set(df["child_uid"]), {"CH-1", "CH-2"})
        ch2 = df[df["child_uid"] == "CH-2"].iloc[0]
        self.assertTrue(pd.isna(ch2["June - Letter Sounds"]))
        self.assertEqual(ch2["On the Programme"], "Yes")
        self.assertEqual(meta["identity_coverage"], 1.0)       # coverage over the full roster cohort
