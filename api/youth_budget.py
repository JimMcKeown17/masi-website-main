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


def school_dates_in_month(year, month, start_from=None, end_on=None):
    """Return the exact in-term weekdays costed inside one calendar month."""
    try:
        first = date(year, month, 1)
    except ValueError:
        return []
    last = date(year, month, monthrange(year, month)[1])
    effective_end = min(end_on or HORIZON_END, HORIZON_END)
    current = first
    result = []
    while current <= last:
        in_term = any(start <= current <= end for start, end in TERM_RANGES_2026)
        if (
            current <= effective_end
            and (start_from is None or current >= start_from)
            and current.weekday() < 5
            and current not in PUBLIC_HOLIDAYS_2026
            and in_term
        ):
            result.append(current)
        current += timedelta(days=1)
    return result


def school_days_in_month(year, month, start_from=None, end_on=None):
    """Count the exact dates returned by :func:`school_dates_in_month`."""
    return len(
        school_dates_in_month(
            year,
            month,
            start_from=start_from,
            end_on=end_on,
        )
    )


def default_scenario_values(year=2026):
    """Defaults used when the shared scenario is first created."""
    return {
        "wage_rate": Decimal("32.01"),
        # Legacy aliases remain populated during the expand-contract release.
        "subsidy_contribution": Decimal("1900"),
        "nys_subsidy_contribution": Decimal("1900"),
        "hours_matrix": deepcopy(HOURS_MATRIX_DEFAULTS),
        "nys_full_time_count": 127,
        "nys_part_time_count": 41,
        "nys_conversion_start_month": 9,
        "nys_start_date": date(year, 9, 1),
        "nys_end_date": date(year, 12, 31),
        "sef_subsidy_contribution": Decimal("1400"),
        "sef_full_time_count": 200,
        "sef_part_time_count": 0,
        "sef_start_date": date(year, 10, 1),
        "sef_end_date": date(year + 1, 3, 31),
        "vacancy_start_month": 8,
        "last_paid_programme_date": HORIZON_END,
        "holiday_pay": Decimal("0"),
        "mentor_reserve": Decimal("0"),
        "utilisation_pct": 100,
        "updated_by": "",
    }


def build_cohorts(today=None, ringfenced_school_ids=frozenset()):
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
    ringfenced_detailed = defaultdict(
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
        "ringfenced": 0,
    }

    rows = Youth.objects.filter(employment_status="Active").select_related("school")
    for youth in rows:
        site_type = _site_type(youth.school.type if youth.school else None)
        job_title = _job_title(youth.job_title)
        programme = programme_for_job_title(job_title)
        # V1 projections are deliberately theoretical. Airtable subsidy tags
        # feed a separate source summary and never change costing or capacity.
        status_active = False
        nys_eligible = programme != YEBO

        notes["active_total"] += 1
        if youth.school_id is None:
            notes["school_less"] += 1
        if programme == YEBO:
            notes["yebo_shown_only"] += 1

        is_ringfenced = youth.school_id in ringfenced_school_ids
        if is_ringfenced:
            notes["ringfenced"] += 1
            detailed_key = (
                youth.school_id,
                youth.school.name if youth.school else "",
                site_type,
                job_title,
                programme,
                status_active,
                youth.subsidy_end_date if status_active else None,
                False,
            )
            ringfenced_detailed[detailed_key]["headcount"] += 1
            ringfenced_detailed[detailed_key]["subsidised_count"] += 0
            continue

        public_key = (site_type, job_title, programme)
        public[public_key]["headcount"] += 1
        public[public_key]["subsidised_count"] += 0
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
        detailed[detailed_key]["subsidised_count"] += 0
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

    def costing_rows(source):
        rows = []
        for key, counts in sorted(
            source.items(),
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
            rows.append(
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
        return rows

    return {
        "cohorts": public_rows,
        "costing_cohorts": costing_rows(detailed),
        "ringfenced_costing_cohorts": costing_rows(ringfenced_detailed),
        "notes": notes,
    }


def build_vacancies(year, ringfenced_school_ids=frozenset()):
    """Return core and ringfenced open posts in projection-ready rows."""
    from django.db.models import F
    from api.models import SchoolProgrammeYear

    vacancies = []
    ringfenced_vacancies = []
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
        vacancy = {
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
        if row.school_id in ringfenced_school_ids:
            ringfenced_vacancies.append(vacancy)
        else:
            vacancies.append(vacancy)
    return {
        "vacancies": vacancies,
        "ringfenced_vacancies": ringfenced_vacancies,
    }


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


def _scenario_last_paid_programme_date(scenario):
    value = _scenario_value(
        scenario,
        "last_paid_programme_date",
        HORIZON_END,
    )
    if isinstance(value, str):
        try:
            value = date.fromisoformat(value)
        except ValueError:
            value = HORIZON_END
    return value if isinstance(value, date) else HORIZON_END


def _projection_months(year, as_of, end_on):
    effective_end = min(end_on, HORIZON_END)
    if as_of.year > year or year > effective_end.year or effective_end < as_of:
        return []
    if as_of.year < year:
        start_month = 1
    else:
        start_month = as_of.month
    if start_month > effective_end.month:
        return []
    return list(range(start_month, effective_end.month + 1))


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


def _scenario_date(scenario, field, fallback):
    value = _scenario_value(scenario, field, fallback)
    if isinstance(value, str):
        try:
            value = date.fromisoformat(value)
        except ValueError:
            value = fallback
    return value if isinstance(value, date) else fallback


def _subsidy_schemes(scenario, year):
    """Return canonical theoretical subsidy inputs with legacy NYS fallbacks."""
    legacy_month = int(
        _scenario_value(scenario, "nys_conversion_start_month", 9) or 9
    )
    nys_start = _scenario_date(
        scenario,
        "nys_start_date",
        date(year, legacy_month, 1),
    )
    return [
        {
            "key": "nys",
            "order": 0,
            "contribution": _decimal(
                _scenario_value(
                    scenario,
                    "nys_subsidy_contribution",
                    _scenario_value(
                        scenario,
                        "subsidy_contribution",
                        Decimal("1900"),
                    ),
                ),
                Decimal("1900"),
            ),
            "requested_full_time": max(
                int(_scenario_value(scenario, "nys_full_time_count", 127) or 0),
                0,
            ),
            "requested_part_time": max(
                int(_scenario_value(scenario, "nys_part_time_count", 41) or 0),
                0,
            ),
            "start_date": nys_start,
            "end_date": _scenario_date(
                scenario,
                "nys_end_date",
                date(year, 12, 31),
            ),
        },
        {
            "key": "sef",
            "order": 1,
            "contribution": _decimal(
                _scenario_value(
                    scenario,
                    "sef_subsidy_contribution",
                    Decimal("1400"),
                ),
                Decimal("1400"),
            ),
            "requested_full_time": max(
                int(_scenario_value(scenario, "sef_full_time_count", 200) or 0),
                0,
            ),
            "requested_part_time": max(
                int(_scenario_value(scenario, "sef_part_time_count", 0) or 0),
                0,
            ),
            "start_date": _scenario_date(
                scenario,
                "sef_start_date",
                date(year, 10, 1),
            ),
            "end_date": _scenario_date(
                scenario,
                "sef_end_date",
                date(year + 1, 3, 31),
            ),
        },
    ]


def _subsidy_allocations(rows, scenario, year):
    """Allocate complete theoretical schemes from one non-overlapping pool."""
    eligible_counts = []
    for row in rows:
        eligible = 0
        if row.get("programme") != YEBO and not row.get("_vacancy"):
            eligible = max(int(row.get("nys_eligible_count") or 0), 0)
        eligible_counts.append(eligible)

    remaining = list(eligible_counts)
    allocations = {}
    schemes = {}
    for scheme in sorted(
        _subsidy_schemes(scenario, year),
        key=lambda item: (item["start_date"], item["order"]),
    ):
        part_time = _allocate_proportionally(
            remaining,
            scheme["requested_part_time"],
        )
        remaining = [
            available - allocated
            for available, allocated in zip(remaining, part_time)
        ]
        full_time = _allocate_proportionally(
            remaining,
            scheme["requested_full_time"],
        )
        remaining = [
            available - allocated
            for available, allocated in zip(remaining, full_time)
        ]
        modelled_part_time = sum(part_time)
        modelled_full_time = sum(full_time)
        requested_total = (
            scheme["requested_full_time"] + scheme["requested_part_time"]
        )
        modelled_total = modelled_full_time + modelled_part_time
        allocations[scheme["key"]] = {
            "part_time": part_time,
            "full_time": full_time,
            "spec": scheme,
        }
        schemes[scheme["key"]] = {
            "contribution": scheme["contribution"],
            "start_date": scheme["start_date"],
            "end_date": scheme["end_date"],
            "requested_full_time": scheme["requested_full_time"],
            "requested_part_time": scheme["requested_part_time"],
            "requested_total": requested_total,
            "modelled_full_time": modelled_full_time,
            "modelled_part_time": modelled_part_time,
            "modelled_total": modelled_total,
            "unmodelled_total": requested_total - modelled_total,
        }

    requested_total = sum(row["requested_total"] for row in schemes.values())
    modelled_total = sum(row["modelled_total"] for row in schemes.values())
    plan = {
        "policy": "theoretical_only",
        "eligible_current_youth": sum(eligible_counts),
        "requested_total": requested_total,
        "modelled_total": modelled_total,
        "unmodelled_total": requested_total - modelled_total,
        "schemes": schemes,
    }
    return allocations, plan


def _project_rows(scenario, rows, as_of, include_holiday_pay=True):
    year = int(_scenario_value(scenario, "year", as_of.year))
    matrix = _scenario_value(scenario, "hours_matrix") or HOURS_MATRIX_DEFAULTS
    wage_rate = _decimal(
        _scenario_value(scenario, "wage_rate"),
        Decimal("32.01"),
    )
    vacancy_month = int(_scenario_value(scenario, "vacancy_start_month", 8))
    utilisation = _decimal(
        _scenario_value(scenario, "utilisation_pct", 100),
        Decimal("100"),
    ) / Decimal("100")
    if utilisation < 0:
        utilisation = Decimal("1")
    last_paid_programme_date = _scenario_last_paid_programme_date(scenario)
    allocations, subsidy_plan = _subsidy_allocations(rows, scenario, year)

    months = []
    school_totals = defaultdict(lambda: Decimal("0"))
    for month in _projection_months(year, as_of, last_paid_programme_date):
        working_dates = school_dates_in_month(
            year,
            month,
            start_from=as_of,
            end_on=last_paid_programme_date,
        )
        days = len(working_dates)
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
            # Subsidy-only youth leave payroll from their first qualifying paid
            # date onward and never automatically re-enter after scheme end.
            if not row.get("_vacancy"):
                for allocation in allocations.values():
                    if any(
                        working_date >= allocation["spec"]["start_date"]
                        for working_date in working_dates
                    ):
                        headcount -= allocation["part_time"][index]
                headcount = max(headcount, 0)
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
            relief = Decimal("0")
            if not row.get("_vacancy"):
                for allocation in allocations.values():
                    spec = allocation["spec"]
                    if any(
                        spec["start_date"] <= working_date <= spec["end_date"]
                        for working_date in working_dates
                    ):
                        relief_each = min(
                            spec["contribution"],
                            gross_each * UIF_FACTOR,
                        )
                        relief += relief_each * allocation["full_time"][index]
            net = gross + uif - relief

            month_gross += gross
            month_uif += uif
            month_relief += relief
            month_net += net
            school_totals[row.get("school_id")] += net

        months.append(
            {
                "month": month,
                # Exposed so the UI can explain costs without duplicating the
                # backend term calendar.
                "school_days": days,
                "working_dates": working_dates,
                "gross": _money(month_gross),
                "uif": _money(month_uif),
                "subsidy_relief": _money(month_relief),
                "net": _money(month_net),
            }
        )

    holiday_pay = (
        _decimal(_scenario_value(scenario, "holiday_pay"), Decimal("0"))
        if include_holiday_pay
        else Decimal("0")
    )
    return {
        "months": months,
        "total": _money(sum((row["net"] for row in months), Decimal("0")) + holiday_pay),
        "school_totals": {
            school_id: _money(total)
            for school_id, total in school_totals.items()
        },
        "subsidy_plan": subsidy_plan,
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
    subsidy_plan = committed.pop("subsidy_plan")
    committed["costed_youth"] = costed_youth
    committed["current_core_youth"] = costed_youth
    committed["open_posts"] = 0
    at_plan = _project_rows(scenario, active_rows + vacancy_rows, as_of)
    at_plan.pop("subsidy_plan")
    at_plan["costed_youth"] = costed_youth + open_posts
    at_plan["current_core_youth"] = costed_youth
    at_plan["open_posts"] = open_posts
    return {
        "committed": committed,
        "at_plan": at_plan,
        "subsidy_plan": subsidy_plan,
    }


def project_ringfenced(
    scenario,
    pots,
    ringfenced_rows,
    ringfenced_vacancies,
    as_of,
):
    """Return each active ringfenced pot's school-bound projection totals."""
    result = []
    for pot in pots:
        if not pot.is_active or not pot.is_ringfenced:
            continue

        schools = sorted(pot.schools.all(), key=lambda school: (school.name, school.id))
        school_ids = {school.id for school in schools}
        active_rows = [
            {**row, "nys_eligible_count": 0}
            for row in ringfenced_rows
            if row.get("school_id") in school_ids
        ]
        vacancy_rows = [
            {**row, "nys_eligible_count": 0, "_vacancy": True}
            for row in ringfenced_vacancies
            if row.get("school_id") in school_ids
        ]
        costed_youth = sum(
            max(int(row.get("headcount") or 0), 0)
            for row in active_rows
            if row.get("programme") != YEBO
        )
        open_posts = sum(
            max(int(row.get("headcount") or 0), 0)
            for row in vacancy_rows
        )
        committed = _project_rows(
            scenario,
            active_rows,
            as_of,
            include_holiday_pay=False,
        )
        at_plan = _project_rows(
            scenario,
            active_rows + vacancy_rows,
            as_of,
            include_holiday_pay=False,
        )
        amount = _money(_decimal(pot.amount))
        projected_at_plan = at_plan["total"]
        result.append(
            {
                "funder_name": pot.funder_name,
                "amount": amount,
                "schools": [school.name for school in schools],
                "costed_youth": costed_youth,
                "open_posts": open_posts,
                "projected_committed": committed["total"],
                "projected_at_plan": projected_at_plan,
                "surplus": _money(amount - projected_at_plan),
            }
        )
    return result


def project_ringfenced_summary(
    scenario,
    ringfenced_rows,
    ringfenced_vacancies,
    as_of,
):
    """Project the unique ringfenced population once for charting.

    Per-pot rows may overlap when funders share schools, so chart totals must
    use the union cohort produced by ``build_cohorts`` rather than summing the
    independent per-pot projections.
    """
    active_rows = [
        {**row, "nys_eligible_count": 0}
        for row in ringfenced_rows
    ]
    vacancy_rows = [
        {**row, "nys_eligible_count": 0, "_vacancy": True}
        for row in ringfenced_vacancies
    ]
    costed_youth = sum(
        max(int(row.get("headcount") or 0), 0)
        for row in active_rows
        if row.get("programme") != YEBO
    )
    open_posts = sum(
        max(int(row.get("headcount") or 0), 0)
        for row in vacancy_rows
    )
    committed = _project_rows(
        scenario,
        active_rows,
        as_of,
        include_holiday_pay=False,
    )
    committed["costed_youth"] = costed_youth
    committed["open_posts"] = 0
    at_plan = _project_rows(
        scenario,
        active_rows + vacancy_rows,
        as_of,
        include_holiday_pay=False,
    )
    at_plan["costed_youth"] = costed_youth + open_posts
    at_plan["open_posts"] = open_posts
    return {"committed": committed, "at_plan": at_plan}


def _expenditure_value(row, field, fallback=None):
    if isinstance(row, dict):
        return row.get(field, fallback)
    return getattr(row, field, fallback)


def build_mentor_estimate(expenditure_rows):
    """Average the latest three published mentor actuals for a monthly proxy."""
    latest = sorted(
        expenditure_rows,
        key=lambda row: int(_expenditure_value(row, "month", 0) or 0),
        reverse=True,
    )[:3]
    source_actuals = sorted(
        (
            {
                "month": int(_expenditure_value(row, "month", 0) or 0),
                "amount": _money(
                    _decimal(_expenditure_value(row, "mentor_amount", 0))
                ),
            }
            for row in latest
        ),
        key=lambda row: row["month"],
    )
    monthly_amount = Decimal("0")
    if source_actuals:
        monthly_amount = _money(
            sum(
                (row["amount"] for row in source_actuals),
                Decimal("0"),
            )
            / Decimal(len(source_actuals))
        )
    return {
        "method": "average_latest_3_actual_months",
        "monthly_amount": monthly_amount,
        "source_actuals": source_actuals,
    }


def build_spend_forecast(core_projection, rural_projection, mentor_estimate):
    """Combine committed core, mentor proxy, and rural costs by month."""
    rural_by_month = {
        row["month"]: row
        for row in rural_projection.get("months", [])
    }
    mentor_amount = _money(mentor_estimate.get("monthly_amount", Decimal("0")))
    months = []
    for core in core_projection.get("months", []):
        rural = rural_by_month.get(core["month"], {})
        core_amount = _money(_decimal(core.get("net")))
        rural_amount = _money(_decimal(rural.get("net")))
        months.append(
            {
                "month": core["month"],
                "working_days": core["school_days"],
                "working_dates": list(core.get("working_dates", [])),
                "core_amount": core_amount,
                "mentor_amount": mentor_amount,
                "rural_amount": rural_amount,
                "total": _money(core_amount + mentor_amount + rural_amount),
            }
        )
    return {
        "months": months,
        "mentor_estimate": mentor_estimate,
    }


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
        if not pot.is_active or pot.is_ringfenced:
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
