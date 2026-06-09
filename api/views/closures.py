"""Closure calendar API: school closures + staff absences.

Authoring CRUD and bulk fan-out are gated to ADMIN / PROJECT MANAGER. The export
endpoints carry no user identity -- they are gated only by the X-Internal-Auth
shared secret, which the Zazi backend sends when pulling the calendar.
"""
from datetime import date as date_cls, timedelta

from rest_framework import generics, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response

from ..authentication import ClerkAuthentication
from ..permissions import IsAdminOrProjectManager, IsInternalService
from ..models import SchoolClosure, StaffAbsence, School, Youth
from ..serializers import SchoolClosureSerializer, StaffAbsenceSerializer
from .. import closures as closures_svc

AUTH = [SessionAuthentication, ClerkAuthentication]
PERM = [IsAdminOrProjectManager]

_CANONICAL_TYPES = {'primary', 'ecd', 'secondary', 'other'}


def _parse_date(value):
    try:
        return date_cls.fromisoformat(value) if value else None
    except (TypeError, ValueError):
        return None


def _weekdays(start, end):
    d = start
    while d <= end:
        if d.weekday() < 5:
            yield d
        d += timedelta(days=1)


def _request_user(request):
    user = getattr(request, 'user', None)
    return user if (user and user.is_authenticated) else None


# ---------------------------------------------------------------------------
# School closures
# ---------------------------------------------------------------------------
class ClosureListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = SchoolClosureSerializer
    authentication_classes = AUTH
    permission_classes = PERM

    def get_queryset(self):
        qs = SchoolClosure.objects.select_related('scope_school').all()
        p = self.request.query_params
        df, dt = _parse_date(p.get('date_from')), _parse_date(p.get('date_to'))
        if df:
            qs = qs.filter(date__gte=df)
        if dt:
            qs = qs.filter(date__lte=dt)
        if p.get('scope_type'):
            qs = qs.filter(scope_type=p['scope_type'])
        if p.get('source'):
            qs = qs.filter(source=p['source'])
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=_request_user(self.request), source='manual')


class ClosureDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = SchoolClosure.objects.select_related('scope_school').all()
    serializer_class = SchoolClosureSerializer
    authentication_classes = AUTH
    permission_classes = PERM


@api_view(['GET'])
@authentication_classes(AUTH)
@permission_classes(PERM)
def closures_lookups(request):
    """Dropdown data for the closure-calendar UI: active schools (with uid,
    normalised suburb, canonical type), the distinct suburbs, the canonical
    school types, and active youth."""
    schools = (
        School.objects.filter(is_active=True)
        .exclude(school_uid__isnull=True).exclude(school_uid='')
        .order_by('name')
    )
    school_rows = [{
        'school_uid': s.school_uid,
        'name': s.name,
        'suburb': closures_svc.normalize_region(s.suburb) or None,
        'canonical_type': closures_svc.canonical_school_type(s.type),
    } for s in schools]
    suburbs = sorted({r['suburb'] for r in school_rows if r['suburb']})
    youth = (
        Youth.objects.filter(employment_status='Active')
        .exclude(youth_uid__isnull=True).exclude(youth_uid='')
        .order_by('first_names', 'last_name')
    )
    youth_rows = [{
        'youth_uid': y.youth_uid,
        'name': y.full_name or f'{y.first_names} {y.last_name}'.strip(),
    } for y in youth]
    return Response({
        'schools': school_rows,
        'suburbs': suburbs,
        'school_types': [
            {'value': 'primary', 'label': 'Primary'},
            {'value': 'ecd', 'label': 'ECD'},
            {'value': 'secondary', 'label': 'Secondary'},
            {'value': 'other', 'label': 'Other'},
        ],
        'youth': youth_rows,
    })


def _closure_scope_kwargs(scope_type, value):
    """Return (model field kwargs, scope_key) for one (scope_type, value)."""
    if scope_type == 'global':
        return {}, 'global'
    if scope_type == 'type':
        if value not in _CANONICAL_TYPES:
            raise ValueError(f'invalid school type: {value!r}')
        return ({'scope_school_type': value},
                closures_svc.build_scope_key('type', canonical_type=value))
    if scope_type == 'region':
        norm = closures_svc.normalize_region(value)
        if not norm:
            raise ValueError('a region (suburb) is required')
        return ({'scope_region': norm},
                closures_svc.build_scope_key('region', region=norm))
    if scope_type == 'school':
        school = School.objects.filter(school_uid=value).first()
        if not school:
            raise ValueError(f'unknown school_uid: {value!r}')
        return ({'scope_school': school},
                closures_svc.build_scope_key('school', school_uid=school.school_uid))
    raise ValueError(f'unknown scope_type: {scope_type!r}')


@api_view(['POST'])
@authentication_classes(AUTH)
@permission_classes(PERM)
def closures_bulk(request):
    """Fan out one closure per (scope_value x weekday) in [date_from, date_to].

    Body: {date_from, date_to, scope_type, scope_values?[], is_open?, reason?}.
    scope_values is omitted for global; a list of canonical types, suburbs, or
    school_uids otherwise. Idempotent on (date, scope_key).
    """
    data = request.data
    start = _parse_date(data.get('date_from'))
    end = _parse_date(data.get('date_to'))
    scope_type = data.get('scope_type')
    if not start or not end or end < start:
        return Response({'detail': 'date_from and date_to (date_from <= date_to) are required.'},
                        status=status.HTTP_400_BAD_REQUEST)
    if scope_type not in {'global', 'type', 'region', 'school'}:
        return Response({'detail': 'invalid scope_type.'}, status=status.HTTP_400_BAD_REQUEST)
    values = data.get('scope_values') or [None]
    is_open = bool(data.get('is_open', False))
    reason = data.get('reason', '') or ''
    user = _request_user(request)

    created = updated = 0
    for value in values:
        try:
            fields, scope_key = _closure_scope_kwargs(scope_type, value)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        for day in _weekdays(start, end):
            _, was_created = SchoolClosure.objects.update_or_create(
                date=day, scope_key=scope_key,
                defaults={'scope_type': scope_type, 'is_open': is_open,
                          'reason': reason, 'source': 'manual', 'created_by': user,
                          **fields},
            )
            created += int(was_created)
            updated += int(not was_created)
    return Response({'created': created, 'updated': updated}, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([IsInternalService])
def closures_export(request):
    """Bounded-window closure feed for the Zazi backend (shared-secret only)."""
    p = request.query_params
    qs = SchoolClosure.objects.select_related('scope_school').all()
    df, dt = _parse_date(p.get('date_from')), _parse_date(p.get('date_to'))
    if df:
        qs = qs.filter(date__gte=df)
    if dt:
        qs = qs.filter(date__lte=dt)
    if p.get('since'):
        qs = qs.filter(updated_at__gte=p['since'])
    rows = [{
        'id': c.id,
        'date': c.date,
        'scope_key': c.scope_key,
        'scope_type': c.scope_type,
        'scope_school_type': c.scope_school_type,
        'scope_region': c.scope_region,
        'school_uid': c.scope_school.school_uid if c.scope_school_id else None,
        'is_open': c.is_open,
        'source': c.source,
        'reason': c.reason,
        'updated_at': c.updated_at,
    } for c in qs]
    return Response(rows)


# ---------------------------------------------------------------------------
# Staff absences
# ---------------------------------------------------------------------------
class AbsenceListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = StaffAbsenceSerializer
    authentication_classes = AUTH
    permission_classes = PERM

    def get_queryset(self):
        qs = StaffAbsence.objects.select_related('youth').all()
        p = self.request.query_params
        df, dt = _parse_date(p.get('date_from')), _parse_date(p.get('date_to'))
        if df:
            qs = qs.filter(date__gte=df)
        if dt:
            qs = qs.filter(date__lte=dt)
        if p.get('youth_uid'):
            qs = qs.filter(youth_uid=p['youth_uid'])
        return qs

    def perform_create(self, serializer):
        serializer.save(created_by=_request_user(self.request))


class AbsenceDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = StaffAbsence.objects.select_related('youth').all()
    serializer_class = StaffAbsenceSerializer
    authentication_classes = AUTH
    permission_classes = PERM


@api_view(['POST'])
@authentication_classes(AUTH)
@permission_classes(PERM)
def absences_bulk(request):
    """Fan out one absence per (youth x weekday) in [date_from, date_to].
    Body: {youth_uids[], date_from, date_to, reason?, note?}."""
    data = request.data
    start = _parse_date(data.get('date_from'))
    end = _parse_date(data.get('date_to'))
    uids = data.get('youth_uids') or []
    if not start or not end or end < start:
        return Response({'detail': 'date_from and date_to (date_from <= date_to) are required.'},
                        status=status.HTTP_400_BAD_REQUEST)
    if not uids:
        return Response({'detail': 'youth_uids is required.'}, status=status.HTTP_400_BAD_REQUEST)
    reason = data.get('reason', 'other') or 'other'
    note = data.get('note', '') or ''
    user = _request_user(request)
    youths = {y.youth_uid: y for y in Youth.objects.filter(youth_uid__in=uids)}

    created = updated = 0
    for uid in uids:
        youth = youths.get(uid)
        if not youth:
            return Response({'detail': f'unknown youth_uid: {uid}'}, status=status.HTTP_400_BAD_REQUEST)
        for day in _weekdays(start, end):
            _, was_created = StaffAbsence.objects.update_or_create(
                date=day, youth_uid=uid,
                defaults={'youth': youth, 'reason': reason, 'note': note, 'created_by': user},
            )
            created += int(was_created)
            updated += int(not was_created)
    return Response({'created': created, 'updated': updated}, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([IsInternalService])
def absences_export(request):
    """Bounded-window absence feed for the Zazi backend (shared-secret only)."""
    p = request.query_params
    qs = StaffAbsence.objects.all()
    df, dt = _parse_date(p.get('date_from')), _parse_date(p.get('date_to'))
    if df:
        qs = qs.filter(date__gte=df)
    if dt:
        qs = qs.filter(date__lte=dt)
    if p.get('since'):
        qs = qs.filter(updated_at__gte=p['since'])
    rows = [{
        'id': a.id,
        'date': a.date,
        'scope_key': f'youth:{a.youth_uid}',
        'youth_uid': a.youth_uid,
        'reason': a.reason,
        'note': a.note,
        'updated_at': a.updated_at,
    } for a in qs]
    return Response(rows)
