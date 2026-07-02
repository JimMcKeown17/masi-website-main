"""Grade normalization shared by the 2026 sync QA report and the parquet export.

`normalize_grade` alias-maps known spellings FIRST so a typo'd real grade
('Grade1', 'grade 1', 'G1') is not silently misclassified as PreR. Only genuine
non-grades (ECD centre-names, blanks) fall back to PreR. `grade_is_fallback`
reports whether a value hit that fallback, so syncs/export can count it.
"""

SKILLS = [
    "Letter Sounds", "Story Comprehension", "Listen First Sound", "Listen Words",
    "Writing Letters", "Read Words", "Read Sentences", "Read Story",
    "Write CVCs", "Write Sentences", "Write Story",
]
VALID_GRADES = {"PreR", "Grade R", "Grade 1", "Grade 2", "Grade 3"}
GRADE_ALIASES = {
    "prer": "PreR", "pre-r": "PreR", "pre r": "PreR", "grade rr": "PreR", "rr": "PreR",
    "grade r": "Grade R", "gr r": "Grade R", "r": "Grade R",
    "grade 1": "Grade 1", "grade1": "Grade 1", "gr 1": "Grade 1", "g1": "Grade 1", "1": "Grade 1",
    "grade 2": "Grade 2", "grade2": "Grade 2", "gr 2": "Grade 2", "g2": "Grade 2", "2": "Grade 2",
    "grade 3": "Grade 3", "grade3": "Grade 3", "gr 3": "Grade 3", "g3": "Grade 3", "3": "Grade 3",
}


def _key(grade):
    return " ".join(str(grade).strip().lower().split()) if grade is not None else ""


def normalize_grade(grade):
    if grade in VALID_GRADES:
        return grade
    return GRADE_ALIASES.get(_key(grade), "PreR")


def grade_is_fallback(grade):
    """True when `grade` was NOT a recognized grade and fell back to PreR."""
    return grade not in VALID_GRADES and _key(grade) not in GRADE_ALIASES
