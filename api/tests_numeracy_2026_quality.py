from django.test import SimpleTestCase

from api.numeracy_2026 import COMPONENTS, evaluate_quality


def assessment(rid, uid="CH-1", term="Jan", value=1):
    return {
        "source_airtable_id": rid,
        "child_uid": uid,
        "year": 2026,
        "term": term,
        **{component.model_field: value for component in COMPONENTS},
    }


class NumeracyQualityTests(SimpleTestCase):
    def test_word_problem_score_above_one_is_quarantined_without_clipping(self):
        bad = assessment("recA")
        word_problems = next(
            component for component in COMPONENTS if component.display_name == "Word Problems"
        )
        bad[word_problems.model_field] = 2
        winners, issues = evaluate_quality([bad])
        self.assertEqual(winners, {})
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["issue_code"], "OUT_OF_RANGE")
        self.assertEqual(issues[0]["component"], "Word Problems")
        self.assertEqual(issues[0]["maximum"], 1)
        self.assertEqual(bad[word_problems.model_field], 2)

    def test_identical_duplicates_choose_lexicographically_and_report_redundancy(self):
        winners, issues = evaluate_quality([assessment("recB"), assessment("recA")])
        self.assertEqual(winners[("CH-1", 2026, "Jan")]["source_airtable_id"], "recA")
        self.assertEqual([i["issue_code"] for i in issues], ["REDUNDANT_IDENTICAL_DUPLICATE"])

    def test_conflicting_duplicates_report_all_source_ids_and_have_no_winner(self):
        a = assessment("recA")
        b = assessment("recB")
        b[COMPONENTS[0].model_field] = 2
        winners, issues = evaluate_quality([b, a])
        self.assertNotIn(("CH-1", 2026, "Jan"), winners)
        self.assertEqual({i["source_airtable_id"] for i in issues}, {"recA", "recB"})
        self.assertTrue(all(i["issue_code"] == "CONFLICTING_DUPLICATE" for i in issues))
        self.assertTrue(all(i["component"] == COMPONENTS[0].display_name for i in issues))

    def test_out_of_range_and_missing_uid_are_blocking_without_clipping(self):
        bad = assessment("recA")
        bad[COMPONENTS[2].model_field] = 3
        missing = assessment("recB", uid=None)
        winners, issues = evaluate_quality([bad, missing])
        self.assertEqual(winners, {})
        self.assertEqual(
            {i["issue_code"] for i in issues}, {"OUT_OF_RANGE", "MISSING_CHILD_UID"}
        )
        self.assertEqual(bad[COMPONENTS[2].model_field], 3)

    def test_missing_uid_row_still_reports_its_invalid_score(self):
        bad = assessment("recA", uid=None)
        bad[COMPONENTS[2].model_field] = 3
        _winners, issues = evaluate_quality([bad])
        self.assertEqual(
            {issue["issue_code"] for issue in issues}, {"MISSING_CHILD_UID", "OUT_OF_RANGE"}
        )
