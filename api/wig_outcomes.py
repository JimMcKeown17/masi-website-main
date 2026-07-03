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
                .order_by('-started_at').first())
        if last is None or not last.success or last.completed_at is None:
            return False, f"latest '{sync_type}' sync is missing, incomplete, or failed"
        details = last.details or {}
        if details.get('retire_skipped') or details.get('dup_uid_skipped'):
            return False, f"latest '{sync_type}' sync flagged retire/duplicate skips"
        if last.completed_at < now - timedelta(hours=MAX_SYNC_AGE_HOURS):
            return False, f"latest '{sync_type}' sync is older than {MAX_SYNC_AGE_HOURS}h"
    return True, None
