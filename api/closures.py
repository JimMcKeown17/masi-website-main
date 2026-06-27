"""Working-days resolution for the closure calendar.

The single place the per-day denominator logic asks "was this school open, and
was this coach expected, on day D". Resolution is most-specific-wins via a
discriminated ``scope_key`` (school > region > type > global). Because
SchoolClosure has a unique ``(date, scope_key)`` constraint, at most one row
exists per scope per day, so the most-specific matching row is unambiguous; an
``is_open=True`` row at a more specific scope overrides a broader closure (e.g. a
school that works on a public holiday).
"""
from datetime import timedelta

# The canonical-key helpers live on the models module so SchoolClosure.save()
# can derive scope_key without importing this module (which imports models).
from .models import (
    SchoolClosure, StaffAbsence,
    canonical_school_type, normalize_region, build_scope_key,
)


def scope_keys_for_school(school):
    """Scope keys that can apply to this school, most specific first."""
    if school is None:
        return ['global']
    keys = []
    if school.school_uid:
        keys.append(f'school:{school.school_uid}')
    region = normalize_region(school.suburb)
    if region:
        keys.append(f'region:{region}')
    keys.append(f'type:{canonical_school_type(school.type)}')
    keys.append('global')
    return keys


def _weekdays(start, end):
    d = start
    while d <= end:
        if d.weekday() < 5:  # Mon-Fri
            yield d
        d += timedelta(days=1)


def _closed_dates(school, start, end):
    """Weekday dates in [start, end] where this school's place is closed."""
    keys = scope_keys_for_school(school)
    rank = {k: i for i, k in enumerate(keys)}
    winner = {}  # date -> (rank, is_open)  -- lower rank = more specific
    rows = SchoolClosure.objects.filter(
        date__gte=start, date__lte=end, scope_key__in=keys,
    ).values('date', 'scope_key', 'is_open')
    for r in rows:
        rk = rank[r['scope_key']]
        cur = winner.get(r['date'])
        if cur is None or rk < cur[0]:
            winner[r['date']] = (rk, r['is_open'])
    return {d for d, (_, is_open) in winner.items() if not is_open}


def _absence_dates(youth, start, end):
    if youth is None or not youth.youth_uid:
        return set()
    return set(
        StaffAbsence.objects
        .filter(youth_uid=youth.youth_uid, date__gte=start, date__lte=end)
        .values_list('date', flat=True)
    )


def is_closed(school, day):
    """True if this school's place is closed on ``day`` (ignores weekend/absence)."""
    return day in _closed_dates(school, day, day)


def open_working_days(school, start, end, *, since=None, youth=None):
    """Ordered weekday dates in [start, end] the coach is expected to work:
    Mon-Fri, minus school closures, minus days before ``since`` (e.g. the coach's
    start date), minus this ``youth``'s personal absences."""
    closed = _closed_dates(school, start, end)
    absent = _absence_dates(youth, start, end)
    out = []
    for d in _weekdays(start, end):
        if since is not None and d < since:
            continue
        if d in closed or d in absent:
            continue
        out.append(d)
    return out


def working_days_count(school, start, end, *, since=None, youth=None):
    return len(open_working_days(school, start, end, since=since, youth=youth))


def open_working_days_bulk(coaches, start, end, since_by_id=None):
    """``{youth_id: set(open weekday dates)}`` for many coaches, loading closures
    and absences for the window once. Each coach is clipped to its own
    ``start_date`` and has its own absences subtracted. ``since_by_id`` can
    override that clip date per coach for derived programme-year windows. Pass
    coaches with ``select_related('school')`` to avoid per-coach school queries."""
    coaches = list(coaches)
    weekdays = list(_weekdays(start, end))

    by_key = {}  # scope_key -> {date: is_open}
    for r in SchoolClosure.objects.filter(
        date__gte=start, date__lte=end,
    ).values('date', 'scope_key', 'is_open'):
        by_key.setdefault(r['scope_key'], {})[r['date']] = r['is_open']

    absences = {}  # youth_uid -> set(date)
    uids = [c.youth_uid for c in coaches if c.youth_uid]
    for uid, d in StaffAbsence.objects.filter(
        youth_uid__in=uids, date__gte=start, date__lte=end,
    ).values_list('youth_uid', 'date'):
        absences.setdefault(uid, set()).add(d)

    result = {}
    for coach in coaches:
        keys = scope_keys_for_school(coach.school)
        absent = absences.get(coach.youth_uid, set())
        since = since_by_id.get(coach.id, coach.start_date) if since_by_id else coach.start_date
        open_days = set()
        for d in weekdays:
            if since is not None and d < since:
                continue
            if d in absent:
                continue
            closed = False
            for k in keys:  # most specific first
                day_map = by_key.get(k)
                if day_map is not None and d in day_map:
                    closed = not day_map[d]
                    break
            if not closed:
                open_days.add(d)
        result[coach.id] = open_days
    return result
