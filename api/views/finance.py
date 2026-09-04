"""Finance dashboard endpoints (ADMIN only until capability grants ship).

Serves the finance snapshot masi-finance published and load_finance_snapshot
stored. Read-only; the workbook is never read here.
"""
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response

from ..authentication import ClerkAuthentication
from ..models import FinanceSnapshot
from ..permissions import IsFinanceReader

AUTH_CLASSES = [SessionAuthentication, ClerkAuthentication]
PERM_CLASSES = [IsFinanceReader]


@api_view(["GET"])
@authentication_classes(AUTH_CLASSES)
@permission_classes(PERM_CLASSES)
def finance_snapshot(request):
    """The published snapshot for ?year=, defaulting to the latest published year."""
    raw_year = request.query_params.get("year")
    years = list(FinanceSnapshot.objects.order_by("-accounting_year").values_list("accounting_year", flat=True))
    if raw_year in (None, ""):
        if not years:
            return Response({"detail": "No finance snapshot has been published."}, status=404)
        year = years[0]
    else:
        try:
            year = int(raw_year)
        except ValueError:
            return Response({"detail": "year must be an integer."}, status=400)
    row = FinanceSnapshot.objects.filter(accounting_year=year).first()
    if row is None:
        return Response({"detail": f"No finance snapshot has been published for {year}."}, status=404)
    return Response({
        "accounting_year": row.accounting_year,
        "run_id": row.run_id,
        "workbook_name": row.workbook_name,
        "workbook_date": row.workbook_date.isoformat(),
        "workbook_modified_at": row.workbook_modified_at.isoformat().replace("+00:00", "Z"),
        "workbook_sha256": row.workbook_sha256,
        "published_at": row.published_at.isoformat().replace("+00:00", "Z"),
        "loaded_at": row.loaded_at.isoformat(),
        "available_years": years,
        "snapshot": row.payload,
    })
