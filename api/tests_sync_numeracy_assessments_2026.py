from django.test import TestCase

from api.management.commands.sync_airtable_numeracy_assessments_2026 import Command
from api.models import CanonicalChild, NumeracyAssessment2026
from api.numeracy_2026 import COMPONENTS, MAX_SCORES


def record(rid, uid="CH-1", term="Jan", **fields):
    values = {
        "Child UID": [uid] if uid else None,
        "Assessment UID": f"{uid}-2026" if uid else None,
        "Year": 2026,
        "Term": term,
        "Grade": "PreR",
        "Counting aloud": 20,
        "Number Recognition": 10,
        "Counting & Matching": 2,
        "Write Numbers": 5,
        "Identification": 3,
        "Missing Numbers": 6,
        "Missing number to 10": 1,
        "Story": 1,
        "Jan Addition & Subtraction": 7,
        "Total (162)": 55,
        "Assessment %": 33.95,
        "Programme Belonging": ["Numeracy Child"],
        "Child DB": ["recChild"],
    }
    values.update(fields)
    return {"id": rid, "createdTime": "2026-01-01T00:00:00.000Z", "fields": values}


class AssessmentMappingTests(TestCase):
    def test_component_contract_and_misleading_addition_field(self):
        self.assertEqual(sum(MAX_SCORES.values()), 161)
        self.assertEqual(len(COMPONENTS), 9)
        word_problems = next(
            component for component in COMPONENTS if component.display_name == "Word Problems"
        )
        self.assertEqual(word_problems.maximum, 1)
        row = Command().extract_row(record("recA", term="Jun"))
        self.assertEqual(row["addition_subtraction"], 7)

    def test_null_uid_is_preserved_and_counted(self):
        cmd = Command()
        raw = record("recA", uid=None)
        self.assertIsNone(cmd.extract_row(raw)["child_uid"])
        report = cmd.qa_report([raw], {})
        self.assertEqual(report["missing_child_uids"], 1)
        self.assertEqual(report["missing_h1_child_uids"], 1)

    def test_qa_counts_conflicts_and_ranges_deterministically(self):
        a = record("recB", **{"Counting & Matching": 3})
        b = record("recA", **{"Counting & Matching": 2})
        report = Command().qa_report([a, b], {"CH-1": 1})
        self.assertEqual(report["duplicate_groups"], 1)
        self.assertEqual(report["conflicting_duplicate_groups"], 1)
        self.assertEqual(report["out_of_range_by_component"], {"Counting & Matching": 1})


class AssessmentUpsertTests(TestCase):
    def test_idempotent_and_preserves_null_uid(self):
        cmd = Command()
        child = CanonicalChild.objects.create(
            source_airtable_id="recChild", child_uid="CH-1", mcode=1, full_name="Child One"
        )
        rows = [record("recA"), record("recB", uid=None)]
        first = cmd.bulk_upsert(rows, {"CH-1": child.id})
        second = cmd.bulk_upsert(rows, {"CH-1": child.id})
        self.assertEqual(first["created"], 2)
        self.assertEqual(second["updated"], 2)
        self.assertEqual(NumeracyAssessment2026.objects.count(), 2)
        self.assertTrue(NumeracyAssessment2026.objects.filter(child_uid__isnull=True).exists())

    def test_short_pull_cannot_mass_retire(self):
        for i in range(30):
            NumeracyAssessment2026.objects.create(
                source_airtable_id=f"old{i}", child_uid=f"CH-{i}", year=2026, term="Jan"
            )
        stats = Command().bulk_upsert([record("old0")], {}, retire_floor=5, retire_fraction=.1)
        self.assertEqual(stats["retired"], 0)
        self.assertEqual(stats["retire_skipped"], 29)
