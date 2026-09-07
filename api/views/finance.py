"""Approved FinanceRun is the sole source of dashboard snapshots."""
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response

from ..authentication import ClerkAuthentication
from ..finance_snapshot_compat import snapshot_response
from ..models import FinanceRun
from ..permissions import IsFinanceReader

AUTH_CLASSES = [SessionAuthentication, ClerkAuthentication]
PERM_CLASSES = [IsFinanceReader]


@api_view(['GET'])
@authentication_classes(AUTH_CLASSES)
@permission_classes(PERM_CLASSES)
def finance_snapshot(request):
    approved = FinanceRun.objects.filter(kind='funders', status='approved')
    years = list(approved.order_by('-accounting_year').values_list('accounting_year', flat=True))
    raw_year = request.query_params.get('year')
    if raw_year in (None, ''):
        if not years:
            return Response({'detail': 'No finance snapshot has been published.'}, status=404)
        year = years[0]
    else:
        try:
            year = int(raw_year)
        except ValueError:
            return Response({'detail': 'year must be an integer.'}, status=400)
    row = approved.filter(accounting_year=year).first()
    if row is None:
        return Response({'detail': f'No finance snapshot has been published for {year}.'}, status=404)
    return Response(snapshot_response(row, years))
