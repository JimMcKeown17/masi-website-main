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
    """Zazi iZandi tile: proxies the Zazi backend's programme overview.

    Degrades to {available: False} if the Zazi API is unreachable, so the tile
    renders 'data unavailable' rather than failing the whole board.
    """
    try:
        overview = zazi_client.fetch_zazi_programme_overview()
    except Exception:
        return Response({'available': False, 'measures': {}})
    payload = zazi_client.build_zazi_measures(overview)
    payload['available'] = True
    return Response(payload)
