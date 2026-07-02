import pandas as pd
from django.test import TestCase
from api.management.commands.reconcile_literacy_2026 import compare, airtable_aggregates, REQUIRED_COLUMNS


class ReconcileCompareTests(TestCase):
    def _row(self, uid, jan_ls, jun_ls, on="Yes"):
        row = {c: 0 for c in REQUIRED_COLUMNS}      # full column contract present
        row.update({"child_uid": uid, "On the Programme": on,
                    "Jan - Letter Sounds": jan_ls, "June - Letter Sounds": jun_ls})
        return row

    def _parquet(self):
        return pd.DataFrame([self._row("CH-1", 10, 40), self._row("CH-2", 12, 44)])

    def test_passes_within_tolerance(self):
        stats = {"roster_count": 2, "jun_assessed_on_roster": 2, "mean_jan_letter_sounds": 11.0}
        self.assertTrue(compare(stats, self._parquet())["ok"])

    def test_fails_when_row_count_off(self):
        stats = {"roster_count": 100, "jun_assessed_on_roster": 2, "mean_jan_letter_sounds": 11.0}
        self.assertFalse(compare(stats, self._parquet())["ok"])

    def test_fails_when_mean_drifts(self):
        stats = {"roster_count": 2, "jun_assessed_on_roster": 2, "mean_jan_letter_sounds": 50.0}
        self.assertFalse(compare(stats, self._parquet())["ok"])

    def test_fails_when_off_programme_row_present(self):
        df = self._parquet(); df.loc[0, "On the Programme"] = "No"
        stats = {"roster_count": 2, "jun_assessed_on_roster": 2, "mean_jan_letter_sounds": 11.0}
        self.assertFalse(compare(stats, df)["ok"])

    def test_fails_when_required_column_missing(self):   # R4-critical
        df = self._parquet().drop(columns=["Full Name"])
        stats = {"roster_count": 2, "jun_assessed_on_roster": 2, "mean_jan_letter_sounds": 11.0}
        self.assertFalse(compare(stats, df)["ok"])

    def test_fails_when_source_or_parquet_empty(self):   # R4-critical
        empty_source = {"roster_count": 0, "jun_assessed_on_roster": 0, "mean_jan_letter_sounds": 0.0}
        self.assertFalse(compare(empty_source, self._parquet())["ok"])
        good = {"roster_count": 2, "jun_assessed_on_roster": 2, "mean_jan_letter_sounds": 11.0}
        self.assertFalse(compare(good, pd.DataFrame(columns=REQUIRED_COLUMNS))["ok"])

    def test_fails_when_roster_below_floor(self):        # R5: 1-row source that self-agrees at 1
        stats = {"roster_count": 1, "jun_assessed_on_roster": 1, "mean_jan_letter_sounds": 11.0}
        df = pd.DataFrame([self._row("CH-1", 10, 40)])
        self.assertFalse(compare(stats, df, min_roster=1000, min_jun=800)["ok"])

    def test_fails_when_first_page_only_roster(self):    # R5: single Airtable page (100) < floor
        stats = {"roster_count": 100, "jun_assessed_on_roster": 90, "mean_jan_letter_sounds": 11.0}
        df = pd.DataFrame([self._row(f"CH-{i}", 10, 40) for i in range(100)])
        self.assertFalse(compare(stats, df, min_roster=1000, min_jun=800)["ok"])

    def test_fails_when_roster_count_drifts_by_one(self):   # R6: exact equality, not 2% tolerance
        stats = {"roster_count": 3, "jun_assessed_on_roster": 2, "mean_jan_letter_sounds": 11.0}
        self.assertFalse(compare(stats, self._parquet(), min_roster=1)["ok"])   # parquet 2 != 3

    def test_fails_when_jun_count_drifts_by_one(self):      # R6: exact equality on Jun count
        stats = {"roster_count": 2, "jun_assessed_on_roster": 1, "mean_jan_letter_sounds": 11.0}
        self.assertFalse(compare(stats, self._parquet(), min_roster=1)["ok"])   # parquet jun notna 2 != 1


class AirtableAggregatesTests(TestCase):
    """Independence exercised by feeding RAW Airtable-shaped records (no sync extractor)."""
    def _a(self, uid, term, ls=10, year=2026, rid=None, dup=None):
        fields = {"Child UID": [uid], "Term": term, "Year": year, "Letter Sounds": ls}
        if dup is not None:
            fields["Duplicate?"] = dup
        return {"id": rid or f"{uid}{term}", "fields": fields}

    def _r(self, uid):
        return {"id": f"r{uid}", "fields": {"Child UID": uid}}

    def test_scopes_to_roster_and_averages_jan(self):
        stats = airtable_aggregates(
            [self._a("CH-1", "Jan", 10), self._a("CH-1", "Jun"), self._a("CH-9", "Jan", 99)],  # CH-9 off-roster
            [self._r("CH-1")])
        self.assertEqual(stats["roster_count"], 1)
        self.assertEqual(stats["jun_assessed_on_roster"], 1)
        self.assertEqual(stats["mean_jan_letter_sounds"], 10)     # off-roster CH-9 excluded

    def test_dedupes_jan_with_status_aware_policy(self):   # R4: mirrors the export's pick_winner
        # A Duplicate-flagged row is more complete (LS=99) but must LOSE to the Unique row (LS=20).
        dup = self._a("CH-1", "Jan", 99, rid="z", dup="Duplicate")
        dup["fields"]["Read Words"] = 5
        uniq = self._a("CH-1", "Jan", 20, rid="a", dup="✅ Unique")
        stats = airtable_aggregates([dup, uniq], [self._r("CH-1")])
        self.assertEqual(stats["mean_jan_letter_sounds"], 20)     # status-aware winner, not first-non-null

    def test_ignores_non_2026(self):
        stats = airtable_aggregates([self._a("CH-1", "Jan", 10, year=2025)], [self._r("CH-1")])
        self.assertEqual(stats["mean_jan_letter_sounds"], 0.0)
        self.assertEqual(stats["jun_assessed_on_roster"], 0)
