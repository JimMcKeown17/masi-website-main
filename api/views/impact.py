from rest_framework import permissions
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response

from ..models import PublishedStat


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
