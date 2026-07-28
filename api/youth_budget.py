"""Youth Budget Calculator policy and projection logic.

This module keeps calendar, cohort, and costing rules separate from HTTP views.
Model imports are lazy inside query functions so the rules can be tested without
loading Django's app registry.
"""
from calendar import monthrange
from collections import defaultdict
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from api.school_programme import (
    SITE_UNASSIGNED,
    YEBO,
    _JOB_TITLE_TO_PROGRAMME,
    normalize_site_type,
    programme_for_job_title,
)


TERM_RANGES_2026 = (
    (date(2026, 7, 21), date(2026, 9, 23)),
    (date(2026, 10, 6), date(2026, 12, 9)),
)
PUBLIC_HOLIDAYS_2026 = {date(2026, 8, 10)}
HORIZON_END = date(2026, 11, 30)
UIF_FACTOR = Decimal("1.01")
MONEY_QUANTUM = Decimal("0.01")

# Zazi iZandi youth work 3.5 hours per day (Jim 2026-07-28, confirmed by the
# full-attendance payment cluster: 3.5h x ~20 days x R32.01 matches the May
# ledger's repeated R2,218 payments).
_ZAZI_TITLES = {"zazi izandi coach", "zz ecd coach", "literacy coaches (zz)"}


def _default_hours(site_type, job_title):
    if job_title in _ZAZI_TITLES:
        return 3.5
    if site_type == "ecd" or job_title in {"practitioner", "ecd practitioner"}:
        return 5.5
    return 4.5


HOURS_MATRIX_DEFAULTS = {
    site_type: {
        job_title: {
            "hours_per_day": _default_hours(site_type, job_title),
            "days_per_week": 5,
        }
        for job_title in _JOB_TITLE_TO_PROGRAMME
    }
    for site_type in ("primary", "ecd")
}

PROGRAMME_REPRESENTATIVE_TITLES = {
    "masi_literacy": "literacy coach",
    "numeracy": "numeracy coach",
    "zazi_izandi": "zazi izandi coach",
    "thousand_stories": "1000 stories youth",
    "edutech": "edutech coach",
    "sport_arts": "sport & arts coach",
    "homework": "homework coach",
    "preschool": "practitioner",
}


def _money(value):
    """Round a Decimal monetary value to cents."""
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _decimal(value, fallback=Decimal("0")):
    """Convert a stored scenario value to Decimal without using binary floats."""
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return fallback


def _scenario_value(scenario, name, fallback=None):
    if isinstance(scenario, dict):
        return scenario.get(name, fallback)
    return getattr(scenario, name, fallback)


def _site_type(raw):
    normalized = normalize_site_type(raw)
    return normalized.lower() if normalized else "primary"


def _job_title(raw):
    return (raw or "").strip().lower()


def _is_empty(value):
    return value is None or (isinstance(value, str) and not value.strip())


def school_days_in_month(year, month, start_from=None):
    """Count in-term weekdays for a month within the November horizon."""
    try:
        first = date(year, month, 1)
    except ValueError:
        return 0
    last = date(year, month, monthrange(year, month)[1])
    current = first
    total = 0
    while current <= last:
        in_term = any(start <= current <= end for start, end in TERM_RANGES_2026)
        if (
            current <= HORIZON_END
            and (start_from is None or current >= start_from)
            and current.weekday() < 5
            and current not in PUBLIC_HOLIDAYS_2026
            and in_term
        ):
            total += 1
        current += timedelta(days=1)
    return total


def default_scenario_values():
    """Defaults used when the shared scenario is first created."""
    return {
        "wage_rate": Decimal("32.01"),
        "subsidy_contribution": Decimal("1600"),
        "hours_matrix": deepcopy(HOURS_MATRIX_DEFAULTS),
        "nys_conversion_count": 200,
        "nys_subsidy_only_count": 0,
        "nys_conversion_start_month": 8,
        "vacancy_start_month": 8,
        "holiday_pay": Decimal("0"),
        "mentor_reserve": Decimal("0"),
        "utilisation_pct": 100,
        "updated_by": "",
    }


def build_cohorts(today=None):
    """Aggregate active Youth for public what-if data and detailed costing.

    The public rows use only the fields the frontend needs. Detailed rows retain
    school and subsidy-end provenance so backend projections and restricted-pot
    checks remain accurate.
    """
    if today is None:
        from django.utils import timezone

        today = timezone.localdate()
    from api.models import Youth

    public = defaultdict(
        lambda: {
            "headcount": 0,
            "subsidised_count": 0,
            "nys_eligible_count": 0,
        }
    )
    detailed = defaultdict(
        lambda: {
            "headcount": 0,
            "subsidised_count": 0,
            "nys_eligible_count": 0,
        }
    )
    notes = {
        "active_total": 0,
        "school_less": 0,
        "yebo_shown_only": 0,
    }

    rows = Youth.objects.filter(employment_status="Active").select_related("school")
    for youth in rows:
        site_type = _site_type(youth.school.type if youth.school else None)
        job_title = _job_title(youth.job_title)
        programme = programme_for_job_title(job_title)
        status_active = (
            (youth.subsidy_status or "").strip().lower() == "active"
            and (
                youth.subsidy_end_date is None
                or youth.subsidy_end_date >= today
            )
        )
        never_sef = all(
            _is_empty(value)
            for value in (
                youth.subsidy_funder,
                youth.subsidy_status,
                youth.subsidy_start_date,
                youth.subsidy_end_date,
            )
        )
        nys_eligible = never_sef and programme != YEBO

        notes["active_total"] += 1
        if youth.school_id is None:
            notes["school_less"] += 1
        if programme == YEBO:
            notes["yebo_shown_only"] += 1

        public_key = (site_type, job_title, programme)
        public[public_key]["headcount"] += 1
        public[public_key]["subsidised_count"] += int(status_active)
        public[public_key]["nys_eligible_count"] += int(nys_eligible)

        detailed_key = (
            youth.school_id,
            youth.school.name if youth.school else "",
            site_type,
            job_title,
            programme,
            status_active,
            youth.subsidy_end_date if status_active else None,
            nys_eligible,
        )
        detailed[detailed_key]["headcount"] += 1
        detailed[detailed_key]["subsidised_count"] += int(status_active)
        detailed[detailed_key]["nys_eligible_count"] += int(nys_eligible)

    public_rows = []
    for (site_type, job_title, programme), counts in sorted(
        public.items(),
        key=lambda item: (item[0][0], item[0][1], item[0][2] or ""),
    ):
        public_rows.append(
            {
                "site_type": site_type,
                "job_title": job_title,
                "programme": programme,
                **counts,
            }
        )

    costing_rows = []
    for key, counts in sorted(
        detailed.items(),
        key=lambda item: (
            item[0][0] is None,
            item[0][0] or 0,
            item[0][2],
            item[0][3],
            item[0][4] or "",
            str(item[0][6] or ""),
        ),
    ):
        (
            school_id,
            school_name,
            site_type,
            job_title,
            programme,
            _status_active,
            subsidy_end_date,
            _nys_eligible,
        ) = key
        costing_rows.append(
            {
                "school_id": school_id,
                "school_name": school_name,
                "site_type": site_type,
                "job_title": job_title,
                "programme": programme,
                "subsidy_end_date": subsidy_end_date,
                **counts,
            }
        )

    return {
        "cohorts": public_rows,
        "costing_cohorts": costing_rows,
        "notes": notes,
    }


def build_vacancies(year):
    """Return open non-Yebo planned posts in projection-ready rows."""
    from django.db.models import F
    from api.models import SchoolProgrammeYear

    vacancies = []
    rows = (
        SchoolProgrammeYear.objects.filter(
            year=year,
            youth_planned__isnull=False,
            youth_planned__gt=F("youth_active"),
        )
        .exclude(programme=YEBO)
        .select_related("school")
        .order_by("school_id", "programme")
    )
    for row in rows:
        vacancies.append(
            {
                "school_id": row.school_id,
                "school_name": row.school.name,
                "site_type": _site_type(row.school.type),
                "job_title": PROGRAMME_REPRESENTATIVE_TITLES.get(
                    row.programme,
                    "",
                ),
                "programme": row.programme,
                "headcount": row.youth_planned - row.youth_active,
                "subsidised_count": 0,
                "nys_eligible_count": 0,
                "_vacancy": True,
            }
        )
    return vacancies


def hours_for(matrix, site_type, job_title):
    """Read one Hours Matrix entry with the specified conservative fallback."""
    entry = (
        (matrix or {})
        .get(site_type, {})
        .get(_job_title(job_title), {})
    )
    hours = _decimal(entry.get("hours_per_day"), Decimal("4.5"))
    days = _decimal(entry.get("days_per_week"), Decimal("5"))
    if hours < 0:
        hours = Decimal("4.5")
    if days < 0:
        days = Decimal("5")
    return hours, days


def _projection_months(year, as_of):
    if as_of.year > year or year > HORIZON_END.year:
        return []
    if as_of.year < year:
        start_month = 1
    else:
        start_month = as_of.month
    if start_month > HORIZON_END.month:
        return []
    return list(range(start_month, HORIZON_END.month + 1))


def _actual_subsidised_count(row, year, month):
    count = int(row.get("subsidised_count") or 0)
    end_date = row.get("subsidy_end_date")
    if isinstance(end_date, str):
        try:
            end_date = date.fromisoformat(end_date)
        except ValueError:
            end_date = None
    if end_date is not None and end_date < date(year, month, 1):
        return 0
    return count


def _allocate_proportionally(eligible_counts, requested):
    """Largest-remainder allocation of `requested` slots across cohorts."""
    eligible_total = sum(eligible_counts)
    target = min(max(int(requested or 0), 0), eligible_total)
    if eligible_total == 0 or target == 0:
        return [0 for _count in eligible_counts]

    allocated = [
        target * eligible // eligible_total
        for eligible in eligible_counts
    ]
    remaining = target - sum(allocated)
    remainders = [
        (target * eligible) % eligible_total
        for eligible in eligible_counts
    ]
    for index in sorted(
        range(len(eligible_counts)),
        key=lambda item: (-remainders[item], item),
    ):
        if remaining == 0:
            break
        if allocated[index] < eligible_counts[index]:
            allocated[index] += 1
            remaining -= 1
    return allocated


def _nys_conversions(rows, requested, subsidy_only=0):
    """Split NYS conversions into zero-cost and top-up allocations per row.

    Subsidy-only part-timers work only the hours the subsidy pays for and
    never touch Masi payroll, so they leave the costed population entirely
    (no gross, no UIF) rather than merely earning the R1,600 relief. They are
    allocated first; the remaining conversions get standard top-up relief
    from the pool that is left.
    """
    eligible_counts = []
    for row in rows:
        eligible = 0
        if row.get("programme") != YEBO and not row.get("_vacancy"):
            eligible = max(int(row.get("nys_eligible_count") or 0), 0)
        eligible_counts.append(eligible)

    requested_total = max(int(requested or 0), 0)
    zero_target = min(max(int(subsidy_only or 0), 0), requested_total)
    zero_cost = _allocate_proportionally(eligible_counts, zero_target)
    remaining_eligible = [
        eligible - converted
        for eligible, converted in zip(eligible_counts, zero_cost)
    ]
    relief = _allocate_proportionally(
        remaining_eligible,
        requested_total - sum(zero_cost),
    )
    return zero_cost, relief


def _project_rows(scenario, rows, as_of):
    year = int(_scenario_value(scenario, "year", as_of.year))
    matrix = _scenario_value(scenario, "hours_matrix") or HOURS_MATRIX_DEFAULTS
    wage_rate = _decimal(
        _scenario_value(scenario, "wage_rate"),
        Decimal("32.01"),
    )
    contribution = _decimal(
        _scenario_value(scenario, "subsidy_contribution"),
        Decimal("1600"),
    )
    conversion_month = int(
        _scenario_value(scenario, "nys_conversion_start_month", 8)
    )
    vacancy_month = int(_scenario_value(scenario, "vacancy_start_month", 8))
    utilisation = _decimal(
        _scenario_value(scenario, "utilisation_pct", 100),
        Decimal("100"),
    ) / Decimal("100")
    if utilisation < 0:
        utilisation = Decimal("1")
    zero_cost_converted, relief_converted = _nys_conversions(
        rows,
        _scenario_value(scenario, "nys_conversion_count", 200),
        _scenario_value(scenario, "nys_subsidy_only_count", 0),
    )

    months = []
    school_totals = defaultdict(lambda: Decimal("0"))
    for month in _projection_months(year, as_of):
        days = school_days_in_month(year, month, start_from=as_of)
        month_gross = Decimal("0")
        month_uif = Decimal("0")
        month_relief = Decimal("0")
        month_net = Decimal("0")

        for index, row in enumerate(rows):
            if row.get("programme") == YEBO:
                continue
            if row.get("_vacancy") and month < vacancy_month:
                continue
            headcount = max(int(row.get("headcount") or 0), 0)
            # Subsidy-only converts leave the costed population from their
            # start month: no gross, no UIF, not merely relief.
            if not row.get("_vacancy") and month >= conversion_month:
                headcount = max(headcount - zero_cost_converted[index], 0)
            if headcount == 0:
                continue

            hours, days_per_week = hours_for(
                matrix,
                row.get("site_type") or "primary",
                row.get("job_title") or "",
            )
            gross_each = (
                hours
                * Decimal(days)
                * (days_per_week / Decimal("5"))
                * wage_rate
                * utilisation
            )
            gross = gross_each * headcount
            uif = gross * (UIF_FACTOR - Decimal("1"))
            subsidised = 0
            if not row.get("_vacancy"):
                subsidised = _actual_subsidised_count(row, year, month)
                if month >= conversion_month:
                    subsidised += relief_converted[index]
                subsidised = min(subsidised, headcount)
            relief_each = min(contribution, gross_each * UIF_FACTOR)
            relief = relief_each * subsidised
            net = gross + uif - relief

            month_gross += gross
            month_uif += uif
            month_relief += relief
            month_net += net
            school_totals[row.get("school_id")] += net

        months.append(
            {
                "month": month,
                # Exposed so the frontend can recompute lever what-ifs without
                # duplicating the term calendar client-side.
                "school_days": days,
                "gross": _money(month_gross),
                "uif": _money(month_uif),
                "subsidy_relief": _money(month_relief),
                "net": _money(month_net),
            }
        )

    holiday_pay = _decimal(_scenario_value(scenario, "holiday_pay"), Decimal("0"))
    return {
        "months": months,
        "total": _money(sum((row["net"] for row in months), Decimal("0")) + holiday_pay),
        "school_totals": {
            school_id: _money(total)
            for school_id, total in school_totals.items()
        },
    }


def project(scenario, cohorts, vacancies, as_of):
    """Return committed and at-plan monthly projections for one scenario."""
    if isinstance(cohorts, dict):
        active_rows = list(cohorts.get("costing_cohorts", cohorts.get("cohorts", [])))
    else:
        active_rows = list(cohorts)
    vacancy_rows = [{**row, "_vacancy": True} for row in vacancies]

    # Headcounts explain WHY at-plan exceeds committed: staff read the gap as
    # "cost of N more posts", so both projections carry their costed population.
    costed_youth = sum(
        max(int(row.get("headcount") or 0), 0)
        for row in active_rows
        if row.get("programme") != YEBO
    )
    open_posts = sum(
        max(int(row.get("headcount") or 0), 0) for row in vacancy_rows
    )

    committed = _project_rows(scenario, active_rows, as_of)
    committed["costed_youth"] = costed_youth
    committed["open_posts"] = 0
    at_plan = _project_rows(scenario, active_rows + vacancy_rows, as_of)
    at_plan["costed_youth"] = costed_youth + open_posts
    at_plan["open_posts"] = open_posts
    return {"committed": committed, "at_plan": at_plan}


def calculate_verdict(pots_total, mentor_reserve, projected_total):
    """Positive means under budget and negative means over budget."""
    return _money(
        _decimal(pots_total)
        - _decimal(mentor_reserve)
        - _decimal(projected_total)
    )


def calculate_feasibility(pots, at_plan_projection):
    """Check whether restricted active pots can be spent at their schools."""
    school_totals = at_plan_projection.get("school_totals", {})
    result = []
    for pot in pots:
        if not pot.is_active:
            continue
        # Sort in Python: chaining .order_by() onto a prefetched manager clones
        # the queryset and re-queries, silently defeating prefetch_related.
        schools = sorted(pot.schools.all(), key=lambda school: (school.name, school.id))
        if not schools:
            continue
        projected = _money(
            sum(
                (school_totals.get(school.id, Decimal("0")) for school in schools),
                Decimal("0"),
            )
        )
        amount = _money(pot.amount)
        result.append(
            {
                "funder_name": pot.funder_name,
                "amount": amount,
                "projected_at_schools": projected,
                "shortfall": _money(max(amount - projected, Decimal("0"))),
                "schools": [school.name for school in schools],
            }
        )
    return result
