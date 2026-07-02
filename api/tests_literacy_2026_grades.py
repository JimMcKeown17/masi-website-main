from django.test import TestCase
from api.literacy_2026_grades import normalize_grade, grade_is_fallback


class GradeTests(TestCase):
    def test_valid_grades_pass_through(self):
        self.assertEqual(normalize_grade("Grade 2"), "Grade 2")

    def test_alias_typos_normalize_not_prer(self):
        self.assertEqual(normalize_grade("Grade1"), "Grade 1")
        self.assertEqual(normalize_grade("grade 1"), "Grade 1")
        self.assertEqual(normalize_grade("G1"), "Grade 1")
        self.assertFalse(grade_is_fallback("Grade1"))

    def test_ecd_centre_name_and_none_become_prer_and_are_fallbacks(self):
        self.assertEqual(normalize_grade("Aaron Gqadu"), "PreR")
        self.assertEqual(normalize_grade(None), "PreR")
        self.assertTrue(grade_is_fallback("Aaron Gqadu"))
        self.assertTrue(grade_is_fallback(None))
