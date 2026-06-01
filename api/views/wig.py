"""WIG dashboard endpoints (ADMIN / PROJECT MANAGER only).

Thin views over api.wig_metrics. The Masi-PG programmes (Core Literacy,
Numeracy, ECD) and the Data team are computed here; the Zazi iZandi tile is
served separately (Masi backend calls the Zazi backend API).
"""
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response
from django.utils import timezone

from ..authentication import ClerkAuthentication
from ..permissions import IsAdminOrProjectManager
from ..wig_metrics import build_lead_measures, build_data_quality
from .. import zazi_client

AUTH_CLASSES = [SessionAuthentication, ClerkAuthentication]
PERM_CLASSES = [IsAdminOrProjectManager]


@api_view(['GET'])
@authentication_classes(AUTH_CLASSES)
@permission_classes(PERM_CLASSES)
def wig_lead_measures(request):
    """Lead-measure scoreboard for the last completed week (Masi-PG programmes)."""
    return Response(build_lead_measures(timezone.now()))


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
    """Zazi iZandi tile: served from the cached snapshot.

    The Zazi overview endpoint takes ~10s to compute, so we never call it live on
    a board load. A cron (refresh_zazi_overview) keeps the snapshot fresh; if it
    has never run (e.g. right after deploy) we populate it once, lazily. Degrades
    to {available: False} when there is no usable snapshot.
    """
    from ..models import ZaziOverviewSnapshot

    snap = ZaziOverviewSnapshot.objects.first()
    if snap is None:
        snap = zazi_client.refresh_zazi_snapshot()

    if snap and snap.ok and snap.payload:
        payload = zazi_client.build_zazi_measures(snap.payload)
        payload['available'] = True
        payload['fetched_at'] = snap.fetched_at.isoformat() if snap.fetched_at else None
        return Response(payload)
    return Response({'available': False, 'measures': {}})


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
    return Response(build_wig_detail(programme, measure, timezone.now()))
