"""WIG drill-down detail builders.

The headline measures (api/wig_metrics.py) return single numbers. The dashboard
lets a user click a ring to see the supporting data behind it. Each builder
returns a discriminated payload ({'kind': ...}) scoped by the same site-type-first
cohorts as the headline measure, so the detail always matches the gauge.
"""
from collections import defaultdict
from datetime import timedelta

from django.db.models import Count, Max, Q

from .models import Youth, LiteracySession2026, NumeracySession2026
from .wig_metrics import (
    COHORTS, ECD_JOB_TITLES, PRIMARY_SITE_TYPES,
    last_completed_week, eligible_coaches,
    _programme_session_qs, _visit_spec, _programme_visit_qs,
)

WEEKS = 8


def _week_buckets(end_sunday, weeks=WEEKS):
    """(monday, sunday) for the last `weeks` completed weeks, oldest first."""
    buckets = []
    for i in range(weeks - 1, -1, -1):
        sun = end_sunday - timedelta(days=7 * i)
        buckets.append((sun - timedelta(days=6), sun))
    return buckets


def _bucket_index(d, buckets):
    for i, (mon, sun) in enumerate(buckets):
        if mon <= d <= sun:
            return i
    return None


def _week_label(monday):
    return monday.strftime('%-d %b')  # e.g. "18 May"


def session_heatmap(programme, reference_dt):
    """Per-coach weekly session counts over the last 8 weeks (current roster)."""
    _start, end = last_completed_week(reference_dt)
    buckets = _week_buckets(end)
    rows_qs = _programme_session_qs(programme, buckets[0][0], buckets[-1][1])
    counts = defaultdict(lambda: [0] * WEEKS)
    for youth_id, session_date in rows_qs.values_list('youth_id', 'session_date'):
        idx = _bucket_index(session_date, buckets)
        if idx is not None:
            counts[youth_id][idx] += 1

    rows = []
    for y in eligible_coaches(programme, end).select_related('mentor'):
        weekly = counts.get(y.id, [0] * WEEKS)
        rows.append({
            'youth_uid': y.youth_uid or f'id-{y.id}',
            'full_name': y.full_name or f'{y.first_names} {y.last_name}',
            'mentor_name': y.mentor.name if y.mentor_id else '',
            'weekly_counts': weekly,
            'total': sum(weekly),
        })
    rows.sort(key=lambda r: r['total'], reverse=True)
    return {
        'kind': 'session_heatmap',
        'weeks': [{'start': mon.isoformat(), 'label': _week_label(mon)} for mon, _ in buckets],
        'rows': rows,
    }


def coverage_detail(programme, reference_dt):
    """Schools reached vs assigned-but-not-reached in the last completed week."""
    start, end = last_completed_week(reference_dt)
    reached = (
        _programme_session_qs(programme, start, end)
        .values('school__school_uid', 'school__name', 'school__type')
        .annotate(session_count=Count('id'), youth_count=Count('youth_id', distinct=True))
    )
    covered = [{
        'school_uid': r['school__school_uid'],
        'name': r['school__name'],
        'type': r['school__type'] or 'Unknown',
        'session_count': r['session_count'],
        'youth_count': r['youth_count'],
    } for r in reached if r['school__school_uid']]
    covered.sort(key=lambda s: s['session_count'], reverse=True)
    covered_uids = {c['school_uid'] for c in covered}

    model = NumeracySession2026 if programme == 'numeracy' else LiteracySession2026
    assigned = (
        eligible_coaches(programme, end).exclude(school__isnull=True)
        .values('school__school_uid', 'school__name', 'school__type').distinct()
    )
    uncovered_specs = [
        a for a in assigned
        if a['school__school_uid'] and a['school__school_uid'] not in covered_uids
    ]
    # Last session date per uncovered school, in one query (not per-school).
    last_map = dict(
        model.objects
        .filter(school__school_uid__in=[a['school__school_uid'] for a in uncovered_specs])
        .values_list('school__school_uid')
        .annotate(last=Max('session_date'))
        .values_list('school__school_uid', 'last')
    )
    uncovered = [{
        'school_uid': a['school__school_uid'],
        'name': a['school__name'],
        'type': a['school__type'] or 'Unknown',
        'last_session_date': last_map[a['school__school_uid']].isoformat()
        if last_map.get(a['school__school_uid']) else None,
    } for a in uncovered_specs]
    uncovered.sort(key=lambda s: s['name'])
    return {'kind': 'coverage', 'covered': covered, 'uncovered': uncovered}


_FIELD_LABELS = {
    'letter_trackers_correct': 'Letter trackers',
    'reading_trackers_correct': 'Reading trackers',
    'sessions_correct': 'Session trackers',
    'admin_correct': 'Admin',
    'numeracy_tracker_correct': 'Numeracy tracker',
}


def visit_detail(programme, reference_dt):
    """Observation visits in the last completed week with their tracker flags."""
    start, end = last_completed_week(reference_dt)
    _model, bundle, _site_types = _visit_spec(programme)
    qs = _programme_visit_qs(programme, start, end).select_related('mentor', 'school').order_by('-visit_date')
    visits = []
    for v in qs:
        flags = {f: getattr(v, f) for f in bundle}
        visits.append({
            'visit_date': v.visit_date.isoformat(),
            'mentor_name': v.mentor.get_full_name() or v.mentor.username,
            'school_name': v.school.name,
            'school_type': v.school.type or 'Unknown',
            'flags': flags,
            'compliant': all(flags[f] is True for f in bundle),
        })
    columns = [{'key': f, 'label': _FIELD_LABELS.get(f, f)} for f in bundle]
    return {'kind': 'visit_table', 'columns': columns, 'visits': visits}


# --- Data-team data-quality record tables (the offending rows behind a gauge) ---

_SESSION_COLUMNS = [
    {'key': 'session_date', 'label': 'Date'},
    {'key': 'youth', 'label': 'Coach'},
    {'key': 'school', 'label': 'School'},
]


def _session_row(s):
    return {
        'session_date': s.session_date.isoformat() if s.session_date else '',
        'youth': s.youth.full_name if s.youth_id else '',
        'school': s.school.name if s.school_id else '',
    }


def _dq(title, columns, rows, total, note):
    return {'kind': 'dq_records', 'title': title, 'columns': columns,
            'rows': rows, 'total_flagged': total, 'note': note}


def dq_detail(measure):
    if measure == 'dq.duplicate_rate':
        qs = (LiteracySession2026.objects.filter(duplicate_status='Duplicate')
              .select_related('youth', 'school').order_by('-session_date'))
        return _dq('Duplicate sessions', _SESSION_COLUMNS, [_session_row(s) for s in qs[:100]],
                   qs.count(), "Literacy sessions flagged duplicate_status='Duplicate'.")

    if measure == 'dq.capture_on_time':
        qs = (LiteracySession2026.objects
              .exclude(capture_delay__gte=0, capture_delay__lte=2)
              .select_related('youth', 'school').order_by('-session_date'))
        rows = [{**_session_row(s), 'capture_delay': s.capture_delay} for s in qs[:100]]
        cols = _SESSION_COLUMNS + [{'key': 'capture_delay', 'label': 'Capture delay (days)'}]
        return _dq('Late / abnormal captures', cols, rows, qs.count(),
                   'Sessions captured outside the 0-2 day window (or missing a delay).')

    if measure == 'dq.child_fk_resolution':
        qs = (LiteracySession2026.objects.filter(Q(child_1__isnull=True) | Q(child_2__isnull=True))
              .select_related('youth', 'school').order_by('-session_date'))
        rows = []
        for s in qs[:100]:
            missing = [slot for slot, val in (('child_1', s.child_1_id), ('child_2', s.child_2_id)) if val is None]
            rows.append({**_session_row(s), 'unresolved': ', '.join(missing)})
        cols = _SESSION_COLUMNS + [{'key': 'unresolved', 'label': 'Unresolved slot'}]
        return _dq('Unresolved child links', cols, rows, qs.count(),
                   'Literacy sessions with an unresolved child_1 / child_2 slot.')

    if measure == 'dq.site_job_mismatch':
        qs = (Youth.objects.filter(employment_status='Active', job_title__in=ECD_JOB_TITLES,
                                   school__type__in=PRIMARY_SITE_TYPES)
              .select_related('school').order_by('full_name'))
        rows = [{
            'name': y.full_name,
            'job_title': y.job_title,
            'school': y.school.name if y.school_id else '',
            'type': y.school.type if y.school_id else '',
        } for y in qs[:100]]
        cols = [{'key': 'name', 'label': 'Youth'}, {'key': 'job_title', 'label': 'Job title'},
                {'key': 'school', 'label': 'School'}, {'key': 'type', 'label': 'Site type'}]
        return _dq('ECD title at a primary site', cols, rows, qs.count(),
                   'Active youth with an ECD job title assigned to a primary site.')

    return {'kind': 'none'}


_SESSION_SUFFIXES = {'sessions_per_day', 'sessions_per_week', 'active_coaches'}
_VISIT_SUFFIXES = {'tracker_compliance', 'admin_compliance', 'school_visits'}


def build_wig_detail(programme, measure, reference_dt):
    """Dispatch a (programme, measure) to the right detail builder."""
    if measure.startswith('dq.'):
        return dq_detail(measure)
    if programme not in COHORTS:
        return {'kind': 'none'}
    suffix = measure.split('.', 1)[1] if '.' in measure else measure
    if suffix in _SESSION_SUFFIXES:
        return session_heatmap(programme, reference_dt)
    if suffix == 'school_coverage':
        return coverage_detail(programme, reference_dt)
    if suffix in _VISIT_SUFFIXES:
        return visit_detail(programme, reference_dt)
    return {'kind': 'none'}
