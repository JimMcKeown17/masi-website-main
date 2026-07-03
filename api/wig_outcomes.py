"""Outcome (lag) measures for the WIG hero rings: Core Literacy + ECD Literacy.

Term-keyed (Jan/Jun/Nov) over literacy_assessments_2026 + on_the_programme_2026,
unlike the weekly lead measures in wig_metrics.py. Fail-closed: any source-health,
staleness, or dedupe-exception problem returns available=False rather than a
number the parquet export (export_literacy_2026_parquet) would refuse to ship.
"""
from datetime import timedelta

from django.utils import timezone

from .literacy_2026_dedupe import assessment_row, dedupe
from .literacy_2026_grades import grade_is_fallback, normalize_grade
from .models import AirtableSyncLog, LiteracyAssessment2026, OnTheProgramme2026

REQUIRED_SYNCS = ("literacy_assessments_2026", "on_the_programme_2026")
MAX_SYNC_AGE_HOURS = 48  # two missed nightly runs = dead cron
# Nov endline: append "Nov" here ONLY together with the exporter's TERM_TO_PREFIX
# and the Streamlit processor's MONTHS, so the parity surfaces can cross-check.
TERM_ORDER = ("Jan", "Jun")

# "max" mirrors the portal's _null_out_of_range: scores above the instrument max
# are data errors, treated as missing. Letter Sounds (60) and Read Words (40) are
# language-invariant (no IsiXhosa/Afrikaans override touches them).
OUTCOME_DEFS = {
    "core_literacy": {"grade": "Grade 1", "skill": "Read Words", "threshold": 16.0, "max": 40.0,
                      "label": "Grade 1 on-roster children with Read Words >= 16"},
    "ecd_literacy": {"grade": "PreR", "skill": "Letter Sounds", "threshold": 20.0, "max": 60.0,
                     "label": "PreR on-roster children with Letter Sounds >= 20"},
}


def check_sources(now):
    """(ok, note): the exporter's _assert_synced rules + a 48h dead-cron age gate."""
    for sync_type in REQUIRED_SYNCS:
        last = (AirtableSyncLog.objects.filter(sync_type=sync_type)
                .order_by('-started_at', '-pk').first())
        if last is None or not last.success or last.completed_at is None:
            return False, f"latest '{sync_type}' sync is missing, incomplete, or failed"
        details = last.details or {}
        if details.get('retire_skipped') or details.get('dup_uid_skipped'):
            return False, f"latest '{sync_type}' sync flagged retire/duplicate skips"
        if last.completed_at < now - timedelta(hours=MAX_SYNC_AGE_HOURS):
            return False, f"latest '{sync_type}' sync is older than {MAX_SYNC_AGE_HOURS}h"
    return True, None


def _term_stat(cohort_uids, winners, term, defn):
    """Assessed-only stats for one term, or None if nobody has the skill scored.

    Scores above the instrument max are data errors, treated as missing —
    the portal's _null_out_of_range rule, so both surfaces publish the same %.
    """
    num = den = 0
    for uid in cohort_uids:
        row = winners.get((uid, term))
        score = row['scores'].get(defn['skill']) if row else None
        if score is None or score > defn['max']:
            continue
        den += 1
        if score >= defn['threshold']:
            num += 1
    if den == 0:
        return None
    return {'value': num / den, 'numerator': num, 'denominator': den, 'term': term}


def _child_grades(roster_grades, winners):
    """Cohort grade per child: normalize_grade(roster grade or winner-row grade),
    the exporter's roster-first rule. Returns (grades, fallback_uids)."""
    grades, fallbacks = {}, set()
    for uid, roster_grade in roster_grades.items():
        raw = roster_grade
        if not raw:
            # Exporter rule: the latest existing winner row's grade, even if
            # None (which falls back to PreR) — never fall through to an
            # earlier term's grade.
            for term in reversed(TERM_ORDER):
                row = winners.get((uid, term))
                if row:
                    raw = row.get('grade')
                    break
        if grade_is_fallback(raw):
            fallbacks.add(uid)
        grades[uid] = normalize_grade(raw)
    return grades, fallbacks


def _programme_outcome(defn, grades, fallback_uids, winners):
    cohort = [uid for uid, g in grades.items() if g == defn['grade']]
    stats = {term: _term_stat(cohort, winners, term, defn) for term in TERM_ORDER}
    latest = None
    for term in TERM_ORDER:
        if stats[term] is not None:
            latest = term
    if latest is None:
        return None
    result = dict(stats[latest])
    result['cohort_total'] = len(cohort)
    result['baseline'] = stats['Jan'] if latest != 'Jan' else None
    n_fallback = sum(1 for uid in cohort if uid in fallback_uids)
    result['calculation_note'] = f"{defn['label']}; {n_fallback} grade fallback(s) in cohort"
    return result


def build_outcomes(now=None):
    """The /api/wig/outcomes/ payload. Fail-closed on source health and dedupe."""
    now = now or timezone.now()

    def unavailable(note):
        return {'available': False, 'source_note': note, 'outcomes': {},
                'data_as_of': now.isoformat()}

    ok, note = check_sources(now)
    if not ok:
        return unavailable(note)

    # Dedupe over ALL active roster children (even off-programme ones), the
    # exact set the exporter dedupes and blocks on; cohorts are then built
    # from the on-programme subset only.
    roster = list(OnTheProgramme2026.objects.filter(is_active=True))
    rows = [assessment_row(a) for a in LiteracyAssessment2026.objects.filter(
        year=2026, is_active=True, term__in=TERM_ORDER,
        child_uid__in=[r.child_uid for r in roster])]
    winners, exceptions = dedupe(rows)
    # Roster-wide scope (all grades), deliberately matching the exporter's
    # blocking scope: it too fails the whole export on any exception.
    if exceptions:
        return unavailable(
            f"{len(exceptions)} dedupe exception(s) need review before outcomes publish")

    roster_grades = {r.child_uid: r.grade for r in roster if r.on_the_programme}

    grades, fallback_uids = _child_grades(roster_grades, winners)
    outcomes = {key: _programme_outcome(defn, grades, fallback_uids, winners)
                for key, defn in OUTCOME_DEFS.items()}
    return {'available': True, 'source_note': None, 'outcomes': outcomes,
            'data_as_of': now.isoformat()}
