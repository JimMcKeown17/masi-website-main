import pandas as pd
from django.test import SimpleTestCase

from api.management.commands.export_numeracy_2026_parquet import REQUIRED_COLUMNS
from api.management.commands.reconcile_numeracy_2026 import (
    aggregate_rows,
    compare_reconciliation,
    golden_trace,
)
from api.numeracy_2026 import COMPONENTS


class ReconcileTests(SimpleTestCase):
    def frame(self):
        row = {column: None for column in REQUIRED_COLUMNS}
        row.update({"child_uid": "CH-1", "Jan - Assessment Complete": True, "June - Assessment Complete": False})
        for component in COMPONENTS:
            row[f"Jan - {component.display_name}"] = 1
        return pd.DataFrame([row])

    def stats(self):
        return {
            "assessment_rows": 2,
            "jan_rows": 1,
            "june_rows": 1,
            "roster_count": 1,
            "roster_uids": {"CH-1"},
            "jan_unique_uids": 1,
            "june_unique_uids": 1,
            "matched_complete": 0,
            "canonical_resolved": 1,
            "component_stats": {
                f"Jan - {component.display_name}": {"count": 1, "mean": 1.0}
                for component in COMPONENTS
            },
        }

    def test_exact_structure_and_float_tolerance_pass(self):
        result = compare_reconciliation(self.stats(), self.stats(), self.frame(), min_roster=1)
        self.assertTrue(result["ok"], result)

    def test_roster_uid_or_count_drift_fails(self):
        postgres = self.stats()
        postgres["roster_uids"] = {"CH-2"}
        result = compare_reconciliation(self.stats(), postgres, self.frame(), min_roster=1)
        self.assertFalse(result["ok"])

    def test_first_page_floor_and_missing_column_fail(self):
        frame = self.frame().drop(columns=["Full Name"])
        result = compare_reconciliation(self.stats(), self.stats(), frame, min_roster=100)
        self.assertFalse(result["ok"])

    def test_golden_trace_compares_every_component_and_total(self):
        source = {
            "source_airtable_id": "recA",
            "child_uid": "CH-1",
            "year": 2026,
            "term": "Jan",
            "total_raw": 9,
            **{component.model_field: 1 for component in COMPONENTS},
        }
        frame = self.frame()
        frame.loc[0, "Jan - Total"] = 9
        self.assertTrue(golden_trace("CH-1", [source], [source.copy()], frame)["ok"])
        frame.loc[0, "Jan - Counting Aloud"] = 2
        self.assertFalse(golden_trace("CH-1", [source], [source.copy()], frame)["ok"])

    def test_aggregate_excludes_assessments_without_canonical_identity(self):
        source = {
            "source_airtable_id": "recA",
            "child_uid": "CH-1",
            "year": 2026,
            "term": "Jan",
            "total_raw": 9,
            **{component.model_field: 1 for component in COMPONENTS},
        }
        result = aggregate_rows([source], {"CH-1"}, set())
        self.assertEqual(result["component_stats"]["Jan - Counting Aloud"]["count"], 0)
