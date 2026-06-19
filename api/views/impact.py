import requests
from rest_framework import permissions
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response

from ..models import PublishedStat
from ..zazi_client import fetch_zazi_programmatic_impact


@api_view(['GET'])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
def published_stats(request):
    """Public, aggregate-only stats for the donor-facing impact pages."""
    rows = PublishedStat.objects.filter(is_published=True).order_by('group', 'sort_order')
    stats = {}
    groups = {}
    verified_through = None

    for row in rows:
        stats[row.key] = {
            'key': row.key,
            'value': row.value,
            'numeric_value': row.numeric_value,
            'numeric_value_secondary': row.numeric_value_secondary,
            'label': row.label,
            'description': row.description,
            'source_system': row.source_system,
            'population': row.population,
            'comparison_type': row.comparison_type,
            'as_of': row.as_of.isoformat(),
            'methodology_note': row.methodology_note,
            'group': row.group,
            'sort_order': row.sort_order,
        }
        if row.group:
            groups.setdefault(row.group, []).append(row.key)
        if verified_through is None or row.as_of.isoformat() > verified_through:
            verified_through = row.as_of.isoformat()

    return Response({'stats': stats, 'groups': groups, 'verified_through': verified_through})


@api_view(['GET'])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
def zazi_programmatic(request):
    """Public proxy for the Zazi Programmatic-impact payload (Impact Data Portal).

    Calls the separate Zazi backend server-side with the shared secret (the house
    pattern: the frontend only talks to the Masi backend) and passes the verified
    payload through. The data is aggregate and funder-facing, so this is public;
    the frontend's ISR layer caches it and keeps the last-good copy if Zazi is
    briefly unreachable.
    """
    try:
        payload = fetch_zazi_programmatic_impact()
    except requests.RequestException as exc:
        return Response(
            {'error': 'Zazi backend unavailable', 'detail': str(exc)},
            status=503,
        )
    return Response(payload)
