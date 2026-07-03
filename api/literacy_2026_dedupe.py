"""Duplicate-resolution policy for 2026 literacy assessments, shared by the
parquet exporter (export_literacy_2026_parquet) and the WIG outcomes service
(wig_outcomes) so both surfaces publish identical numbers.

Rows are plain dicts (see assessment_row). Winner policy: duplicate_status
('Single'/'Unique' best, 'Duplicate' worst), then completeness, then recency,
then record id. Exceptions (unresolved ties, Duplicate-more-complete rejects)
are returned for the caller to fail closed on.
"""
from .literacy_2026_grades import SKILLS

SKILL_MODEL_FIELDS = {
    "Letter Sounds": "letter_sounds", "Story Comprehension": "story_comprehension",
    "Listen First Sound": "listen_first_sound", "Listen Words": "listen_words",
    "Writing Letters": "writing_letters", "Read Words": "read_words",
    "Read Sentences": "read_sentences", "Read Story": "read_story",
    "Write CVCs": "write_cvcs", "Write Sentences": "write_sentences",
    "Write Story": "write_story",
}


def assessment_row(a):
    """LiteracyAssessment2026 instance -> the dict shape dedupe operates on."""
    return dict(
        child_uid=a.child_uid, year=a.year, term=a.term, grade=a.grade, language=a.language,
        total=a.total, duplicate_status=a.duplicate_status, source_airtable_id=a.source_airtable_id,
        source_created_time=a.source_created_time, source_modified_time=a.source_modified_time,
        scores={skill: getattr(a, field) for skill, field in SKILL_MODEL_FIELDS.items()},
    )


def _status_rank(a):
    # Verified live vocabulary (Task 3 dry-run): 'Single'/'Duplicate'/'Not June 2026'.
    # 'Single' is the confirmed-unique value; the plan's 'Unique' is kept for compatibility.
    s = (a.get("duplicate_status") or "").strip().lower()
    if s in ("unique", "single"):
        return 0
    return 2 if s == "duplicate" else 1


def _completeness(a):
    return sum(1 for s in SKILLS if a["scores"].get(s) is not None)


def _recency_ordinal(a):
    t = a.get("source_modified_time") or a.get("source_created_time")
    return t.timestamp() if t is not None else 0.0


def _winner_key(a):
    # Lower is better; negatives so more-complete / more-recent sort first.
    return (_status_rank(a), -_completeness(a), -_recency_ordinal(a), str(a["source_airtable_id"]))


def pick_winner(group):
    return min(group, key=_winner_key)


def dedupe(assessments):
    """Group by (child_uid, term); pick one winner per group. Returns (winners, exceptions).

    An exception is 'unresolved_tie' when the top two rows are identical on every criterion
    except record id (a genuine tie), or 'duplicate_more_complete_rejected' when a Duplicate-
    flagged row was more complete than the chosen winner (surfaced for human review).
    """
    groups = {}
    for a in assessments:
        groups.setdefault((a["child_uid"], a["term"]), []).append(a)
    winners, exceptions = {}, []
    for key, group in groups.items():
        winner = pick_winner(group)
        winners[key] = winner
        if len(group) > 1:
            ranks = sorted(_winner_key(a) for a in group)
            if ranks[0][:3] == ranks[1][:3]:
                exceptions.append({"key": key, "reason": "unresolved_tie",
                                   "winner": winner["source_airtable_id"], "n": len(group)})
            if any((a.get("duplicate_status") or "").strip().lower() == "duplicate"
                   and _completeness(a) > _completeness(winner) for a in group):
                exceptions.append({"key": key, "reason": "duplicate_more_complete_rejected",
                                   "winner": winner["source_airtable_id"], "n": len(group)})
    return winners, exceptions
