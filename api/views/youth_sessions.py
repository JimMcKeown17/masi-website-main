from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.authentication import SessionAuthentication
from django.utils import timezone
from django.db.models import Count, Max, Q
from datetime import timedelta, date
from collections import defaultdict
from itertools import chain

from ..models import (
    LiteracySession2026, NumeracySession2026,
    Youth, School, Mentor,
)
from ..authentication import ClerkAuthentication
from ..closures import open_working_days_bulk, working_days_count

AUTH_CLASSES = [SessionAuthentication, ClerkAuthentication]
PERM_CLASSES = [permissions.IsAuthenticated]

# Job titles included in this dashboard (v1).
# Excluded for now: Zazi Izandi Coach, ZZ ECD Coach, 1000 Stories Youth,
# Assessor, EduTech Coach, Literacy Coaches (ZZ), Practitioner, Homework Coach.
INCLUDED_JOB_TITLES = ['Literacy Coach', 'Numeracy Coach']
LITERACY_JOB_TITLES = ['Literacy Coach']
NUMERACY_JOB_TITLES = ['Numeracy Coach']


def _get_job_titles_for_programme(programme):
    """Return the job_title list to filter Youth by, based on programme param."""
    if programme == 'literacy':
        return LITERACY_JOB_TITLES
    elif programme == 'numeracy':
        return NUMERACY_JOB_TITLES
    return INCLUDED_JOB_TITLES


def _active_youth_qs(params, *, reference_date=None):
    """Base queryset for active youth, filtered by programme job titles.

    Honors mentor_id, school_uid, and youth_uid params. Excludes youth whose
    start_date is after reference_date; youth with no recorded start_date are
    kept. reference_date defaults to today.
    """
    programme = params.get('programme', 'all')
    titles = _get_job_titles_for_programme(programme)
    qs = Youth.objects.filter(employment_status='Active', job_title__in=titles)
    mentor_id = params.get('mentor_id')
    if mentor_id:
        qs = qs.filter(mentor_id=mentor_id)
    school_uid = params.get('school_uid')
    if school_uid:
        qs = qs.filter(school__school_uid=school_uid)
    youth_uid = params.get('youth_uid')
    if youth_uid:
        qs = qs.filter(youth_uid=youth_uid)
    if reference_date is None:
        reference_date = timezone.now().date()
    qs = qs.filter(Q(start_date__isnull=True) | Q(start_date__lte=reference_date))
    return qs


def _get_working_days(start_date, end_date):
    """Return list of weekday dates in [start_date, end_date]."""
    days = []
    d = start_date
    while d <= end_date:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    return days


def _last_n_working_days(n, ref_date=None):
    """Return the last N working days ending at ref_date (inclusive)."""
    ref = ref_date or timezone.now().date()
    days = []
    d = ref
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d)
        d -= timedelta(days=1)
    return sorted(days)


def _apply_common_filters(qs, params):
    """Apply common query params to a session queryset."""
    date_from = params.get('date_from')
    date_to = params.get('date_to')
    youth_uid = params.get('youth_uid')
    school_uid = params.get('school_uid')
    mentor_id = params.get('mentor_id')

    if date_from:
        qs = qs.filter(session_date__gte=date_from)
    if date_to:
        qs = qs.filter(session_date__lte=date_to)
    if youth_uid:
        qs = qs.filter(youth__youth_uid=youth_uid)
    if school_uid:
        qs = qs.filter(school__school_uid=school_uid)
    if mentor_id:
        qs = qs.filter(youth__mentor_id=mentor_id)

    return qs


def _get_session_querysets(params):
    """Return (literacy_qs, numeracy_qs) with common filters applied.
    Respects the 'programme' param to return empty querysets when filtered out.
    Also restricts sessions to only those from included youth (by job title)."""
    programme = params.get('programme', 'all')
    titles = _get_job_titles_for_programme(programme)

    # Only include sessions from youth with included job titles
    lit_qs = LiteracySession2026.objects.filter(youth__job_title__in=titles)
    num_qs = NumeracySession2026.objects.filter(youth__job_title__in=titles)

    if programme == 'literacy':
        num_qs = num_qs.none()
    elif programme == 'numeracy':
        lit_qs = lit_qs.none()

    lit_qs = _apply_common_filters(lit_qs, params)
    num_qs = _apply_common_filters(num_qs, params)

    return lit_qs, num_qs


def _inactivity_state(params, days, today):
    """Inputs for closure/absence-aware inactivity: the active youth, each youth's
    open working days (closures + absences + start-date applied), and the dates
    each had sessions. Looks back a generous window so closures don't shorten the
    'last N working days' check."""
    active = list(_active_youth_qs(params, reference_date=today).select_related('mentor', 'school'))
    lookback = _last_n_working_days(days + 14, today)
    window_start = lookback[0] if lookback else today
    open_by_id = open_working_days_bulk(active, window_start, today)
    lit_qs, num_qs = _get_session_querysets(params)
    sess = defaultdict(set)
    for uid, d in lit_qs.filter(session_date__gte=window_start).values_list('youth_uid', 'session_date'):
        if uid:
            sess[uid].add(d)
    for uid, d in num_qs.filter(session_date__gte=window_start).values_list('youth_uid', 'session_date'):
        if uid:
            sess[uid].add(d)
    return active, open_by_id, sess


def _is_inactive(youth, open_by_id, sess, days):
    """Inactive = no session on any of the youth's last `days` OPEN working days.
    Youth with no recent expected days (brand new, or fully closed) aren't flagged."""
    open_days = sorted(open_by_id.get(youth.id, set()))
    last_n_open = set(open_days[-days:])
    if not last_n_open:
        return False
    return not (last_n_open & sess.get(youth.youth_uid, set()))


@api_view(['GET'])
@authentication_classes(AUTH_CLASSES)
@permission_classes(PERM_CLASSES)
def youth_sessions_summary(request):
    """Top-level stat cards for youth sessions dashboard."""
    params = request.query_params
    lit_qs, num_qs = _get_session_querysets(params)

    today = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    lit_today = lit_qs.filter(session_date=today).count()
    num_today = num_qs.filter(session_date=today).count()
    lit_week = lit_qs.filter(session_date__gte=week_start).count()
    num_week = num_qs.filter(session_date__gte=week_start).count()
    lit_month = lit_qs.filter(session_date__gte=month_start).count()
    num_month = num_qs.filter(session_date__gte=month_start).count()

    today_youth_uids = set(
        lit_qs.filter(session_date=today).values_list('youth_uid', flat=True)
    ) | set(
        num_qs.filter(session_date=today).values_list('youth_uid', flat=True)
    )

    active_youth_week_uids = set(
        lit_qs.filter(session_date__gte=week_start).values_list('youth_uid', flat=True)
    ) | set(
        num_qs.filter(session_date__gte=week_start).values_list('youth_uid', flat=True)
    )

    active_youth = _active_youth_qs(params, reference_date=today)
    total_active_youth = active_youth.count()

    # Inactive: active youth with no sessions in their last 2 *expected* working
    # days (so a closure or personal absence doesn't count against them).
    inactive_active, inactive_open, inactive_sess = _inactivity_state(params, 2, today)
    inactive_count = sum(
        1 for y in inactive_active
        if y.youth_uid and _is_inactive(y, inactive_open, inactive_sess, 2)
    )

    today_school_uids = set(
        lit_qs.filter(session_date=today).values_list('school_uid', flat=True)
    ) | set(
        num_qs.filter(session_date=today).values_list('school_uid', flat=True)
    )
    total_schools = School.objects.filter(is_active=True).count()

    week_total = lit_week + num_week
    active_week_count = len(active_youth_week_uids)
    avg_sessions = round(week_total / active_week_count, 1) if active_week_count else 0

    return Response({
        'total_sessions_today': lit_today + num_today,
        'total_sessions_this_week': lit_week + num_week,
        'total_sessions_this_month': lit_month + num_month,
        'active_youth_today': len(today_youth_uids),
        'active_youth_this_week': len(active_youth_week_uids),
        'total_active_youth': total_active_youth,
        'inactive_youth_2_days': inactive_count,
        'schools_covered_today': len(today_school_uids),
        'total_schools': total_schools,
        'avg_sessions_per_youth_this_week': avg_sessions,
        'literacy_sessions': lit_qs.count(),
        'numeracy_sessions': num_qs.count(),
    })


@api_view(['GET'])
@authentication_classes(AUTH_CLASSES)
@permission_classes(PERM_CLASSES)
def youth_sessions_daily_activity(request):
    """Stacked bar chart data: daily session counts grouped by school type."""
    params = request.query_params
    lit_qs, num_qs = _get_session_querysets(params)

    today = timezone.now().date()
    if not params.get('date_from'):
        lit_qs = lit_qs.filter(session_date__gte=today - timedelta(days=30))
        num_qs = num_qs.filter(session_date__gte=today - timedelta(days=30))

    def _agg(qs):
        return qs.filter(school__isnull=False).values(
            'session_date', 'school__type'
        ).annotate(count=Count('id'))

    pivot = defaultdict(lambda: defaultdict(int))
    for row in chain(_agg(lit_qs), _agg(num_qs)):
        d = str(row['session_date'])
        school_type = row['school__type'] or 'Other'
        if 'primary' in school_type.lower():
            key = 'primary_school'
        elif 'ecd' in school_type.lower() or 'ecdc' in school_type.lower():
            key = 'ecd'
        else:
            key = 'other'
        pivot[d][key] += row['count']

    range_from = date.fromisoformat(params['date_from']) if params.get('date_from') else today - timedelta(days=30)
    range_to = date.fromisoformat(params['date_to']) if params.get('date_to') else today

    data = []
    d = range_from
    while d <= range_to:
        iso = str(d)
        entry = pivot.get(iso, {})
        primary = entry.get('primary_school', 0)
        ecd = entry.get('ecd', 0)
        other = entry.get('other', 0)
        data.append({
            'date': iso,
            'primary_school': primary,
            'ecd': ecd,
            'other': other,
            'total': primary + ecd + other,
        })
        d += timedelta(days=1)

    return Response({'data': data})


@api_view(['GET'])
@authentication_classes(AUTH_CLASSES)
@permission_classes(PERM_CLASSES)
def youth_sessions_heatmap(request):
    """Youth x date heatmap of daily session counts."""
    params = request.query_params
    lit_qs, num_qs = _get_session_querysets(params)

    today = timezone.now().date()

    if not params.get('date_from'):
        working_days = _last_n_working_days(10, today)
    else:
        d_from = date.fromisoformat(params['date_from'])
        d_to = date.fromisoformat(params.get('date_to', str(today)))
        working_days = _get_working_days(d_from, d_to)

    if working_days:
        lit_qs = lit_qs.filter(session_date__in=working_days)
        num_qs = num_qs.filter(session_date__in=working_days)

    def _agg(qs):
        return qs.values('youth_uid', 'session_date').annotate(count=Count('id'))

    youth_data = defaultdict(lambda: defaultdict(int))
    for row in chain(_agg(lit_qs), _agg(num_qs)):
        uid = row['youth_uid']
        if uid:
            youth_data[uid][str(row['session_date'])] += row['count']

    max_date = working_days[-1] if working_days else None
    active_youth = list(
        _active_youth_qs(params, reference_date=max_date).select_related('mentor', 'school')
    )

    # Per-youth open working days in the window: weekdays minus closures and the
    # youth's absences, clipped to their start_date.
    window_start = working_days[0] if working_days else today
    window_end = working_days[-1] if working_days else today
    open_by_id = open_working_days_bulk(active_youth, window_start, window_end)
    open_by_uid = {y.youth_uid: open_by_id.get(y.id, set()) for y in active_youth if y.youth_uid}

    youth_info = {
        y.youth_uid: {
            'full_name': y.full_name or f"{y.first_names} {y.last_name}",
            'mentor_name': y.mentor.name if y.mentor else 'Unassigned',
            'start_date': y.start_date,
        }
        for y in active_youth if y.youth_uid
    }

    # Exclude active youth who haven't started yet (start_date after the window).
    # _active_youth_qs already filters this at the DB level when reference_date is set;
    # this remains as a safety net for any uids that came in via youth_data only.
    not_yet_started = {
        uid for uid, info in youth_info.items()
        if max_date and info['start_date'] and info['start_date'] > max_date
    }
    for uid in not_yet_started:
        youth_info.pop(uid, None)

    # Only include currently-active L/N coaches. Sessions from youth no longer
    # in _active_youth_qs (resigned, Inactive, or sync mismatch) used to leak in
    # via youth_data.keys() and render as "YTH-XXXX / Unknown" rows.
    all_uids = set(youth_info.keys()) - not_yet_started
    date_strs = [str(d) for d in working_days]

    result = []
    for uid in all_uids:
        info = youth_info[uid]
        daily_counts = [youth_data[uid].get(d, 0) for d in date_strs]
        open_set = open_by_uid.get(uid, set())
        # expected[i] == was this youth expected to work on working_days[i]?
        expected = [d in open_set for d in working_days]
        total_active_days = sum(1 for c in daily_counts if c > 0)
        total_sessions = sum(daily_counts)
        start_date = info.get('start_date')
        # Denominator = days actually expected (weekdays minus closures/absences,
        # clipped to start_date), not every weekday in the window.
        eligible_days = len(open_set)
        result.append({
            'youth_uid': uid,
            'full_name': info['full_name'],
            'mentor_name': info['mentor_name'],
            'start_date': start_date.isoformat() if start_date else None,
            'daily_counts': daily_counts,
            'expected': expected,
            'total_active_days': total_active_days,
            'total_sessions': total_sessions,
            'eligible_days': eligible_days,
        })

    result.sort(key=lambda x: (x['total_active_days'], x['total_sessions']))

    return Response({
        'dates': date_strs,
        'youth': result,
    })


@api_view(['GET'])
@authentication_classes(AUTH_CLASSES)
@permission_classes(PERM_CLASSES)
def youth_sessions_inactive(request):
    """Active youth with no sessions in their last N *expected* working days
    (closures and personal absences don't count against them)."""
    params = request.query_params
    days = int(params.get('days', 2))

    today = timezone.now().date()

    active_youth, open_by_id, sess_dates = _inactivity_state(params, days, today)
    inactive_youth = [
        y for y in active_youth
        if y.youth_uid and _is_inactive(y, open_by_id, sess_dates, days)
    ]
    inactive_uids = [y.youth_uid for y in inactive_youth]

    last_lit = dict(
        LiteracySession2026.objects.filter(
            youth_uid__in=inactive_uids
        ).values('youth_uid').annotate(last=Max('session_date')).values_list('youth_uid', 'last')
    )
    last_num = dict(
        NumeracySession2026.objects.filter(
            youth_uid__in=inactive_uids
        ).values('youth_uid').annotate(last=Max('session_date')).values_list('youth_uid', 'last')
    )

    month_start = today.replace(day=1)
    month_lit = dict(
        LiteracySession2026.objects.filter(
            youth_uid__in=inactive_uids, session_date__gte=month_start
        ).values('youth_uid').annotate(c=Count('id')).values_list('youth_uid', 'c')
    )
    month_num = dict(
        NumeracySession2026.objects.filter(
            youth_uid__in=inactive_uids, session_date__gte=month_start
        ).values('youth_uid').annotate(c=Count('id')).values_list('youth_uid', 'c')
    )

    result = []
    for y in inactive_youth:
        uid = y.youth_uid
        lit_last = last_lit.get(uid)
        num_last = last_num.get(uid)
        last_session = max(filter(None, [lit_last, num_last]), default=None)
        if last_session:
            calendar_days_inactive = (today - last_session).days
            # OPEN working days (excluding closures + this youth's absences) strictly
            # after last_session through today -- over the full gap, not just the
            # recent inactivity lookback window.
            working_days_inactive = working_days_count(
                y.school, last_session + timedelta(days=1), today, youth=y,
            )
        else:
            calendar_days_inactive = None
            working_days_inactive = None

        result.append({
            'youth_uid': uid,
            'full_name': y.full_name or f"{y.first_names} {y.last_name}",
            'mentor_name': y.mentor.name if y.mentor else 'Unassigned',
            'school_name': y.school.name if y.school else 'Unassigned',
            'last_session_date': str(last_session) if last_session else None,
            'calendar_days_inactive': calendar_days_inactive,
            'working_days_inactive': working_days_inactive,
            'total_sessions_this_month': month_lit.get(uid, 0) + month_num.get(uid, 0),
        })

    result.sort(key=lambda x: -(x['working_days_inactive'] or 0))

    return Response({'inactive_youth': result})


@api_view(['GET'])
@authentication_classes(AUTH_CLASSES)
@permission_classes(PERM_CLASSES)
def youth_sessions_school_coverage(request):
    """Schools with/without sessions in the date range."""
    params = request.query_params
    lit_qs, num_qs = _get_session_querysets(params)

    today = timezone.now().date()
    if not params.get('date_from'):
        week_start = today - timedelta(days=today.weekday())
        lit_qs = lit_qs.filter(session_date__gte=week_start)
        num_qs = num_qs.filter(session_date__gte=week_start)

    def _covered(qs):
        return qs.filter(school__isnull=False).values(
            'school__school_uid', 'school__name', 'school__type'
        ).annotate(
            session_count=Count('id'),
            youth_count=Count('youth_uid', distinct=True),
        )

    covered_map = {}
    for row in chain(_covered(lit_qs), _covered(num_qs)):
        uid = row['school__school_uid']
        if uid not in covered_map:
            covered_map[uid] = {
                'school_uid': uid,
                'name': row['school__name'],
                'type': row['school__type'] or 'Unknown',
                'session_count': 0,
                'youth_count': 0,
            }
        covered_map[uid]['session_count'] += row['session_count']
        covered_map[uid]['youth_count'] = max(covered_map[uid]['youth_count'], row['youth_count'])

    covered = sorted(covered_map.values(), key=lambda x: -x['session_count'])

    # Schools that have ever had sessions but not in this range
    all_session_school_uids = set(
        LiteracySession2026.objects.filter(school_uid__isnull=False).values_list('school_uid', flat=True).distinct()
    ) | set(
        NumeracySession2026.objects.filter(school_uid__isnull=False).values_list('school_uid', flat=True).distinct()
    )
    uncovered_uids = all_session_school_uids - set(covered_map.keys())

    last_lit = dict(
        LiteracySession2026.objects.filter(
            school_uid__in=uncovered_uids
        ).values('school_uid').annotate(last=Max('session_date')).values_list('school_uid', 'last')
    )
    last_num = dict(
        NumeracySession2026.objects.filter(
            school_uid__in=uncovered_uids
        ).values('school_uid').annotate(last=Max('session_date')).values_list('school_uid', 'last')
    )

    uncovered = []
    for s in School.objects.filter(school_uid__in=uncovered_uids):
        lit_last = last_lit.get(s.school_uid)
        num_last = last_num.get(s.school_uid)
        last_session = max(filter(None, [lit_last, num_last]), default=None)
        uncovered.append({
            'school_uid': s.school_uid,
            'name': s.name,
            'type': s.type or 'Unknown',
            'last_session_date': str(last_session) if last_session else None,
        })

    uncovered.sort(key=lambda x: x['name'])

    return Response({'covered': covered, 'uncovered': uncovered})


@api_view(['GET'])
@authentication_classes(AUTH_CLASSES)
@permission_classes(PERM_CLASSES)
def youth_sessions_detail(request, youth_uid):
    """Individual youth drilldown."""
    params = request.query_params
    today = timezone.now().date()
    month_start = today.replace(day=1)

    try:
        youth = Youth.objects.select_related('mentor', 'school').get(youth_uid=youth_uid)
    except Youth.DoesNotExist:
        return Response({'error': 'Youth not found'}, status=404)

    lit_qs = LiteracySession2026.objects.filter(youth_uid=youth_uid)
    num_qs = NumeracySession2026.objects.filter(youth_uid=youth_uid)

    date_from = params.get('date_from')
    date_to = params.get('date_to')

    default_from = today - timedelta(days=30)
    daily_from = date.fromisoformat(date_from) if date_from else default_from
    daily_to = date.fromisoformat(date_to) if date_to else today

    lit_filtered = lit_qs.filter(session_date__gte=daily_from, session_date__lte=daily_to)
    num_filtered = num_qs.filter(session_date__gte=daily_from, session_date__lte=daily_to)

    total_sessions = lit_filtered.count() + num_filtered.count()
    total_month = (
        lit_qs.filter(session_date__gte=month_start).count()
        + num_qs.filter(session_date__gte=month_start).count()
    )

    lit_daily = dict(
        lit_filtered.values('session_date').annotate(c=Count('id')).values_list('session_date', 'c')
    )
    num_daily = dict(
        num_filtered.values('session_date').annotate(c=Count('id')).values_list('session_date', 'c')
    )

    working_days = _get_working_days(daily_from, daily_to)
    open_days = open_working_days_bulk([youth], daily_from, daily_to).get(youth.id, set())
    daily_sessions = []
    days_with_sessions = 0
    for d in working_days:
        lit_c = lit_daily.get(d, 0)
        num_c = num_daily.get(d, 0)
        if lit_c + num_c > 0:
            days_with_sessions += 1
        daily_sessions.append({
            'date': str(d), 'literacy': lit_c, 'numeracy': num_c,
            'expected': d in open_days,
        })

    # Expected working days = weekdays minus closures and this youth's absences.
    total_working_days = len(open_days)
    avg_per_day = round(total_sessions / days_with_sessions, 1) if days_with_sessions else 0

    # Children worked with — bounded to the same daily_from/daily_to window
    child_uids = set()
    for s in lit_filtered:
        if s.child_uid_1:
            child_uids.add(s.child_uid_1)
        if s.child_uid_2:
            child_uids.add(s.child_uid_2)
    for s in num_filtered:
        if s.child_uids:
            child_uids.update(s.child_uids)

    return Response({
        'youth_uid': youth_uid,
        'full_name': youth.full_name or f"{youth.first_names} {youth.last_name}",
        'mentor_name': youth.mentor.name if youth.mentor else 'Unassigned',
        'school_name': youth.school.name if youth.school else 'Unassigned',
        'start_date': youth.start_date.isoformat() if youth.start_date else None,
        'total_sessions': total_sessions,
        'total_sessions_this_month': total_month,
        'avg_sessions_per_day': avg_per_day,
        'days_with_no_sessions': max(total_working_days - days_with_sessions, 0),
        'total_working_days': total_working_days,
        'children_worked_with': len(child_uids),
        'daily_sessions': daily_sessions,
    })


@api_view(['GET'])
@authentication_classes(AUTH_CLASSES)
@permission_classes(PERM_CLASSES)
def youth_sessions_lookups(request):
    """Filter dropdown data: youth, schools, mentors."""
    youth_list = [
        {
            'youth_uid': y['youth_uid'],
            'full_name': y['full_name'] or f"{y['first_names']} {y['last_name']}",
        }
        for y in Youth.objects.filter(
            employment_status='Active',
            job_title__in=INCLUDED_JOB_TITLES,
        ).order_by('full_name').values('youth_uid', 'full_name', 'first_names', 'last_name')
        if y['youth_uid']
    ]

    school_list = [
        {'school_uid': s['school_uid'], 'name': s['name'], 'type': s['type'] or 'Unknown'}
        for s in School.objects.filter(is_active=True).order_by('name').values('school_uid', 'name', 'type')
        if s['school_uid']
    ]

    # Only return mentors actually assigned to active youth with included job titles
    active_mentor_ids = Youth.objects.filter(
        employment_status='Active',
        job_title__in=INCLUDED_JOB_TITLES,
        mentor__isnull=False,
    ).values_list('mentor_id', flat=True).distinct()
    mentor_list = list(
        Mentor.objects.filter(id__in=active_mentor_ids).order_by('name').values('id', 'name')
    )

    return Response({
        'youth': youth_list,
        'schools': school_list,
        'mentors': mentor_list,
    })
