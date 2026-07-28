"""Youth Budget Calculator endpoints.

Reads are available to authenticated users. Every write is restricted to
ADMIN and PROJECT MANAGER roles and runs inside a database transaction.
"""
from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .. import youth_budget
from ..authentication import ClerkAuthentication
from ..models import (
    BudgetScenario,
    FundingPot,
    MonthlyYouthExpenditure,
    School,
)
from ..permissions import IsAdminOrProjectManager


AUTH_CLASSES = [SessionAuthentication, ClerkAuthentication]
SCENARIO_DECIMAL_FIELDS = {
    "wage_rate",
    "subsidy_contribution",
    "holiday_pay",
    "mentor_reserve",
}
SCENARIO_MONTH_FIELDS = {
    "nys_conversion_start_month",
    "vacancy_start_month",
}


def _number(value):
    return float(value) if value is not None else None


def _iso(value):
    return value.isoformat() if value else None


def _integer(value, field):
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer.")
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be an integer.")
    if str(value).strip() not in {str(parsed), f"+{parsed}"}:
        raise ValueError(f"{field} must be an integer.")
    return parsed


def _nonnegative_decimal(value, field):
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a non-negative number.")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f"{field} must be a non-negative number.")
    if not parsed.is_finite() or parsed < 0:
        raise ValueError(f"{field} must be a non-negative number.")
    return parsed


def _boolean(value, field):
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be true or false.")
    return value


def _date(value, field):
    parsed = parse_date(str(value)) if value is not None else None
    if parsed is None:
        raise ValueError(f"{field} must be an ISO date.")
    return parsed


def _hours_matrix(value):
    if not isinstance(value, dict):
        raise ValueError("hours_matrix must be an object.")
    normalized = {}
    for site_type, titles in value.items():
        if not isinstance(titles, dict):
            raise ValueError("Each hours_matrix site type must be an object.")
        normalized[site_type] = {}
        for job_title, entry in titles.items():
            if not isinstance(entry, dict):
                raise ValueError("Each hours_matrix job title must be an object.")
            unknown = set(entry) - {"hours_per_day", "days_per_week"}
            if unknown:
                raise ValueError(
                    "Hours Matrix entries may contain only hours_per_day and days_per_week."
                )
            normalized_entry = {}
            for field in ("hours_per_day", "days_per_week"):
                if field in entry:
                    normalized_entry[field] = float(
                        _nonnegative_decimal(entry[field], field)
                    )
            normalized[site_type][job_title] = normalized_entry
    return normalized


def _scenario_defaults():
    return youth_budget.default_scenario_values()


def _scenario_year(request):
    raw = request.data.get("year") if hasattr(request, "data") else None
    return _integer(raw or timezone.localdate().year, "year")


def serialize_scenario(scenario):
    return {
        "id": scenario.id,
        "year": scenario.year,
        "wage_rate": _number(scenario.wage_rate),
        "subsidy_contribution": _number(scenario.subsidy_contribution),
        "hours_matrix": scenario.hours_matrix,
        "nys_conversion_count": scenario.nys_conversion_count,
        "nys_subsidy_only_count": scenario.nys_subsidy_only_count,
        "utilisation_pct": scenario.utilisation_pct,
        "nys_conversion_start_month": scenario.nys_conversion_start_month,
        "vacancy_start_month": scenario.vacancy_start_month,
        "holiday_pay": _number(scenario.holiday_pay),
        "mentor_reserve": _number(scenario.mentor_reserve),
        "updated_by": scenario.updated_by,
        "updated_at": _iso(scenario.updated_at),
    }


def serialize_pot(pot):
    # Sort in Python: chaining .order_by() onto a prefetched manager clones the
    # queryset and re-queries, silently defeating prefetch_related.
    schools = sorted(pot.schools.all(), key=lambda school: (school.name, school.id))
    return {
        "id": pot.id,
        "year": pot.year,
        "funder_name": pot.funder_name,
        "amount": _number(pot.amount),
        "as_of": _iso(pot.as_of),
        "note": pot.note,
        "schools": [
            {"id": school.id, "name": school.name}
            for school in schools
        ],
        "is_active": pot.is_active,
        "created_at": _iso(pot.created_at),
        "updated_at": _iso(pot.updated_at),
    }


def serialize_expenditure(row):
    total = row.core_amount + row.mentor_amount + row.rural_amount
    return {
        "id": row.id,
        "year": row.year,
        "month": row.month,
        "core_amount": _number(row.core_amount),
        "mentor_amount": _number(row.mentor_amount),
        "rural_amount": _number(row.rural_amount),
        "total": _number(total),
        "note": row.note,
    }


def serialize_projection(projection):
    return {
        "months": [
            {
                "month": row["month"],
                "school_days": row["school_days"],
                "gross": _number(row["gross"]),
                "uif": _number(row["uif"]),
                "subsidy_relief": _number(row["subsidy_relief"]),
                "net": _number(row["net"]),
            }
            for row in projection["months"]
        ],
        "total": _number(projection["total"]),
        "costed_youth": projection.get("costed_youth", 0),
        "open_posts": projection.get("open_posts", 0),
    }


def serialize_feasibility(rows):
    return [
        {
            "funder_name": row["funder_name"],
            "amount": _number(row["amount"]),
            "projected_at_schools": _number(row["projected_at_schools"]),
            "shortfall": _number(row["shortfall"]),
            "schools": row["schools"],
        }
        for row in rows
    ]


def _schools_from_ids(value):
    if not isinstance(value, list):
        raise ValueError("schools must be a list of school ids.")
    try:
        school_ids = {_integer(item, "school id") for item in value}
    except ValueError:
        raise ValueError("schools must be a list of school ids.")
    schools = list(School.objects.filter(id__in=school_ids))
    found = {school.id for school in schools}
    missing = sorted(school_ids - found)
    if missing:
        raise ValueError(f"Unknown school ids: {missing}.")
    return schools


@api_view(["GET"])
@authentication_classes(AUTH_CLASSES)
@permission_classes([IsAuthenticated])
def youth_budget_summary(request):
    """Return the saved scenario and its current committed and at-plan forecast."""
    try:
        year = _integer(
            request.query_params.get("year") or timezone.localdate().year,
            "year",
        )
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=400)

    as_of = timezone.localdate()
    with transaction.atomic():
        scenario, _created = BudgetScenario.objects.get_or_create(
            year=year,
            defaults=_scenario_defaults(),
        )
    pots = list(
        FundingPot.objects.filter(year=year)
        .prefetch_related("schools")
        .order_by("funder_name", "id")
    )
    active_pots_total = sum(
        (pot.amount for pot in pots if pot.is_active),
        Decimal("0"),
    )
    cohorts = youth_budget.build_cohorts(today=as_of)
    vacancies = youth_budget.build_vacancies(year)
    projections = youth_budget.project(scenario, cohorts, vacancies, as_of)
    feasibility = youth_budget.calculate_feasibility(
        pots,
        projections["at_plan"],
    )
    expenditure = MonthlyYouthExpenditure.objects.filter(year=year).order_by(
        "month",
        "id",
    )

    return Response(
        {
            "year": year,
            "as_of": as_of.isoformat(),
            "pots": [serialize_pot(pot) for pot in pots],
            "pots_total": _number(active_pots_total),
            "scenario": serialize_scenario(scenario),
            "cohorts": cohorts["cohorts"],
            "projections": {
                "committed": serialize_projection(projections["committed"]),
                "at_plan": serialize_projection(projections["at_plan"]),
                "verdict_committed": _number(
                    youth_budget.calculate_verdict(
                        active_pots_total,
                        scenario.mentor_reserve,
                        projections["committed"]["total"],
                    )
                ),
                "verdict_at_plan": _number(
                    youth_budget.calculate_verdict(
                        active_pots_total,
                        scenario.mentor_reserve,
                        projections["at_plan"]["total"],
                    )
                ),
            },
            "expenditure": [
                serialize_expenditure(row)
                for row in expenditure
            ],
            "feasibility": serialize_feasibility(feasibility),
            "notes": cohorts["notes"],
            # Directory for the pot school-restriction picker: pot writes take
            # numeric School ids, which the grid payload (school_uid keyed)
            # cannot supply.
            "school_options": list(
                School.objects.filter(is_active=True)
                .order_by("name", "id")
                .values("id", "name")
            ),
        }
    )


@api_view(["PATCH"])
@authentication_classes(AUTH_CLASSES)
@permission_classes([IsAdminOrProjectManager])
def update_youth_budget_scenario(request):
    """Partially update the shared scenario selected by its year."""
    try:
        year = _scenario_year(request)
        updates = {}
        for field in SCENARIO_DECIMAL_FIELDS:
            if field in request.data:
                updates[field] = _nonnegative_decimal(request.data[field], field)
        if "utilisation_pct" in request.data:
            pct = _integer(request.data["utilisation_pct"], "utilisation_pct")
            if not 1 <= pct <= 120:
                raise ValueError("utilisation_pct must be between 1 and 120.")
            updates["utilisation_pct"] = pct
        if "nys_subsidy_only_count" in request.data:
            count = _integer(
                request.data["nys_subsidy_only_count"],
                "nys_subsidy_only_count",
            )
            if count < 0:
                raise ValueError("nys_subsidy_only_count must be non-negative.")
            updates["nys_subsidy_only_count"] = count
        if "nys_conversion_count" in request.data:
            count = _integer(
                request.data["nys_conversion_count"],
                "nys_conversion_count",
            )
            if count < 0:
                raise ValueError("nys_conversion_count must be non-negative.")
            updates["nys_conversion_count"] = count
        for field in SCENARIO_MONTH_FIELDS:
            if field in request.data:
                month = _integer(request.data[field], field)
                if not 1 <= month <= 12:
                    raise ValueError(f"{field} must be between 1 and 12.")
                updates[field] = month
        if "hours_matrix" in request.data:
            updates["hours_matrix"] = _hours_matrix(request.data["hours_matrix"])
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=400)

    with transaction.atomic():
        scenario, _created = BudgetScenario.objects.get_or_create(
            year=year,
            defaults=_scenario_defaults(),
        )
        for field, value in updates.items():
            setattr(scenario, field, value)
        scenario.updated_by = (
            request.user.get_full_name()
            or request.user.get_username()
        )
        scenario.save()
    return Response(serialize_scenario(scenario))


def _create_pot(data):
    required = {"year", "funder_name", "amount", "as_of"}
    missing = sorted(field for field in required if field not in data)
    if missing:
        raise ValueError(f"Missing required fields: {missing}.")
    funder_name = str(data["funder_name"]).strip()
    if not funder_name:
        raise ValueError("funder_name is required.")
    schools = _schools_from_ids(data.get("schools", []))
    pot = FundingPot.objects.create(
        year=_integer(data["year"], "year"),
        funder_name=funder_name,
        amount=_nonnegative_decimal(data["amount"], "amount"),
        as_of=_date(data["as_of"], "as_of"),
        note=str(data.get("note", "")),
        is_active=_boolean(data.get("is_active", True), "is_active"),
    )
    pot.schools.set(schools)
    return pot


@api_view(["POST"])
@authentication_classes(AUTH_CLASSES)
@permission_classes([IsAdminOrProjectManager])
def create_youth_budget_pot(request):
    """Create a funding pot and set its optional school restriction."""
    try:
        with transaction.atomic():
            pot = _create_pot(request.data)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=400)
    return Response(serialize_pot(pot), status=201)


@api_view(["PATCH", "DELETE"])
@authentication_classes(AUTH_CLASSES)
@permission_classes([IsAdminOrProjectManager])
def update_youth_budget_pot(request, pk):
    """Edit or delete one funding pot."""
    try:
        with transaction.atomic():
            pot = FundingPot.objects.select_for_update().get(pk=pk)
            if request.method == "DELETE":
                pot.delete()
                return Response(status=204)

            if "year" in request.data:
                pot.year = _integer(request.data["year"], "year")
            if "funder_name" in request.data:
                funder_name = str(request.data["funder_name"]).strip()
                if not funder_name:
                    raise ValueError("funder_name cannot be blank.")
                pot.funder_name = funder_name
            if "amount" in request.data:
                pot.amount = _nonnegative_decimal(
                    request.data["amount"],
                    "amount",
                )
            if "as_of" in request.data:
                pot.as_of = _date(request.data["as_of"], "as_of")
            if "note" in request.data:
                pot.note = str(request.data["note"])
            if "is_active" in request.data:
                pot.is_active = _boolean(
                    request.data["is_active"],
                    "is_active",
                )
            schools = None
            if "schools" in request.data:
                schools = _schools_from_ids(request.data["schools"])
            pot.save()
            if schools is not None:
                pot.schools.set(schools)
    except FundingPot.DoesNotExist:
        return Response({"detail": "Funding pot not found."}, status=404)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=400)
    return Response(serialize_pot(pot))


def _expenditure_values(data, partial=False):
    required = {"year", "month"} if not partial else set()
    missing = sorted(field for field in required if field not in data)
    if missing:
        raise ValueError(f"Missing required fields: {missing}.")
    values = {}
    if "year" in data:
        values["year"] = _integer(data["year"], "year")
    if "month" in data:
        month = _integer(data["month"], "month")
        if not 1 <= month <= 12:
            raise ValueError("month must be between 1 and 12.")
        values["month"] = month
    for field in ("core_amount", "mentor_amount", "rural_amount"):
        if field in data:
            values[field] = _nonnegative_decimal(data[field], field)
        elif not partial:
            values[field] = Decimal("0")
    if "note" in data:
        values["note"] = str(data["note"])
    elif not partial:
        values["note"] = ""
    return values


@api_view(["POST"])
@authentication_classes(AUTH_CLASSES)
@permission_classes([IsAdminOrProjectManager])
def create_youth_budget_expenditure(request):
    """Create one actual-expenditure month."""
    try:
        values = _expenditure_values(request.data)
        with transaction.atomic():
            row = MonthlyYouthExpenditure.objects.create(**values)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=400)
    except IntegrityError:
        return Response(
            {"detail": "Expenditure already exists for that year and month."},
            status=400,
        )
    return Response(serialize_expenditure(row), status=201)


@api_view(["PATCH"])
@authentication_classes(AUTH_CLASSES)
@permission_classes([IsAdminOrProjectManager])
def update_youth_budget_expenditure(request, pk):
    """Partially update one actual-expenditure month."""
    try:
        values = _expenditure_values(request.data, partial=True)
        with transaction.atomic():
            row = MonthlyYouthExpenditure.objects.select_for_update().get(pk=pk)
            for field, value in values.items():
                setattr(row, field, value)
            row.save()
    except MonthlyYouthExpenditure.DoesNotExist:
        return Response({"detail": "Expenditure row not found."}, status=404)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=400)
    except IntegrityError:
        return Response(
            {"detail": "Expenditure already exists for that year and month."},
            status=400,
        )
    return Response(serialize_expenditure(row))
