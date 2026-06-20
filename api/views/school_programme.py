"""School Programme Grid endpoints.

Reads are open to any authenticated user; writes (cell edits, demographics,
year-rollover) are restricted to ADMIN / PROJECT MANAGER -- these cells become
official grant/impact numbers (plan section 3). Thin views over
api.school_programme; each write runs in a transaction so the dependent-rollup
recompute is atomic with the edit.
"""
from django.db import transaction
from django.utils import timezone
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import (
    api_view, authentication_classes, permission_classes,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..authentication import ClerkAuthentication
from ..permissions import IsAdminOrProjectManager
from ..models import SchoolProgrammeYear, SchoolYearStats
from .. import school_programme

AUTH_CLASSES = [SessionAuthentication, ClerkAuthentication]


@api_view(['GET'])
@authentication_classes(AUTH_CLASSES)
@permission_classes([IsAuthenticated])
def school_programme_grid(request):
    """The pivoted grid for a year (schools x programmes + school-level stats)."""
    year = int(request.query_params.get('year') or timezone.now().year)
    return Response(school_programme.build_grid(year))


@api_view(['POST'])
@authentication_classes(AUTH_CLASSES)
@permission_classes([IsAdminOrProjectManager])
def create_grid_cell(request):
    """Declare a programme at a school for a year (the "click to add" path).
    Body: {school_uid, programme, year}. Returns the new cell in the grid-read
    shape at 201 (idempotent: an existing cell is returned 201 unchanged)."""
    try:
        with transaction.atomic():
            row = school_programme.create_cell(
                request.data.get('school_uid'),
                request.data.get('programme'),
                request.data.get('year'),
                request.user,
            )
    except ValueError as exc:
        return Response({'detail': str(exc)}, status=400)
    return Response(school_programme.serialize_cell(row), status=201)


@api_view(['PATCH', 'DELETE'])
@authentication_classes(AUTH_CLASSES)
@permission_classes([IsAdminOrProjectManager])
def update_grid_cell(request, pk):
    """PATCH edits a manual programme cell (children_count for manual programmes,
    percent_of_school, youth_planned); editing a computed cell is rejected.
    DELETE removes an accidental empty cell (a data-bearing cell is refused)."""
    if request.method == 'DELETE':
        try:
            with transaction.atomic():
                school_programme.delete_cell(pk, request.user)
        except SchoolProgrammeYear.DoesNotExist:
            return Response({'detail': 'Cell not found.'}, status=404)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response(status=204)

    try:
        with transaction.atomic():
            row = school_programme.apply_cell_edit(pk, request.data, request.user)
    except SchoolProgrammeYear.DoesNotExist:
        return Response({'detail': 'Cell not found.'}, status=404)
    except ValueError as exc:
        return Response({'detail': str(exc)}, status=400)
    return Response({
        'id': row.id,
        'children_count': row.children_count,
        'percent_of_school': row.percent_of_school,
        'youth_planned': row.youth_planned,
    })


@api_view(['PATCH'])
@authentication_classes(AUTH_CLASSES)
@permission_classes([IsAdminOrProjectManager])
def update_grid_stats(request, pk):
    """Edit a school's year-stats (enrolment + race estimates). Editing
    total_kids_in_school recomputes unique_beneficiaries in the same transaction."""
    try:
        with transaction.atomic():
            stats = school_programme.apply_stats_edit(pk, request.data, request.user)
    except SchoolYearStats.DoesNotExist:
        return Response({'detail': 'Stats not found.'}, status=404)
    return Response(school_programme.serialize_year_stats(stats))


@api_view(['POST'])
@authentication_classes(AUTH_CLASSES)
@permission_classes([IsAdminOrProjectManager])
def rollover_grid(request):
    """Copy a year's grid structure forward, counts blank (year-rollover)."""
    try:
        from_year = int(request.data['from_year'])
        to_year = int(request.data['to_year'])
    except (KeyError, TypeError, ValueError):
        return Response(
            {'detail': 'from_year and to_year (integers) are required.'}, status=400
        )
    with transaction.atomic():
        result = school_programme.rollover_grid(from_year, to_year)
    return Response(result)
