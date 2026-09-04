"""Youth Budget Calculator endpoints.

The summary, preview, and every write are restricted to ADMIN and PROJECT
MANAGER roles. Writes run inside database transactions.
"""
from datetime import date
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
from rest_framework.response import Response

from .. import youth_budget
from ..authentication import ClerkAuthentication
from ..models import (
    AirtableSyncLog,
    BudgetScenario,
    FundingPot,
    MonthlyYouthExpenditure,
    School,
    Youth,
)
from ..permissions import IsAdminOrProjectManager


AUTH_CLASSES = [SessionAuthentication, ClerkAuthentication]
SCENARIO_DECIMAL_FIELDS = {
    "wage_rate",
    "nys_subsidy_contribution",
    "sef_subsidy_contribution",
    "holiday_pay",
    "mentor_reserve",
}
SCENARIO_MONTH_FIELDS = {
    "vacancy_start_month",
}
SCENARIO_COUNT_FIELDS = {
    "nys_full_time_count",
    "nys_part_time_count",
    "sef_full_time_count",
    "sef_part_time_count",
}
SUBSIDY_ENRICHMENT_CONTRACT = "youth_subsidy_enrichment_v1"


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


def _scenario_defaults(year):
    return youth_budget.default_scenario_values(year)


def _scenario_year(request):
    raw = request.data.get("year") if hasattr(request, "data") else None
    return _integer(raw or timezone.localdate().year, "year")


def _scenario_updates(data, year, scenario):
    updates = {}
    for field in SCENARIO_DECIMAL_FIELDS:
        if field in data:
            updates[field] = _nonnegative_decimal(data[field], field)

    legacy_contribution = None
    if "subsidy_contribution" in data:
        legacy_contribution = _nonnegative_decimal(
            data["subsidy_contribution"],
            "subsidy_contribution",
        )
        canonical = updates.get("nys_subsidy_contribution")
        if canonical is not None and canonical != legacy_contribution:
            raise ValueError(
                "subsidy_contribution conflicts with nys_subsidy_contribution."
            )
        updates["nys_subsidy_contribution"] = legacy_contribution
    if "nys_subsidy_contribution" in updates:
        updates["subsidy_contribution"] = updates[
            "nys_subsidy_contribution"
        ]
    if "utilisation_pct" in data:
        pct = _integer(data["utilisation_pct"], "utilisation_pct")
        if not 1 <= pct <= 120:
            raise ValueError("utilisation_pct must be between 1 and 120.")
        updates["utilisation_pct"] = pct
    for field in SCENARIO_COUNT_FIELDS:
        if field in data:
            count = _integer(data[field], field)
            if count < 0:
                raise ValueError(f"{field} must be non-negative.")
            updates[field] = count
    for field in SCENARIO_MONTH_FIELDS:
        if field in data:
            month = _integer(data[field], field)
            if not 1 <= month <= 12:
                raise ValueError(f"{field} must be between 1 and 12.")
            updates[field] = month
    nys_start = None
    if "nys_start_date" in data:
        nys_start = _date(data["nys_start_date"], "nys_start_date")
    legacy_start_month = None
    if "nys_conversion_start_month" in data:
        legacy_start_month = _integer(
            data["nys_conversion_start_month"],
            "nys_conversion_start_month",
        )
        if not 1 <= legacy_start_month <= 12:
            raise ValueError(
                "nys_conversion_start_month must be between 1 and 12."
            )
        legacy_start = date(year, legacy_start_month, 1)
        if nys_start is not None and nys_start != legacy_start:
            raise ValueError(
                "nys_conversion_start_month conflicts with nys_start_date."
            )
        nys_start = legacy_start
    if nys_start is not None:
        updates["nys_start_date"] = nys_start
        updates["nys_conversion_start_month"] = nys_start.month

    for field in ("nys_end_date", "sef_start_date", "sef_end_date"):
        if field in data:
            updates[field] = _date(data[field], field)
    if "last_paid_programme_date" in data:
        end_date = _date(
            data["last_paid_programme_date"],
            "last_paid_programme_date",
        )
        if end_date.year != year:
            raise ValueError(
                "last_paid_programme_date must be in the scenario year."
            )
        if end_date > youth_budget.HORIZON_END:
            raise ValueError(
                "last_paid_programme_date cannot be after 30 November 2026."
            )
        updates["last_paid_programme_date"] = end_date
    if "hours_matrix" in data:
        updates["hours_matrix"] = _hours_matrix(data["hours_matrix"])

    merged = _scenario_as_dict(scenario, updates)
    for scheme in ("nys", "sef"):
        start = merged[f"{scheme}_start_date"]
        end = merged[f"{scheme}_end_date"]
        if start.year != year:
            raise ValueError(f"{scheme}_start_date must be in the scenario year.")
        if end.year not in {year, year + 1}:
            raise ValueError(
                f"{scheme}_end_date must be in the scenario year or following year."
            )
        if start > end:
            raise ValueError(
                f"{scheme}_start_date must be on or before {scheme}_end_date."
            )
    return updates


def _scenario_as_dict(scenario, updates=None):
    values = {
        "year": scenario.year,
        "wage_rate": scenario.wage_rate,
        "subsidy_contribution": scenario.nys_subsidy_contribution,
        "nys_subsidy_contribution": scenario.nys_subsidy_contribution,
        "hours_matrix": scenario.hours_matrix,
        "nys_full_time_count": scenario.nys_full_time_count,
        "nys_part_time_count": scenario.nys_part_time_count,
        "nys_start_date": scenario.nys_start_date,
        "nys_end_date": scenario.nys_end_date,
        "sef_subsidy_contribution": scenario.sef_subsidy_contribution,
        "sef_full_time_count": scenario.sef_full_time_count,
        "sef_part_time_count": scenario.sef_part_time_count,
        "sef_start_date": scenario.sef_start_date,
        "sef_end_date": scenario.sef_end_date,
        "utilisation_pct": scenario.utilisation_pct,
        "nys_conversion_start_month": scenario.nys_conversion_start_month,
        "vacancy_start_month": scenario.vacancy_start_month,
        "last_paid_programme_date": scenario.last_paid_programme_date,
        "holiday_pay": scenario.holiday_pay,
        "mentor_reserve": scenario.mentor_reserve,
    }
    values.update(updates or {})
    return values


def serialize_scenario(scenario):
    return {
        "id": scenario.id,
        "year": scenario.year,
        "wage_rate": _number(scenario.wage_rate),
        "subsidy_contribution": _number(scenario.nys_subsidy_contribution),
        "nys_subsidy_contribution": _number(
            scenario.nys_subsidy_contribution
        ),
        "hours_matrix": scenario.hours_matrix,
        "nys_full_time_count": scenario.nys_full_time_count,
        "nys_part_time_count": scenario.nys_part_time_count,
        "nys_start_date": _iso(scenario.nys_start_date),
        "nys_end_date": _iso(scenario.nys_end_date),
        "sef_subsidy_contribution": _number(
            scenario.sef_subsidy_contribution
        ),
        "sef_full_time_count": scenario.sef_full_time_count,
        "sef_part_time_count": scenario.sef_part_time_count,
        "sef_start_date": _iso(scenario.sef_start_date),
        "sef_end_date": _iso(scenario.sef_end_date),
        "utilisation_pct": scenario.utilisation_pct,
        "nys_conversion_start_month": scenario.nys_start_date.month,
        "vacancy_start_month": scenario.vacancy_start_month,
        "last_paid_programme_date": _iso(scenario.last_paid_programme_date),
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
        "is_ringfenced": pot.is_ringfenced,
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
                "working_dates": [
                    _iso(value) for value in row.get("working_dates", [])
                ],
                "gross": _number(row["gross"]),
                "uif": _number(row["uif"]),
                "subsidy_relief": _number(row["subsidy_relief"]),
                "net": _number(row["net"]),
            }
            for row in projection["months"]
        ],
        "total": _number(projection["total"]),
        "current_core_youth": projection.get(
            "current_core_youth",
            projection.get("costed_youth", 0),
        ),
        # Deprecated response alias retained for the running frontend.
        "costed_youth": projection.get("costed_youth", 0),
        "open_posts": projection.get("open_posts", 0),
    }


def serialize_subsidy_plan(plan):
    return {
        "policy": plan["policy"],
        "eligible_current_youth": plan["eligible_current_youth"],
        "requested_total": plan["requested_total"],
        "modelled_total": plan["modelled_total"],
        "unmodelled_total": plan["unmodelled_total"],
        "schemes": {
            key: {
                "contribution": _number(row["contribution"]),
                "start_date": _iso(row["start_date"]),
                "end_date": _iso(row["end_date"]),
                "requested_full_time": row["requested_full_time"],
                "requested_part_time": row["requested_part_time"],
                "requested_total": row["requested_total"],
                "modelled_full_time": row["modelled_full_time"],
                "modelled_part_time": row["modelled_part_time"],
                "modelled_total": row["modelled_total"],
                "unmodelled_total": row["unmodelled_total"],
            }
            for key, row in plan["schemes"].items()
        },
    }


def source_subsidies_summary():
    """Return the last complete canonical enrichment and current source counts."""
    attempts = list(
        AirtableSyncLog.objects.filter(sync_type="youth")
        .order_by("-started_at")[:100]
    )

    canonical_attempts = []
    for attempt in attempts:
        details = attempt.details or {}
        enrichment = details.get("subsidy_enrichment") or {}
        if enrichment.get("contract_version") == SUBSIDY_ENRICHMENT_CONTRACT:
            canonical_attempts.append((attempt, enrichment))

    latest = canonical_attempts[0] if canonical_attempts else None
    complete = next(
        (
            (attempt, enrichment)
            for attempt, enrichment in canonical_attempts
            if attempt.success and enrichment.get("complete") is True
        ),
        None,
    )
    latest_succeeded = bool(
        latest
        and latest[0].success
        and latest[1].get("complete") is True
    )

    if complete is None:
        return {
            "policy": "informational_only",
            "available": False,
            "nys_tagged_active_employees": None,
            "sef_active_status_employees": None,
            "last_success_at": None,
            "latest_attempt_succeeded": latest_succeeded,
            "enrichment": None,
        }

    receipt, enrichment = complete
    active = Youth.objects.filter(employment_status__iexact="Active")
    return {
        "policy": "informational_only",
        "available": True,
        "nys_tagged_active_employees": active.filter(
            subsidy_funder__iexact="NYS"
        ).count(),
        "sef_active_status_employees": active.filter(
            subsidy_funder__iexact="SEF",
            subsidy_status__iexact="Active",
        ).count(),
        "last_success_at": _iso(receipt.completed_at),
        "latest_attempt_succeeded": latest_succeeded,
        "enrichment": {
            key: enrichment.get(key, 0)
            for key in (
                "matched",
                "missing_link",
                "multiple_links",
                "missing_target",
            )
        },
    }


def serialize_spend_forecast(forecast):
    estimate = forecast["mentor_estimate"]
    return {
        "months": [
            {
                "month": row["month"],
                "working_days": row["working_days"],
                "working_dates": [
                    _iso(value) for value in row.get("working_dates", [])
                ],
                "core_amount": _number(row["core_amount"]),
                "mentor_amount": _number(row["mentor_amount"]),
                "rural_amount": _number(row["rural_amount"]),
                "total": _number(row["total"]),
            }
            for row in forecast["months"]
        ],
        "mentor_estimate": {
            "method": estimate["method"],
            "monthly_amount": _number(estimate["monthly_amount"]),
            "source_actuals": [
                {
                    "month": row["month"],
                    "amount": _number(row["amount"]),
                }
                for row in estimate["source_actuals"]
            ],
        },
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


def serialize_ringfenced(rows):
    return [
        {
            "funder_name": row["funder_name"],
            "amount": _number(row["amount"]),
            "schools": row["schools"],
            "costed_youth": row["costed_youth"],
            "open_posts": row["open_posts"],
            "projected_committed": _number(row["projected_committed"]),
            "projected_at_plan": _number(row["projected_at_plan"]),
            "surplus": _number(row["surplus"]),
        }
        for row in rows
    ]


def _load_budget_state(year, as_of):
    pots = list(
        FundingPot.objects.filter(year=year)
        .prefetch_related("schools")
        .order_by("funder_name", "id")
    )
    active_core_pots_total = sum(
        (
            pot.amount
            for pot in pots
            if pot.is_active and not pot.is_ringfenced
        ),
        Decimal("0"),
    )
    active_ringfenced_pots = [
        pot for pot in pots if pot.is_active and pot.is_ringfenced
    ]
    ringfenced_school_ids = frozenset(
        school.id
        for pot in active_ringfenced_pots
        for school in pot.schools.all()
    )
    cohorts = youth_budget.build_cohorts(
        today=as_of,
        ringfenced_school_ids=ringfenced_school_ids,
    )
    vacancies = youth_budget.build_vacancies(
        year,
        ringfenced_school_ids=ringfenced_school_ids,
    )
    expenditure = list(
        MonthlyYouthExpenditure.objects.filter(year=year).order_by(
            "month",
            "id",
        )
    )
    return {
        "pots": pots,
        "active_core_pots_total": active_core_pots_total,
        "active_ringfenced_pots": active_ringfenced_pots,
        "ringfenced_total": sum(
            (pot.amount for pot in active_ringfenced_pots),
            Decimal("0"),
        ),
        "cohorts": cohorts,
        "vacancies": vacancies,
        "expenditure": expenditure,
    }


def _calculate_budget(state, scenario, as_of):
    cohorts = state["cohorts"]
    vacancies = state["vacancies"]
    projections = youth_budget.project(
        scenario,
        cohorts,
        vacancies["vacancies"],
        as_of,
    )
    ringfenced_pots = youth_budget.project_ringfenced(
        scenario,
        state["active_ringfenced_pots"],
        cohorts["ringfenced_costing_cohorts"],
        vacancies["ringfenced_vacancies"],
        as_of,
    )
    ringfenced_projections = youth_budget.project_ringfenced_summary(
        scenario,
        cohorts["ringfenced_costing_cohorts"],
        vacancies["ringfenced_vacancies"],
        as_of,
    )
    mentor_estimate = youth_budget.build_mentor_estimate(state["expenditure"])
    spend_forecast = youth_budget.build_spend_forecast(
        projections["committed"],
        ringfenced_projections["committed"],
        mentor_estimate,
    )
    feasibility = youth_budget.calculate_feasibility(
        state["pots"],
        projections["at_plan"],
    )
    return {
        "projections": projections,
        "ringfenced_pots": ringfenced_pots,
        "ringfenced_projections": ringfenced_projections,
        "spend_forecast": spend_forecast,
        "feasibility": feasibility,
    }


def _serialize_projection_calculation(calculation, state, scenario):
    projections = calculation["projections"]
    return {
        "subsidy_plan": serialize_subsidy_plan(
            projections["subsidy_plan"]
        ),
        "projections": {
            "committed": serialize_projection(projections["committed"]),
            "at_plan": serialize_projection(projections["at_plan"]),
            "verdict_committed": _number(
                youth_budget.calculate_verdict(
                    state["active_core_pots_total"],
                    _scenario_value_for_view(scenario, "mentor_reserve"),
                    projections["committed"]["total"],
                )
            ),
            "verdict_at_plan": _number(
                youth_budget.calculate_verdict(
                    state["active_core_pots_total"],
                    _scenario_value_for_view(scenario, "mentor_reserve"),
                    projections["at_plan"]["total"],
                )
            ),
        },
        "ringfenced_projections": {
            "committed": serialize_projection(
                calculation["ringfenced_projections"]["committed"]
            ),
            "at_plan": serialize_projection(
                calculation["ringfenced_projections"]["at_plan"]
            ),
        },
        "ringfenced_pots": serialize_ringfenced(
            calculation["ringfenced_pots"]
        ),
        "spend_forecast": serialize_spend_forecast(
            calculation["spend_forecast"]
        ),
        "feasibility": serialize_feasibility(calculation["feasibility"]),
    }


def _scenario_value_for_view(scenario, field):
    if isinstance(scenario, dict):
        return scenario.get(field)
    return getattr(scenario, field)


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
@permission_classes([IsAdminOrProjectManager])
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
            defaults=_scenario_defaults(year),
        )
    state = _load_budget_state(year, as_of)
    calculation = _calculate_budget(state, scenario, as_of)
    serialized_calculation = _serialize_projection_calculation(
        calculation,
        state,
        scenario,
    )
    cohorts = state["cohorts"]

    return Response(
        {
            "year": year,
            "as_of": as_of.isoformat(),
            "pots": [serialize_pot(pot) for pot in state["pots"]],
            "pots_total": _number(state["active_core_pots_total"]),
            "ringfenced": {
                "pots": serialized_calculation["ringfenced_pots"],
                "total_amount": _number(state["ringfenced_total"]),
                "youth": cohorts["notes"]["ringfenced"],
                "projections": serialized_calculation[
                    "ringfenced_projections"
                ],
            },
            "scenario": serialize_scenario(scenario),
            "subsidy_plan": serialized_calculation["subsidy_plan"],
            "source_subsidies": source_subsidies_summary(),
            "cohorts": cohorts["cohorts"],
            "projections": serialized_calculation["projections"],
            "spend_forecast": serialized_calculation["spend_forecast"],
            "expenditure": [
                serialize_expenditure(row)
                for row in state["expenditure"]
            ],
            "feasibility": serialized_calculation["feasibility"],
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


@api_view(["POST"])
@authentication_classes(AUTH_CLASSES)
@permission_classes([IsAdminOrProjectManager])
def preview_youth_budget_scenario(request):
    """Recalculate a draft scenario without changing shared database state."""
    try:
        year = _scenario_year(request)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=400)

    try:
        scenario = BudgetScenario.objects.get(year=year)
    except BudgetScenario.DoesNotExist:
        scenario = BudgetScenario(year=year, **_scenario_defaults(year))
    try:
        updates = _scenario_updates(request.data, year, scenario)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=400)
    draft = _scenario_as_dict(scenario, updates)
    as_of = timezone.localdate()
    state = _load_budget_state(year, as_of)
    calculation = _calculate_budget(state, draft, as_of)
    serialized = _serialize_projection_calculation(
        calculation,
        state,
        draft,
    )
    return Response(serialized)


@api_view(["PATCH"])
@authentication_classes(AUTH_CLASSES)
@permission_classes([IsAdminOrProjectManager])
def update_youth_budget_scenario(request):
    """Partially update the shared scenario selected by its year."""
    try:
        year = _scenario_year(request)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=400)

    scenario = BudgetScenario.objects.filter(year=year).first()
    validation_scenario = scenario or BudgetScenario(
        year=year,
        **_scenario_defaults(year),
    )
    try:
        updates = _scenario_updates(request.data, year, validation_scenario)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=400)

    with transaction.atomic():
        scenario, _created = BudgetScenario.objects.get_or_create(
            year=year,
            defaults=_scenario_defaults(year),
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
        is_ringfenced=_boolean(
            data.get("is_ringfenced", False),
            "is_ringfenced",
        ),
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
            if "is_ringfenced" in request.data:
                pot.is_ringfenced = _boolean(
                    request.data["is_ringfenced"],
                    "is_ringfenced",
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
