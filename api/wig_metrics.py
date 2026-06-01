"""WIG dashboard metric service.

Pure-ish calculation logic for the WIG scoreboard, kept separate from the view
layer so it can be unit-tested directly. See
frontend `_plans/wig-dashboard/metric-contract.md` for definitions.
"""
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.db.models import Q

from .models import (
    Youth, LiteracySession2026, NumeracySession2026, MentorVisit, NumeracyVisit,
)

# Programme dates are South African; the server runs UTC, so resolve the
# business day in SAST before deriving week boundaries.
SAST = ZoneInfo('Africa/Johannesburg')


def last_completed_week(reference_dt):
    """Return (monday, sunday) dates of the last fully completed Mon-Sun week,
    relative to `reference_dt` (an aware datetime) interpreted in SAST."""
    today = reference_dt.astimezone(SAST).date()
    this_monday = today - timedelta(days=today.weekday())
    end = this_monday - timedelta(days=1)   # previous Sunday
    start = end - timedelta(days=6)          # previous Monday
    return start, end


# Site types are free-text on School.type and inconsistent in prod
# ('ECDC' and 'ECD' both occur). Normalise here, once.
ECD_SITE_TYPES = {'ECD', 'ECDC'}
PRIMARY_SITE_TYPES = {'Primary School'}


def classify_literacy_site(site_type):
    """Map a school's site type to a literacy programme.

    Core Literacy is delivered at primary schools, ECD Literacy at ECD sites.
    The same coach can work at both, so the *session's* site type decides the
    programme. Non-literacy sites (e.g. secondary) and blank/unknown -> None.
    """
    if site_type in PRIMARY_SITE_TYPES:
        return 'core_literacy'
    if site_type in ECD_SITE_TYPES:
        return 'ecd_literacy'
    return None


# Programme cohorts (site-type first). job_titles is a secondary filter that
# excludes non-coach roles; site_types splits the shared literacy coaches into
# Core (primary) vs ECD. Zazi iZandi is intentionally absent here - it comes
# from the Zazi backend, not the Masi PG.
COHORTS = {
    'core_literacy': {
        'site_types': PRIMARY_SITE_TYPES,
        'job_titles': {'Literacy Coach', 'Literacy Coaches (ZZ)'},
    },
    'ecd_literacy': {
        'site_types': ECD_SITE_TYPES,
        'job_titles': {'Literacy Coach', 'ZZ ECD Coach', 'ECD Practitioner', 'Practitioner'},
    },
    'numeracy': {
        'site_types': None,  # all sites for now (ECDC today; Primary coming)
        'job_titles': {'Numeracy Coach', 'Count Coach'},
    },
}


def eligible_coaches(programme, as_of):
    """Active coaches in a programme cohort who had started by `as_of`.

    A coach's programme bucket is their assigned school's site type, so the same
    job title splits into Core vs ECD by `school.type`. Coaches with no recorded
    start_date are kept (treated as long-standing).
    """
    spec = COHORTS[programme]
    qs = Youth.objects.filter(
        employment_status='Active',
        job_title__in=spec['job_titles'],
    ).filter(Q(start_date__isnull=True) | Q(start_date__lte=as_of))
    if spec['site_types'] is not None:
        qs = qs.filter(school__type__in=spec['site_types'])
    return qs


def _working_days_count(start, end):
    """Number of weekdays (Mon-Fri) in the inclusive range."""
    d, n = start, 0
    while d <= end:
        if d.weekday() < 5:
            n += 1
        d += timedelta(days=1)
    return n


def _programme_session_qs(programme, start, end):
    """Sessions for a programme in the window: right session table, filtered by
    the cohort's site types and coach job titles."""
    spec = COHORTS[programme]
    model = NumeracySession2026 if programme == 'numeracy' else LiteracySession2026
    qs = model.objects.filter(
        session_date__gte=start, session_date__lte=end,
        youth__job_title__in=spec['job_titles'],
    )
    if spec['site_types'] is not None:
        qs = qs.filter(school__type__in=spec['site_types'])
    return qs


def sessions_per_day(programme, start, end):
    """Average sessions per eligible coach per working day across the window.

    Zero eligible coaches (or zero working days) -> value None, so the frontend
    can render "no eligible coaches" rather than a misleading 0 or a crash.
    """
    eligible = eligible_coaches(programme, end).count()
    working_days = _working_days_count(start, end)
    numerator = _programme_session_qs(programme, start, end).count()
    denominator = eligible * working_days
    value = (numerator / denominator) if denominator else None
    return {
        'numerator': numerator,
        'denominator': denominator,
        'value': value,
        'eligible_entity_count': eligible,
        'calculation_note': f'{numerator} sessions / ({eligible} coaches x {working_days} working days)',
    }


def active_coaches(programme, start, end):
    """Fraction of eligible coaches who taught at least one session this window."""
    eligible_qs = eligible_coaches(programme, end)
    eligible = eligible_qs.count()
    taught_ids = set(_programme_session_qs(programme, start, end).values_list('youth_id', flat=True))
    active = eligible_qs.filter(id__in=taught_ids).count()
    value = (active / eligible) if eligible else None
    return {
        'numerator': active,
        'denominator': eligible,
        'value': value,
        'eligible_entity_count': eligible,
        'calculation_note': f'{active} of {eligible} eligible coaches taught this week',
    }


def school_coverage(programme, start, end):
    """Fraction of assigned schools (>=1 active assigned coach) reached this window.

    Denominator is intentional - schools we staffed, not 'schools ever touched'.
    """
    assigned_ids = set(
        eligible_coaches(programme, end)
        .exclude(school__isnull=True)
        .values_list('school_id', flat=True)
    )
    reached_ids = set(_programme_session_qs(programme, start, end).values_list('school_id', flat=True))
    covered = assigned_ids & reached_ids
    denominator = len(assigned_ids)
    value = (len(covered) / denominator) if denominator else None
    return {
        'numerator': len(covered),
        'denominator': denominator,
        'value': value,
        'eligible_entity_count': denominator,
        'calculation_note': f'{len(covered)} of {denominator} assigned schools reached this week',
    }


# --- Data-team quality sub-gauges (over the full dataset; accuracy is a state) ---

# Job titles that imply ECD work; assigned to a primary site they're a likely
# data-entry error (the obvious mismatch to minimise).
ECD_JOB_TITLES = {'ZZ ECD Coach', 'ECD Practitioner'}


def _quality_measure(numerator, denominator, note=''):
    value = (numerator / denominator) if denominator else None
    return {'numerator': numerator, 'denominator': denominator, 'value': value,
            'calculation_note': note}


def capture_on_time():
    """Share of literacy sessions captured within 2 days of the session date."""
    total = LiteracySession2026.objects.count()
    on_time = LiteracySession2026.objects.filter(
        capture_delay__gte=0, capture_delay__lte=2).count()
    return _quality_measure(on_time, total, f'{on_time} of {total} captured within 2 days')


def duplicate_rate():
    """Share of literacy sessions flagged as duplicates (lower is better)."""
    total = LiteracySession2026.objects.count()
    dups = LiteracySession2026.objects.filter(duplicate_status='Duplicate').count()
    return _quality_measure(dups, total, f'{dups} of {total} flagged Duplicate')


def site_job_mismatch():
    """Active youth with an ECD job title assigned to a primary site (likely
    data error). Lower is better."""
    active = Youth.objects.filter(employment_status='Active')
    flagged = active.filter(
        job_title__in=ECD_JOB_TITLES, school__type__in=PRIMARY_SITE_TYPES).count()
    return _quality_measure(flagged, active.count(),
                            f'{flagged} active youth with an ECD title at a primary site')


def child_fk_resolution():
    """Share of literacy child *slots* resolved to a CanonicalChild. Each session
    has two child slots; counts both (a null child_2 is an unresolved slot)."""
    total = LiteracySession2026.objects.count()
    slots = total * 2
    resolved = (LiteracySession2026.objects.filter(child_1__isnull=False).count()
                + LiteracySession2026.objects.filter(child_2__isnull=False).count())
    return _quality_measure(resolved, slots, f'{resolved} of {slots} child slots resolved')


def sessions_per_week(programme, start, end):
    """Total sessions per eligible coach across the window (no per-day divisor).

    Used by numeracy, whose lead measure is "N sessions per week per coach".
    """
    eligible = eligible_coaches(programme, end).count()
    numerator = _programme_session_qs(programme, start, end).count()
    value = (numerator / eligible) if eligible else None
    return {
        'numerator': numerator,
        'denominator': eligible,
        'value': value,
        'eligible_entity_count': eligible,
        'calculation_note': f'{numerator} sessions / {eligible} coaches this week',
    }


# --- Mentor-visit lead measures (attributed by visited school's site type) ---

LITERACY_VISIT_BUNDLE = ['letter_trackers_correct', 'reading_trackers_correct',
                         'sessions_correct', 'admin_correct']
NUMERACY_VISIT_BUNDLE = ['numeracy_tracker_correct']


def _visit_spec(programme):
    """(model, compliance-bundle fields, site_types) for a programme's visits."""
    if programme == 'numeracy':
        return NumeracyVisit, NUMERACY_VISIT_BUNDLE, None
    return MentorVisit, LITERACY_VISIT_BUNDLE, COHORTS[programme]['site_types']


def _programme_visit_qs(programme, start, end):
    """Observation visits in the window, attributed to the programme by the
    visited school's site type."""
    model, _bundle, site_types = _visit_spec(programme)
    qs = model.objects.filter(visit_type='observation',
                              visit_date__gte=start, visit_date__lte=end)
    if site_types is not None:
        qs = qs.filter(school__type__in=site_types)
    return qs


def visit_compliance(programme, start, end):
    """Share of observation visits where every tracker boolean is true. A null
    boolean is non-compliant (and counted as incomplete for transparency)."""
    _model, bundle, _st = _visit_spec(programme)
    qs = _programme_visit_qs(programme, start, end)
    total = qs.count()
    compliant = qs.filter(**{f: True for f in bundle}).count()
    incomplete_q = Q()
    for f in bundle:
        incomplete_q |= Q(**{f'{f}__isnull': True})
    incomplete = qs.filter(incomplete_q).count()
    value = (compliant / total) if total else None
    return {
        'numerator': compliant,
        'denominator': total,
        'value': value,
        'incomplete_count': incomplete,
        'calculation_note': f'{compliant} of {total} observation visits fully compliant',
    }


def school_visits(programme, start, end):
    """Average observation visits per mentor this window (per-mentor target).

    Counted per submitting user; mentors are dedicated per site type, so a
    submitter crossing site types would be a data issue (see notes in contract).
    """
    qs = _programme_visit_qs(programme, start, end)
    visits = qs.count()
    mentors = qs.values('mentor_id').distinct().count()
    value = (visits / mentors) if mentors else None
    return {
        'numerator': visits,
        'denominator': mentors,
        'value': value,
        'eligible_entity_count': mentors,
        'calculation_note': f'{visits} observation visits across {mentors} mentors',
    }


# --- Assembly into the API payload shapes (see metric-contract.md) ---

def build_lead_measures(reference_dt):
    """Assemble the /api/wig/lead-measures payload for the last completed week."""
    start, end = last_completed_week(reference_dt)
    measures = {}
    for prog in ('core_literacy', 'ecd_literacy'):
        measures[f'{prog}.sessions_per_day'] = sessions_per_day(prog, start, end)
        measures[f'{prog}.active_coaches'] = active_coaches(prog, start, end)
        measures[f'{prog}.school_coverage'] = school_coverage(prog, start, end)
        measures[f'{prog}.tracker_compliance'] = visit_compliance(prog, start, end)
        measures[f'{prog}.school_visits'] = school_visits(prog, start, end)
    measures['numeracy.sessions_per_week'] = sessions_per_week('numeracy', start, end)
    measures['numeracy.active_coaches'] = active_coaches('numeracy', start, end)
    measures['numeracy.school_coverage'] = school_coverage('numeracy', start, end)
    measures['numeracy.admin_compliance'] = visit_compliance('numeracy', start, end)
    return {
        'window': {
            'period': 'last_week',
            'date_from': start.isoformat(),
            'date_to': end.isoformat(),
            'working_days': _working_days_count(start, end),
            'data_as_of': end.isoformat(),
        },
        'measures': measures,
    }


def build_data_quality():
    """Assemble the /api/wig/data-quality payload (full-dataset accuracy gauges).

    The headline "98% accurate" formula is deferred to the team; v1 surfaces the
    concrete sub-gauges only.
    """
    return {
        'scope': 'full_dataset',
        'measures': {
            'dq.child_fk_resolution': child_fk_resolution(),
            'dq.capture_on_time': capture_on_time(),
            'dq.duplicate_rate': duplicate_rate(),
            'dq.site_job_mismatch': site_job_mismatch(),
        },
    }
