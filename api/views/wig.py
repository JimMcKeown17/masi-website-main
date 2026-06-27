"""WIG dashboard endpoints (ADMIN / PROJECT MANAGER only).

Thin views over api.wig_metrics. The Masi-PG programmes (Core Literacy,
Numeracy, ECD) and the Data team are computed here; the Zazi iZandi tile is
served separately (Masi backend calls the Zazi backend API).
"""
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone

from ..authentication import ClerkAuthentication
from ..permissions import IsAdminOrProjectManager
from ..wig_metrics import build_lead_measures, build_data_quality, VALID_WIG_PERIODS, WIG_PERIOD_WEEK
from .. import zazi_client

AUTH_CLASSES = [SessionAuthentication, ClerkAuthentication]
PERM_CLASSES = [IsAdminOrProjectManager]


@api_view(['GET'])
@authentication_classes(AUTH_CLASSES)
@permission_classes(PERM_CLASSES)
def wig_lead_measures(request):
    """Lead-measure scoreboard for the requested completed period."""
    period = request.query_params.get('period', WIG_PERIOD_WEEK)
    if period not in VALID_WIG_PERIODS:
        return Response(
            {'detail': 'Invalid period. Use week, month, or programme_year.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(build_lead_measures(timezone.now(), period=period))


@api_view(['GET'])
@authentication_classes(AUTH_CLASSES)
@permission_classes(PERM_CLASSES)
def wig_data_quality(request):
    """Data-team accuracy sub-gauges over the full dataset."""
    return Response(build_data_quality())


@api_view(['GET'])
@authentication_classes(AUTH_CLASSES)
@permission_classes(PERM_CLASSES)
def wig_zazi(request):
    """Zazi iZandi tiles (Primary + ECD): served from cached snapshots.

    The Zazi overview endpoint takes ~10s to compute, so we never call it live on
    a board load. A cron (refresh_zazi_overview) keeps one snapshot per cohort
    fresh; if a cohort has never been fetched (e.g. right after deploy) we
    populate it once, lazily. Each segment degrades independently to unavailable.
    """
    from ..models import ZaziOverviewSnapshot
    from ..zazi_client import ZAZI_SEGMENTS

    measures = {}
    available = {}
    fetched_at = {}
    for prog_key, cohort, prefix in ZAZI_SEGMENTS:
        snap = ZaziOverviewSnapshot.objects.filter(cohort=cohort).first()
        if snap is None:
            snap = zazi_client.refresh_zazi_snapshot(cohort)
        if snap and snap.ok and snap.payload:
            measures.update(zazi_client.build_zazi_measures(snap.payload, prefix=prefix)['measures'])
            available[prog_key] = True
            fetched_at[prog_key] = snap.fetched_at.isoformat() if snap.fetched_at else None
        else:
            available[prog_key] = False
    return Response({'available': available, 'measures': measures, 'fetched_at': fetched_at})


@api_view(['GET'])
@authentication_classes(AUTH_CLASSES)
@permission_classes(PERM_CLASSES)
def wig_detail(request):
    """Drill-down data behind a single measure: GET ?programme=&measure=.

    Dispatches by measure key to the right builder (session heatmap, school
    coverage, visit table, or a data-quality record table) and returns a
    discriminated {'kind': ...} payload. Unknown measures return {'kind': 'none'}.
    """
    from ..wig_detail import build_wig_detail

    programme = request.query_params.get('programme', '')
    measure = request.query_params.get('measure', '')
    period = request.query_params.get('period', WIG_PERIOD_WEEK)
    if period not in VALID_WIG_PERIODS:
        return Response(
            {'detail': 'Invalid period. Use week, month, or programme_year.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return Response(build_wig_detail(programme, measure, timezone.now(), period=period))
