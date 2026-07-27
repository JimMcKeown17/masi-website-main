"""Outcome (lag) measures for the WIG hero rings.

Term-keyed assessment results, unlike the weekly lead measures in wig_metrics.py.
Each backend-owned programme follows the same population and quality rules as its
parquet export so the WIG board and data portal cannot publish different answers.
"""
from datetime import timedelta

from django.utils import timezone

from . import zazi_client
from .literacy_2026_dedupe import assessment_row, dedupe
from .literacy_2026_grades import grade_is_fallback, normalize_grade
from .models import (
    AirtableSyncLog,
    CanonicalChild,
    LiteracyAssessment2026,
    NumeracyAssessment2026,
    NumeracyOnTheProgramme2026,
    OnTheProgramme2026,
)
from .numeracy_2026 import COMPONENTS as NUMERACY_COMPONENTS, evaluate_quality

REQUIRED_SYNCS = ("literacy_assessments_2026", "on_the_programme_2026")
NUMERACY_REQUIRED_SYNCS = (
    "numeracy_assessments_2026",
    "numeracy_on_the_programme_2026",
)
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


ZAZI_PROGRAMME_KEYS = ('zazi_izandi', 'zazi_izandi_ecd')


# Live-fetch architecture is kept; the cache only prevents timeout storms.
_zazi_cache = {'at': None, 'entries': None}

ZAZI_REQUIRED_METRIC_KEYS = {
    'key', 'label', 'threshold', 'target', 'value', 'numerator', 'denominator', 'baseline'
}


def _zazi_single(prog, as_of):
    """Flatten a one-metric Zazi programme to the single-outcome shape."""
    m = prog['metrics'][0]
    return {
        'kind': 'single', 'value': m['value'], 'numerator': m['numerator'],
        'denominator': m['denominator'], 'term': prog['term'],
        'baseline': (dict(m['baseline'], term='baseline') if m.get('baseline') else None),
        'target': m['target'],
        'calculation_note': f"Zazi backend benchmark; data as of {as_of or 'unknown'}",
    }


def _zazi_unavailable(note):
    return {key: {'kind': 'unavailable', 'note': note} for key in ZAZI_PROGRAMME_KEYS}


def _validate_zazi_programme(prog):
    if not isinstance(prog, dict):
        raise ValueError('programme is not a dict')
    term = prog.get('term')
    metrics = prog.get('metrics')
    if not isinstance(term, str) or not isinstance(metrics, list) or not metrics:
        raise ValueError('programme has invalid term or metrics')
    for metric in metrics:
        if not isinstance(metric, dict):
            raise ValueError('metric is not a dict')
        if not ZAZI_REQUIRED_METRIC_KEYS.issubset(metric.keys()):
            raise ValueError('metric is missing required keys')


def _normalize_zazi_payload(payload):
    if not isinstance(payload, dict):
        raise ValueError('payload is not a dict')
    programmes = payload.get('programmes')
    if not isinstance(programmes, dict):
        raise ValueError('programmes is not a dict')
    if any(key not in programmes for key in ZAZI_PROGRAMME_KEYS):
        raise ValueError('programmes missing required key')

    as_of = payload.get('as_of')
    result = {}
    for key in ZAZI_PROGRAMME_KEYS:
        prog = programmes[key]
        if prog is None:
            result[key] = None
            continue
        _validate_zazi_programme(prog)
        if key == 'zazi_izandi':
            result[key] = {'kind': 'multi', 'term': prog['term'],
                           'as_of': as_of, 'metrics': prog['metrics']}
        else:
            result[key] = _zazi_single(prog, as_of)
    return result


def _zazi_outcomes(now):
    """Per-programme Zazi entries; any failure degrades ONLY the Zazi keys."""
    cached_at = _zazi_cache['at']
    if cached_at is not None and _zazi_cache['entries'] is not None:
        if now - cached_at < timedelta(seconds=60):
            return _zazi_cache['entries']

    try:
        payload = zazi_client.fetch_zazi_wig_outcomes()
    except Exception:
        entries = _zazi_unavailable('Zazi backend unreachable')
    else:
        try:
            entries = _normalize_zazi_payload(payload)
        except Exception:
            entries = _zazi_unavailable('Zazi payload malformed')

    _zazi_cache.update({'at': now, 'entries': entries})
    return entries


def check_sources(now):
    """(ok, note): the exporter's _assert_synced rules."""
    for sync_type in REQUIRED_SYNCS:
        last = (AirtableSyncLog.objects.filter(sync_type=sync_type)
                .order_by('-started_at', '-pk').first())
        if last is None or not last.success or last.completed_at is None:
            return False, f"latest '{sync_type}' sync is missing, incomplete, or failed"
        details = last.details or {}
        if details.get('retire_skipped') or details.get('dup_uid_skipped'):
            return False, f"latest '{sync_type}' sync flagged retire/duplicate skips"
    return True, None


def check_numeracy_sources(now):
    """Apply the numeracy exporter's sync-integrity gate."""
    blocking_keys = {
        "numeracy_assessments_2026": ("retire_skipped",),
        "numeracy_on_the_programme_2026": (
            "retire_skipped",
            "duplicate_child_uids",
        ),
    }
    for sync_type in NUMERACY_REQUIRED_SYNCS:
        last = (AirtableSyncLog.objects.filter(sync_type=sync_type)
                .order_by('-started_at', '-pk').first())
        if last is None or not last.success or last.completed_at is None:
            return False, f"latest '{sync_type}' sync is missing, incomplete, or failed"
        details = last.details or {}
        if any(details.get(key) for key in blocking_keys[sync_type]):
            return False, f"latest '{sync_type}' sync flagged publication blockers"
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
    result['kind'] = 'single'
    result['cohort_total'] = len(cohort)
    result['baseline'] = stats['Jan'] if latest != 'Jan' else None
    n_fallback = sum(1 for uid in cohort if uid in fallback_uids)
    result['calculation_note'] = f"{defn['label']}; {n_fallback} grade fallback(s) in cohort"
    return result


def _numeracy_term_stat(cohort_uids, winners, term):
    """Count-to-30 status among complete, accepted assessments for one term."""
    numerator = denominator = 0
    for uid in cohort_uids:
        row = winners.get((uid, 2026, term))
        if row is None or any(
            row.get(component.model_field) is None
            for component in NUMERACY_COMPONENTS
        ):
            continue
        denominator += 1
        if row["counting_aloud"] >= 30:
            numerator += 1
    if denominator == 0:
        return None
    return {
        "value": numerator / denominator,
        "numerator": numerator,
        "denominator": denominator,
        "term": term,
    }


def _numeracy_outcome(now):
    """Build the portal-parity count-to-30 result, independently of literacy."""
    ok, note = check_numeracy_sources(now)
    if not ok:
        return {"kind": "unavailable", "note": note}

    roster_uids = list(
        NumeracyOnTheProgramme2026.objects.filter(is_active=True)
        .values_list("child_uid", flat=True)
    )
    if not roster_uids:
        return None

    resolved_uids = set(
        CanonicalChild.objects.filter(child_uid__in=roster_uids)
        .exclude(full_name__isnull=True)
        .exclude(full_name="")
        .values_list("child_uid", flat=True)
    )
    fields = [
        "source_airtable_id",
        "child_uid",
        "year",
        "term",
        *(component.model_field for component in NUMERACY_COMPONENTS),
    ]
    rows = list(
        NumeracyAssessment2026.objects.filter(
            is_active=True,
            year=2026,
            term__in=("Jan", "Jun"),
            child_uid__in=roster_uids,
        ).values(*fields)
    )
    winners, _issues = evaluate_quality(rows)
    stats = {
        term: _numeracy_term_stat(resolved_uids, winners, term)
        for term in ("Jan", "Jun")
    }
    latest = "Jun" if stats["Jun"] is not None else "Jan"
    if stats[latest] is None:
        return None

    result = dict(stats[latest])
    result.update({
        "kind": "single",
        "cohort_total": len(roster_uids),
        "baseline": stats["Jan"] if latest != "Jan" else None,
        "calculation_note": (
            "Active 2026 numeracy roster children with complete, accepted "
            "assessments and Counting Aloud >= 30; "
            f"{len(roster_uids) - len(resolved_uids)} unresolved roster "
            "identity row(s) excluded"
        ),
    })
    return result


def build_outcomes(now=None):
    """The /api/wig/outcomes/ payload. Fail-closed on source health and dedupe."""
    now = now or timezone.now()

    outcomes = _zazi_outcomes(now)
    outcomes["numeracy"] = _numeracy_outcome(now)

    def unavailable(note):
        return {'available': False, 'source_note': note, 'outcomes': outcomes,
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
    outcomes.update({key: _programme_outcome(defn, grades, fallback_uids, winners)
                     for key, defn in OUTCOME_DEFS.items()})
    return {'available': True, 'source_note': None, 'outcomes': outcomes,
            'data_as_of': now.isoformat()}
