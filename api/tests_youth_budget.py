"""Tests for the Youth Budget Calculator backend.

The tests protect the financial rules, source-data normalization, permissions,
and response contract that the frontend will treat as authoritative.
"""
import unittest
from copy import deepcopy
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from api import youth_budget
from api.management.commands.sync_airtable_youth import Command as YouthSyncCommand
from api.models import (
    AirtableSyncLog,
    BudgetScenario,
    FundingPot,
    MonthlyYouthExpenditure,
    School,
    SchoolProgrammeYear,
    Youth,
)


def _make_user(username, role):
    """Use the existing profile signal so permission tests match production."""
    user = User.objects.create_user(username=username, password="x")
    user.profile.role = role
    user.profile.save()
    return user


def _scenario(**overrides):
    """Return a complete in-memory scenario for pure projection tests."""
    scenario = {
        "year": 2026,
        **youth_budget.default_scenario_values(),
        "sef_full_time_count": 0,
        "sef_part_time_count": 0,
    }
    scenario.update(overrides)
    return scenario


def _cohort(**overrides):
    """Return one paid active-youth cohort with safe defaults."""
    cohort = {
        "school_id": None,
        "site_type": "primary",
        "job_title": "literacy coach",
        "programme": "masi_literacy",
        "headcount": 1,
        "subsidised_count": 0,
        "nys_eligible_count": 0,
        "subsidy_end_date": None,
    }
    cohort.update(overrides)
    return cohort


class SchoolDaysTests(SimpleTestCase):
    """Term-day counts are the calendar foundation for every projected Rand."""

    def test_august_has_twenty_school_days(self):
        self.assertEqual(youth_budget.school_days_in_month(2026, 8), 20)

    def test_september_has_seventeen_school_days(self):
        self.assertEqual(youth_budget.school_days_in_month(2026, 9), 17)

    def test_october_has_nineteen_school_days(self):
        self.assertEqual(youth_budget.school_days_in_month(2026, 10), 19)

    def test_november_has_twenty_one_school_days(self):
        self.assertEqual(youth_budget.school_days_in_month(2026, 11), 21)

    def test_december_is_removed_by_the_horizon(self):
        self.assertEqual(youth_budget.school_days_in_month(2026, 12), 0)

    def test_july_from_the_twenty_eighth_has_four_school_days(self):
        self.assertEqual(
            youth_budget.school_days_in_month(
                2026,
                7,
                start_from=date(2026, 7, 28),
            ),
            4,
        )

    def test_mid_november_end_date_exposes_the_ten_exact_working_dates(self):
        dates = youth_budget.school_dates_in_month(
            2026,
            11,
            end_on=date(2026, 11, 14),
        )

        self.assertEqual(len(dates), 10)
        self.assertEqual(dates[0], date(2026, 11, 2))
        self.assertEqual(dates[-1], date(2026, 11, 13))
        self.assertNotIn(date(2026, 11, 14), dates)


class HoursMatrixTests(SimpleTestCase):
    """Defaults must cover live roster titles while unknown titles stay costed."""

    def test_defaults_cover_thirteen_titles_for_both_site_types(self):
        self.assertEqual(len(youth_budget.HOURS_MATRIX_DEFAULTS["primary"]), 13)
        self.assertEqual(len(youth_budget.HOURS_MATRIX_DEFAULTS["ecd"]), 13)

    def test_practitioners_are_five_and_a_half_hours_at_primary_sites(self):
        entry = youth_budget.HOURS_MATRIX_DEFAULTS["primary"]["practitioner"]
        self.assertEqual(entry["hours_per_day"], 5.5)
        self.assertEqual(entry["days_per_week"], 5)

    def test_missing_lookup_uses_four_and_a_half_hours_and_five_days(self):
        self.assertEqual(
            youth_budget.hours_for({}, "unknown", "assessor"),
            (Decimal("4.5"), Decimal("5")),
        )


class ProjectionTests(SimpleTestCase):
    """Projection tests isolate money math from the database and HTTP layer."""

    def test_theoretical_subsidy_relief_is_floored_at_zero_per_youth_month(self):
        matrix = {
            "primary": {
                "literacy coach": {
                    "hours_per_day": 0.1,
                    "days_per_week": 5,
                }
            }
        }
        result = youth_budget.project(
            _scenario(
                wage_rate=Decimal("1"),
                nys_subsidy_contribution=Decimal("1600"),
                hours_matrix=matrix,
                nys_full_time_count=1,
                nys_part_time_count=0,
            ),
            [_cohort(nys_eligible_count=1)],
            [],
            date(2026, 10, 1),
        )
        october = result["committed"]["months"][0]
        self.assertEqual(october["net"], Decimal("0.00"))
        self.assertEqual(
            october["subsidy_relief"],
            october["gross"] + october["uif"],
        )

    def test_employer_uif_is_one_percent_of_gross(self):
        matrix = {
            "primary": {
                "literacy coach": {
                    "hours_per_day": 1,
                    "days_per_week": 5,
                }
            }
        }
        result = youth_budget.project(
            _scenario(
                wage_rate=Decimal("10"),
                hours_matrix=matrix,
                nys_full_time_count=0,
                nys_part_time_count=0,
            ),
            [_cohort()],
            [],
            date(2026, 10, 1),
        )
        october = result["committed"]["months"][0]
        self.assertEqual(october["gross"], Decimal("190.00"))
        self.assertEqual(october["uif"], Decimal("1.90"))
        self.assertEqual(october["net"], Decimal("191.90"))

    def test_four_days_per_week_scales_gross_to_eighty_percent(self):
        five_days = youth_budget.project(
            _scenario(nys_full_time_count=0, nys_part_time_count=0),
            [_cohort()],
            [],
            date(2026, 10, 1),
        )
        matrix = deepcopy(youth_budget.HOURS_MATRIX_DEFAULTS)
        matrix["primary"]["literacy coach"]["days_per_week"] = 4
        four_days = youth_budget.project(
            _scenario(hours_matrix=matrix, nys_full_time_count=0, nys_part_time_count=0),
            [_cohort()],
            [],
            date(2026, 10, 1),
        )
        self.assertEqual(
            four_days["committed"]["months"][0]["gross"],
            Decimal("2189.48"),
        )

    def test_nys_conversion_starts_in_its_month_and_caps_at_eligible_count(self):
        result = youth_budget.project(
            _scenario(
                nys_subsidy_contribution=Decimal("100"),
                nys_full_time_count=10,
                nys_part_time_count=0,
                nys_start_date=date(2026, 9, 1),
            ),
            [_cohort(headcount=3, nys_eligible_count=3)],
            [],
            date(2026, 8, 1),
        )
        august, september = result["committed"]["months"][:2]
        self.assertEqual(august["subsidy_relief"], Decimal("0.00"))
        self.assertEqual(september["subsidy_relief"], Decimal("300.00"))

    def test_nys_and_sef_share_capacity_without_overlap(self):
        result = youth_budget.project(
            _scenario(
                nys_full_time_count=2,
                nys_part_time_count=0,
                nys_start_date=date(2026, 9, 1),
                sef_full_time_count=2,
                sef_part_time_count=0,
                sef_start_date=date(2026, 10, 1),
            ),
            [_cohort(headcount=3, nys_eligible_count=3)],
            [],
            date(2026, 9, 1),
        )

        plan = result["subsidy_plan"]
        self.assertEqual(plan["eligible_current_youth"], 3)
        self.assertEqual(plan["requested_total"], 4)
        self.assertEqual(plan["modelled_total"], 3)
        self.assertEqual(plan["unmodelled_total"], 1)
        self.assertEqual(plan["schemes"]["nys"]["modelled_total"], 2)
        self.assertEqual(plan["schemes"]["sef"]["modelled_total"], 1)

    def test_nys_wins_same_date_capacity_tie(self):
        result = youth_budget.project(
            _scenario(
                nys_full_time_count=1,
                nys_part_time_count=0,
                nys_start_date=date(2026, 10, 1),
                sef_full_time_count=1,
                sef_part_time_count=0,
                sef_start_date=date(2026, 10, 1),
            ),
            [_cohort(headcount=1, nys_eligible_count=1)],
            [],
            date(2026, 10, 1),
        )

        plan = result["subsidy_plan"]["schemes"]
        self.assertEqual(plan["nys"]["modelled_total"], 1)
        self.assertEqual(plan["sef"]["modelled_total"], 0)

    def test_part_time_allocates_before_full_time_within_scheme(self):
        result = youth_budget.project(
            _scenario(
                nys_full_time_count=1,
                nys_part_time_count=1,
                nys_start_date=date(2026, 9, 1),
            ),
            [_cohort(headcount=1, nys_eligible_count=1)],
            [],
            date(2026, 9, 1),
        )

        nys = result["subsidy_plan"]["schemes"]["nys"]
        self.assertEqual(nys["modelled_part_time"], 1)
        self.assertEqual(nys["modelled_full_time"], 0)

    def test_subsidy_after_programme_end_does_not_offset_earlier_wages(self):
        result = youth_budget.project(
            _scenario(
                nys_full_time_count=1,
                nys_part_time_count=0,
                nys_start_date=date(2026, 11, 30),
                nys_end_date=date(2026, 12, 31),
                last_paid_programme_date=date(2026, 11, 14),
            ),
            [_cohort(headcount=1, nys_eligible_count=1)],
            [],
            date(2026, 11, 1),
        )

        self.assertEqual(
            result["committed"]["months"][0]["subsidy_relief"],
            Decimal("0.00"),
        )

    def test_one_paid_boundary_date_activates_full_monthly_cap(self):
        result = youth_budget.project(
            _scenario(
                nys_subsidy_contribution=Decimal("100"),
                nys_full_time_count=1,
                nys_part_time_count=0,
                nys_start_date=date(2026, 11, 13),
                nys_end_date=date(2026, 11, 13),
                last_paid_programme_date=date(2026, 11, 14),
            ),
            [_cohort(headcount=1, nys_eligible_count=1)],
            [],
            date(2026, 11, 1),
        )

        self.assertEqual(
            result["committed"]["months"][0]["subsidy_relief"],
            Decimal("100.00"),
        )

    def test_vacancy_uses_ecd_hours_and_starts_in_selected_month(self):
        vacancy = _cohort(
            site_type="ecd",
            job_title="literacy coach",
            headcount=1,
            _vacancy=True,
        )
        result = youth_budget.project(
            _scenario(
                nys_full_time_count=0,
                nys_part_time_count=0,
                vacancy_start_month=9,
            ),
            [],
            [vacancy],
            date(2026, 8, 1),
        )
        august, september = result["at_plan"]["months"][:2]
        self.assertEqual(august["gross"], Decimal("0.00"))
        self.assertEqual(
            september["gross"],
            Decimal("2992.94"),
        )

    def test_projection_horizon_stops_after_november(self):
        result = youth_budget.project(
            _scenario(nys_full_time_count=0, nys_part_time_count=0),
            [_cohort()],
            [],
            date(2026, 8, 1),
        )
        self.assertEqual(
            [row["month"] for row in result["committed"]["months"]],
            [8, 9, 10, 11],
        )

    def test_last_paid_programme_date_caps_months_days_and_date_provenance(self):
        result = youth_budget.project(
            _scenario(
                nys_full_time_count=0,
                nys_part_time_count=0,
                last_paid_programme_date=date(2026, 11, 14),
            ),
            [_cohort()],
            [],
            date(2026, 9, 1),
        )

        months = result["committed"]["months"]
        self.assertEqual([row["month"] for row in months], [9, 10, 11])
        self.assertEqual(months[-1]["school_days"], 10)
        self.assertEqual(months[-1]["working_dates"][0], date(2026, 11, 2))
        self.assertEqual(months[-1]["working_dates"][-1], date(2026, 11, 13))

    def test_end_october_removes_november_from_the_projection(self):
        result = youth_budget.project(
            _scenario(
                nys_full_time_count=0,
                nys_part_time_count=0,
                last_paid_programme_date=date(2026, 10, 30),
            ),
            [_cohort()],
            [],
            date(2026, 9, 1),
        )

        self.assertEqual(
            [row["month"] for row in result["committed"]["months"]],
            [9, 10],
        )

    def test_holiday_pay_is_added_to_both_projection_totals(self):
        without_holiday = youth_budget.project(
            _scenario(nys_full_time_count=0,
                nys_part_time_count=0, holiday_pay=Decimal("0")),
            [_cohort()],
            [],
            date(2026, 10, 1),
        )
        with_holiday = youth_budget.project(
            _scenario(nys_full_time_count=0,
                nys_part_time_count=0, holiday_pay=Decimal("250")),
            [_cohort()],
            [],
            date(2026, 10, 1),
        )
        self.assertEqual(
            with_holiday["committed"]["total"],
            without_holiday["committed"]["total"] + Decimal("250"),
        )
        self.assertEqual(
            with_holiday["at_plan"]["total"],
            without_holiday["at_plan"]["total"] + Decimal("250"),
        )


class CohortTests(TestCase):
    """Cohorts must preserve paid population and subsidy provenance."""

    def setUp(self):
        self.school = School.objects.create(
            name="Cohort Primary",
            school_uid="SCH-YB-1",
            type="Primary School",
        )

    def _youth(self, employee_id, title, **extra):
        return Youth.objects.create(
            employee_id=employee_id,
            first_names="Test",
            last_name=str(employee_id),
            job_title=title,
            school=self.school,
            **extra,
        )

    def test_yebo_is_shown_in_notes_but_excluded_from_cost(self):
        self._youth(9001, "Literacy Coach")
        self._youth(9002, "Yeboneer")
        cohorts = youth_budget.build_cohorts(today=date(2026, 7, 27))
        result = youth_budget.project(
            _scenario(nys_full_time_count=0, nys_part_time_count=0),
            cohorts,
            [],
            date(2026, 10, 1),
        )
        self.assertEqual(cohorts["notes"]["active_total"], 2)
        self.assertEqual(cohorts["notes"]["yebo_shown_only"], 1)
        self.assertEqual(
            result["committed"]["months"][0]["gross"],
            Decimal("2736.86"),
        )

    def test_airtable_subsidy_does_not_change_theoretical_eligibility(self):
        self._youth(
            9003,
            "Literacy Coach",
            subsidy_funder="SEF",
            subsidy_status="Ended",
            subsidy_start_date=date(2026, 1, 1),
            subsidy_end_date=date(2026, 6, 30),
        )
        cohorts = youth_budget.build_cohorts(today=date(2026, 7, 27))
        row = cohorts["cohorts"][0]
        self.assertEqual(row["headcount"], 1)
        self.assertEqual(row["subsidised_count"], 0)
        self.assertEqual(row["nys_eligible_count"], 1)

    def test_airtable_subsidy_is_not_injected_into_projection_cohorts(self):
        self._youth(
            9004,
            "Literacy Coach",
            subsidy_funder="NYS",
            subsidy_status=" active ",
            subsidy_start_date=date(2026, 7, 1),
        )
        cohorts = youth_budget.build_cohorts(today=date(2026, 7, 27))
        self.assertEqual(cohorts["cohorts"][0]["subsidised_count"], 0)

    def test_airtable_subsidy_fields_do_not_change_any_projection_money(self):
        youth = self._youth(9008, "Literacy Coach")
        before = youth_budget.project(
            _scenario(nys_full_time_count=0, nys_part_time_count=0),
            youth_budget.build_cohorts(today=date(2026, 9, 1)),
            [],
            date(2026, 9, 1),
        )
        youth.subsidy_funder = "NYS"
        youth.subsidy_status = "Active"
        youth.subsidy_start_date = date(2026, 9, 1)
        youth.subsidy_end_date = date(2026, 12, 31)
        youth.save(update_fields=[
            "subsidy_funder",
            "subsidy_status",
            "subsidy_start_date",
            "subsidy_end_date",
        ])
        after = youth_budget.project(
            _scenario(nys_full_time_count=0, nys_part_time_count=0),
            youth_budget.build_cohorts(today=date(2026, 9, 1)),
            [],
            date(2026, 9, 1),
        )

        self.assertEqual(before, after)

    def test_school_less_note_counts_all_active_youth_without_a_school(self):
        Youth.objects.create(
            employee_id=9005,
            first_names="No",
            last_name="School",
            job_title="Assessor",
        )
        cohorts = youth_budget.build_cohorts(today=date(2026, 7, 27))
        self.assertEqual(cohorts["notes"]["school_less"], 1)
        self.assertEqual(
            cohorts["cohorts"][0]["programme"],
            youth_budget.SITE_UNASSIGNED,
        )

    def test_ringfenced_youth_are_separated_from_core_and_cannot_consume_nys(self):
        ringfenced_school = School.objects.create(
            name="Ringfenced Primary",
            school_uid="SCH-YB-RING-1",
            type="Primary School",
        )
        self._youth(9006, "Literacy Coach")
        Youth.objects.create(
            employee_id=9007,
            first_names="Rural",
            last_name="Youth",
            job_title="Literacy Coach",
            school=ringfenced_school,
        )

        cohorts = youth_budget.build_cohorts(
            today=date(2026, 7, 27),
            ringfenced_school_ids=frozenset({ringfenced_school.id}),
        )

        self.assertEqual(cohorts["notes"]["active_total"], 2)
        self.assertEqual(cohorts["notes"]["ringfenced"], 1)
        self.assertEqual(sum(row["headcount"] for row in cohorts["cohorts"]), 1)
        self.assertEqual(
            {row["school_id"] for row in cohorts["costing_cohorts"]},
            {self.school.id},
        )
        self.assertEqual(
            cohorts["ringfenced_costing_cohorts"][0]["school_id"],
            ringfenced_school.id,
        )
        self.assertEqual(
            cohorts["ringfenced_costing_cohorts"][0]["nys_eligible_count"],
            0,
        )


class VacancyTests(TestCase):
    """Vacancies come from positive grid gaps and never include Yebo posts."""

    def setUp(self):
        self.school = School.objects.create(
            name="Vacancy ECD",
            school_uid="SCH-YB-2",
            type="ECDC",
        )

    def test_build_vacancies_uses_programme_representative_title(self):
        SchoolProgrammeYear.objects.create(
            school=self.school,
            programme="preschool",
            year=2026,
            youth_planned=4,
            youth_active=1,
        )
        vacancies = youth_budget.build_vacancies(2026)
        self.assertEqual(len(vacancies["vacancies"]), 1)
        self.assertEqual(vacancies["vacancies"][0]["headcount"], 3)
        self.assertEqual(vacancies["vacancies"][0]["site_type"], "ecd")
        self.assertEqual(vacancies["vacancies"][0]["job_title"], "practitioner")
        self.assertEqual(vacancies["ringfenced_vacancies"], [])

    def test_build_vacancies_excludes_yebo(self):
        SchoolProgrammeYear.objects.create(
            school=self.school,
            programme="yebo",
            year=2026,
            youth_planned=10,
            youth_active=0,
        )
        self.assertEqual(
            youth_budget.build_vacancies(2026),
            {"vacancies": [], "ringfenced_vacancies": []},
        )

    def test_ringfenced_vacancy_is_separated_from_core(self):
        SchoolProgrammeYear.objects.create(
            school=self.school,
            programme="preschool",
            year=2026,
            youth_planned=4,
            youth_active=1,
        )

        vacancies = youth_budget.build_vacancies(
            2026,
            ringfenced_school_ids=frozenset({self.school.id}),
        )

        self.assertEqual(vacancies["vacancies"], [])
        self.assertEqual(len(vacancies["ringfenced_vacancies"]), 1)
        self.assertEqual(
            vacancies["ringfenced_vacancies"][0]["school_id"],
            self.school.id,
        )
        self.assertEqual(
            vacancies["ringfenced_vacancies"][0]["headcount"],
            3,
        )


class BudgetArithmeticTests(TestCase):
    """Verdicts and restrictions answer distinct management questions."""

    def setUp(self):
        self.school = School.objects.create(
            name="Restricted School",
            school_uid="SCH-YB-3",
            type="Primary School",
        )

    def test_verdict_deducts_mentor_reserve_and_projection(self):
        self.assertEqual(
            youth_budget.calculate_verdict(
                Decimal("1000"),
                Decimal("100"),
                Decimal("700"),
            ),
            Decimal("200.00"),
        )

    def test_feasibility_shortfall_is_unspendable_restricted_balance(self):
        pot = FundingPot.objects.create(
            year=2026,
            funder_name="Restricted",
            amount=Decimal("100"),
            as_of=date(2026, 7, 27),
        )
        pot.schools.add(self.school)
        ringfenced = FundingPot.objects.create(
            year=2026,
            funder_name="Ringfenced",
            amount=Decimal("100"),
            as_of=date(2026, 7, 27),
            is_ringfenced=True,
        )
        ringfenced.schools.add(self.school)
        rows = youth_budget.calculate_feasibility(
            [pot, ringfenced],
            {"school_totals": {self.school.id: Decimal("60")}},
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["funder_name"], "Restricted")
        self.assertEqual(rows[0]["projected_at_schools"], Decimal("60.00"))
        self.assertEqual(rows[0]["shortfall"], Decimal("40.00"))

    def test_unrestricted_and_inactive_pots_have_no_feasibility_row(self):
        unrestricted = FundingPot.objects.create(
            year=2026,
            funder_name="Unrestricted",
            amount=Decimal("100"),
            as_of=date(2026, 7, 27),
        )
        inactive = FundingPot.objects.create(
            year=2026,
            funder_name="Inactive",
            amount=Decimal("100"),
            as_of=date(2026, 7, 27),
            is_active=False,
        )
        inactive.schools.add(self.school)
        self.assertEqual(
            youth_budget.calculate_feasibility(
                [unrestricted, inactive],
                {"school_totals": {}},
            ),
            [],
        )

    def test_ringfenced_projection_reports_positive_and_negative_surplus(self):
        second_school = School.objects.create(
            name="Second Ringfenced School",
            school_uid="SCH-YB-RING-2",
            type="Primary School",
        )
        positive = FundingPot.objects.create(
            year=2026,
            funder_name="Positive Wind Farm",
            amount=Decimal("50000"),
            as_of=date(2026, 7, 27),
            is_ringfenced=True,
        )
        positive.schools.add(self.school)
        negative = FundingPot.objects.create(
            year=2026,
            funder_name="Negative Wind Farm",
            amount=Decimal("1"),
            as_of=date(2026, 7, 27),
            is_ringfenced=True,
        )
        negative.schools.add(second_school)
        inactive = FundingPot.objects.create(
            year=2026,
            funder_name="Inactive Wind Farm",
            amount=Decimal("999999"),
            as_of=date(2026, 7, 27),
            is_ringfenced=True,
            is_active=False,
        )
        inactive.schools.add(self.school)

        rows = [
            _cohort(school_id=self.school.id, headcount=1),
            _cohort(school_id=second_school.id, headcount=1),
        ]
        vacancies = [
            _cohort(
                school_id=self.school.id,
                headcount=2,
                _vacancy=True,
            ),
        ]
        projected = youth_budget.project_ringfenced(
            _scenario(nys_full_time_count=0, nys_part_time_count=0),
            [positive, negative, inactive],
            rows,
            vacancies,
            date(2026, 10, 1),
        )
        by_funder = {row["funder_name"]: row for row in projected}

        self.assertEqual(set(by_funder), {"Positive Wind Farm", "Negative Wind Farm"})
        self.assertEqual(by_funder["Positive Wind Farm"]["costed_youth"], 1)
        self.assertEqual(by_funder["Positive Wind Farm"]["open_posts"], 2)
        self.assertEqual(
            by_funder["Positive Wind Farm"]["schools"],
            [self.school.name],
        )
        for row in by_funder.values():
            self.assertEqual(
                row["surplus"],
                row["amount"] - row["projected_at_plan"],
            )
        self.assertGreater(by_funder["Positive Wind Farm"]["surplus"], 0)
        self.assertLess(by_funder["Negative Wind Farm"]["surplus"], 0)

    def test_ringfenced_summary_projects_the_unique_population_once(self):
        rows = [_cohort(school_id=self.school.id, headcount=2)]
        result = youth_budget.project_ringfenced_summary(
            _scenario(
                nys_full_time_count=0,
                nys_part_time_count=0,
                last_paid_programme_date=date(2026, 10, 30),
            ),
            rows,
            [],
            date(2026, 10, 1),
        )

        self.assertEqual(result["committed"]["costed_youth"], 2)
        self.assertEqual(result["committed"]["months"][0]["month"], 10)
        self.assertEqual(result["committed"]["months"][0]["school_days"], 19)


class MentorEstimateTests(SimpleTestCase):
    def test_latest_three_actual_mentor_months_form_the_monthly_estimate(self):
        estimate = youth_budget.build_mentor_estimate(
            [
                {"month": 5, "mentor_amount": Decimal("100")},
                {"month": 6, "mentor_amount": Decimal("200")},
                {"month": 7, "mentor_amount": Decimal("400")},
                {"month": 8, "mentor_amount": Decimal("600")},
            ]
        )

        self.assertEqual(estimate["monthly_amount"], Decimal("400.00"))
        self.assertEqual(
            estimate["source_actuals"],
            [
                {"month": 6, "amount": Decimal("200.00")},
                {"month": 7, "amount": Decimal("400.00")},
                {"month": 8, "amount": Decimal("600.00")},
            ],
        )

    def test_category_forecast_keeps_mentor_full_month_when_end_date_touches_month(self):
        core = youth_budget.project(
            _scenario(
                nys_full_time_count=0,
                nys_part_time_count=0,
                last_paid_programme_date=date(2026, 11, 14),
            ),
            [_cohort()],
            [],
            date(2026, 11, 1),
        )["committed"]
        rural = youth_budget.project_ringfenced_summary(
            _scenario(
                nys_full_time_count=0,
                nys_part_time_count=0,
                last_paid_programme_date=date(2026, 11, 14),
            ),
            [],
            [],
            date(2026, 11, 1),
        )["committed"]
        estimate = youth_budget.build_mentor_estimate(
            [
                {"month": 6, "mentor_amount": Decimal("60")},
                {"month": 7, "mentor_amount": Decimal("90")},
                {"month": 8, "mentor_amount": Decimal("150")},
            ]
        )

        forecast = youth_budget.build_spend_forecast(core, rural, estimate)

        self.assertEqual(len(forecast["months"]), 1)
        self.assertEqual(forecast["months"][0]["working_days"], 10)
        self.assertEqual(forecast["months"][0]["mentor_amount"], Decimal("100.00"))
        self.assertEqual(
            forecast["months"][0]["total"],
            forecast["months"][0]["core_amount"] + Decimal("100.00"),
        )


class ModelAndSyncTests(TestCase):
    """Schema defaults and Airtable mapping must preserve source intent."""

    def test_funding_pot_is_core_by_default(self):
        pot = FundingPot.objects.create(
            year=2026,
            funder_name="Core by default",
            amount=Decimal("100"),
            as_of=date(2026, 7, 27),
        )
        self.assertFalse(pot.is_ringfenced)

    def test_budget_scenario_defaults_use_current_subsidy_levers(self):
        scenario = BudgetScenario.objects.create(
            year=2026,
            **youth_budget.default_scenario_values(2026),
        )
        self.assertEqual(scenario.wage_rate, Decimal("32.01"))
        self.assertEqual(scenario.nys_subsidy_contribution, Decimal("1900"))
        self.assertEqual(scenario.nys_start_date, date(2026, 9, 1))
        self.assertEqual(scenario.nys_end_date, date(2026, 12, 31))
        self.assertEqual(scenario.sef_subsidy_contribution, Decimal("1400"))
        self.assertEqual(scenario.sef_full_time_count, 200)
        self.assertEqual(scenario.sef_start_date, date(2026, 10, 1))
        self.assertEqual(scenario.sef_end_date, date(2027, 3, 31))
        self.assertEqual(scenario.vacancy_start_month, 8)
        self.assertEqual(scenario.last_paid_programme_date, date(2026, 11, 30))

    def test_monthly_expenditure_is_unique_by_year_and_month(self):
        MonthlyYouthExpenditure.objects.create(year=2026, month=6)
        with self.assertRaises(IntegrityError), transaction.atomic():
            MonthlyYouthExpenditure.objects.create(year=2026, month=6)

    def test_sync_maps_first_lookup_value_and_parses_subsidy_dates(self):
        row = YouthSyncCommand().extract_row(
            {
                "fields": {
                    "Employee ID": 9100,
                    "Funder": ["NYS", "Ignored"],
                    "SEF (Current Status) (from Office Link)": ["Active"],
                    "SEF Start Date (from Office Link)": ["2026-08-01"],
                    "SEF End Date (from Office Link)": ["2027-01-31"],
                    "Hours Cap": 20,
                }
            },
            {},
            {},
        )
        self.assertEqual(row["subsidy_funder"], "NYS")
        self.assertEqual(row["subsidy_status"], "Active")
        self.assertEqual(row["subsidy_start_date"], date(2026, 8, 1))
        self.assertEqual(row["subsidy_end_date"], date(2027, 1, 31))
        self.assertNotIn("hours_cap", row)


class YouthBudgetEndpointTests(TestCase):
    """HTTP tests pin the shared-scenario contract and role boundary."""

    def setUp(self):
        self.client = APIClient()
        self.school = School.objects.create(
            name="Endpoint Primary",
            school_uid="SCH-YB-4",
            type="Primary School",
        )

    def _auth(self, role):
        user = _make_user(
            f"yb_{role.replace(' ', '_').lower()}_{User.objects.count()}",
            role,
        )
        self.client.force_authenticate(user=user)
        return user

    def test_authenticated_user_can_read_and_scenario_is_created(self):
        self._auth("MENTOR")
        response = self.client.get("/api/youth-budget/?year=2026")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(
            set(body),
            {
                "year",
                "as_of",
                "pots",
                "pots_total",
                "ringfenced",
                "scenario",
                "cohorts",
                "projections",
                "expenditure",
                "feasibility",
                "notes",
                "school_options",
                "spend_forecast",
                "subsidy_plan",
                "source_subsidies",
            },
        )
        for option in body["school_options"]:
            self.assertEqual(set(option), {"id", "name"})
        self.assertEqual(body["scenario"]["nys_conversion_start_month"], 9)
        self.assertEqual(body["scenario"]["vacancy_start_month"], 8)
        self.assertEqual(
            body["scenario"]["last_paid_programme_date"],
            "2026-11-30",
        )
        self.assertEqual(
            body["scenario"]["hours_matrix"],
            youth_budget.HOURS_MATRIX_DEFAULTS,
        )
        self.assertFalse(body["source_subsidies"]["available"])
        self.assertIsNone(
            body["source_subsidies"]["nys_tagged_active_employees"]
        )
        self.assertEqual(
            set(body["notes"]),
            {"active_total", "school_less", "yebo_shown_only", "ringfenced"},
        )
        self.assertTrue(BudgetScenario.objects.filter(year=2026).exists())

    def test_projection_response_has_the_frontend_contract(self):
        self._auth("MENTOR")
        response = self.client.get("/api/youth-budget/?year=2026")
        projections = response.json()["projections"]
        self.assertEqual(
            set(projections),
            {
                "committed",
                "at_plan",
                "verdict_committed",
                "verdict_at_plan",
            },
        )
        self.assertEqual(
            set(projections["committed"]),
            {
                "months",
                "total",
                "costed_youth",
                "current_core_youth",
                "open_posts",
            },
        )
        self.assertEqual(
            set(response.json()["spend_forecast"]),
            {"months", "mentor_estimate"},
        )

    def test_summary_segregates_ringfenced_money_youth_and_vacancies(self):
        self._auth("MENTOR")
        FundingPot.objects.create(
            year=2026,
            funder_name="Core Funder",
            amount=Decimal("1000"),
            as_of=date(2026, 7, 27),
        )
        ringfenced = FundingPot.objects.create(
            year=2026,
            funder_name="Rural Wind Farm",
            amount=Decimal("50000"),
            as_of=date(2026, 7, 27),
            is_ringfenced=True,
        )
        ringfenced.schools.add(self.school)
        Youth.objects.create(
            employee_id=9200,
            first_names="Ringfenced",
            last_name="Youth",
            job_title="Literacy Coach",
            school=self.school,
        )
        SchoolProgrammeYear.objects.create(
            school=self.school,
            programme="masi_literacy",
            year=2026,
            youth_planned=3,
            youth_active=1,
        )

        response = self.client.get("/api/youth-budget/?year=2026")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["pots_total"], 1000.0)
        self.assertEqual(
            set(body["ringfenced"]),
            {"pots", "total_amount", "youth", "projections"},
        )
        self.assertEqual(body["ringfenced"]["total_amount"], 50000.0)
        self.assertEqual(body["ringfenced"]["youth"], 1)
        self.assertEqual(len(body["ringfenced"]["pots"]), 1)
        ringfenced_row = body["ringfenced"]["pots"][0]
        self.assertEqual(
            set(ringfenced_row),
            {
                "funder_name",
                "amount",
                "schools",
                "costed_youth",
                "open_posts",
                "projected_committed",
                "projected_at_plan",
                "surplus",
            },
        )
        self.assertEqual(ringfenced_row["costed_youth"], 1)
        self.assertEqual(ringfenced_row["open_posts"], 2)
        self.assertGreater(
            ringfenced_row["projected_at_plan"],
            ringfenced_row["projected_committed"],
        )
        self.assertEqual(body["projections"]["committed"]["costed_youth"], 0)
        self.assertEqual(body["projections"]["committed"]["total"], 0.0)
        self.assertEqual(body["projections"]["at_plan"]["open_posts"], 0)
        self.assertEqual(body["projections"]["at_plan"]["total"], 0.0)
        serialized = {
            pot["funder_name"]: pot
            for pot in body["pots"]
        }
        self.assertEqual(
            set(serialized["Core Funder"]),
            {
                "id",
                "year",
                "funder_name",
                "amount",
                "as_of",
                "note",
                "schools",
                "is_active",
                "is_ringfenced",
                "created_at",
                "updated_at",
            },
        )
        self.assertFalse(serialized["Core Funder"]["is_ringfenced"])
        self.assertTrue(serialized["Rural Wind Farm"]["is_ringfenced"])

    def test_unauthenticated_read_is_rejected(self):
        response = self.client.get("/api/youth-budget/?year=2026")
        self.assertIn(response.status_code, (401, 403))

    def test_non_manager_cannot_write_any_budget_resource(self):
        self._auth("MENTOR")
        scenario = self.client.patch(
            "/api/youth-budget/scenario/",
            {"year": 2026, "holiday_pay": 10},
            format="json",
        )
        pot = self.client.post(
            "/api/youth-budget/pots/",
            {
                "year": 2026,
                "funder_name": "Denied",
                "amount": 10,
                "as_of": "2026-07-27",
            },
            format="json",
        )
        expenditure = self.client.post(
            "/api/youth-budget/expenditure/",
            {"year": 2026, "month": 7},
            format="json",
        )
        self.assertEqual(
            [scenario.status_code, pot.status_code, expenditure.status_code],
            [403, 403, 403],
        )

    def test_admin_can_patch_scenario(self):
        user = self._auth("ADMIN")
        response = self.client.patch(
            "/api/youth-budget/scenario/",
            {
                "year": 2026,
                "nys_full_time_count": 175,
                "nys_conversion_start_month": 9,
                "vacancy_start_month": 10,
                "holiday_pay": "2500.50",
                "last_paid_programme_date": "2026-11-14",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        scenario = BudgetScenario.objects.get(year=2026)
        self.assertEqual(scenario.nys_full_time_count, 175)
        self.assertEqual(scenario.nys_conversion_start_month, 9)
        self.assertEqual(scenario.nys_start_date, date(2026, 9, 1))
        self.assertEqual(scenario.vacancy_start_month, 10)
        self.assertEqual(scenario.holiday_pay, Decimal("2500.50"))
        self.assertEqual(scenario.last_paid_programme_date, date(2026, 11, 14))
        self.assertEqual(scenario.updated_by, user.username)

    def test_legacy_nys_write_updates_canonical_field_and_alias(self):
        self._auth("ADMIN")
        response = self.client.patch(
            "/api/youth-budget/scenario/",
            {
                "year": 2026,
                "subsidy_contribution": "1775",
                "nys_conversion_start_month": 10,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        scenario = BudgetScenario.objects.get(year=2026)
        self.assertEqual(scenario.nys_subsidy_contribution, Decimal("1775"))
        self.assertEqual(scenario.subsidy_contribution, Decimal("1775"))
        self.assertEqual(scenario.nys_start_date, date(2026, 10, 1))
        self.assertEqual(scenario.nys_conversion_start_month, 10)
        self.assertEqual(response.json()["nys_subsidy_contribution"], 1775.0)
        self.assertEqual(response.json()["subsidy_contribution"], 1775.0)

    def test_conflicting_legacy_and_canonical_fields_are_rejected(self):
        self._auth("ADMIN")
        response = self.client.patch(
            "/api/youth-budget/scenario/",
            {
                "year": 2026,
                "subsidy_contribution": "1775",
                "nys_subsidy_contribution": "1900",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(BudgetScenario.objects.filter(year=2026).exists())

    def test_partial_date_update_validates_against_saved_end_date(self):
        self._auth("ADMIN")
        self.client.get("/api/youth-budget/?year=2026")
        response = self.client.patch(
            "/api/youth-budget/scenario/",
            {"year": 2026, "nys_start_date": "2026-12-31"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        invalid = self.client.patch(
            "/api/youth-budget/scenario/",
            {"year": 2026, "nys_end_date": "2026-12-01"},
            format="json",
        )
        self.assertEqual(invalid.status_code, 400)

    def test_complete_source_receipt_exposes_bounded_airtable_counts(self):
        self._auth("MENTOR")
        Youth.objects.create(
            employee_id=9301,
            full_name="NYS Source",
            employment_status="Active",
            subsidy_funder="NYS",
        )
        Youth.objects.create(
            employee_id=9302,
            full_name="SEF Source",
            employment_status="Active",
            subsidy_funder="SEF",
            subsidy_status="Active",
        )
        receipt = AirtableSyncLog.objects.create(
            sync_type="youth",
            details={
                "subsidy_enrichment": {
                    "contract_version": "youth_subsidy_enrichment_v1",
                    "complete": True,
                    "matched": 2,
                    "missing_link": 0,
                    "multiple_links": 0,
                    "missing_target": 0,
                }
            },
        )
        receipt.mark_complete(success=True)

        source = self.client.get(
            "/api/youth-budget/?year=2026"
        ).json()["source_subsidies"]

        self.assertTrue(source["available"])
        self.assertTrue(source["latest_attempt_succeeded"])
        self.assertEqual(source["nys_tagged_active_employees"], 1)
        self.assertEqual(source["sef_active_status_employees"], 1)

    def test_scenario_rejects_invalid_month_and_negative_money(self):
        self._auth("ADMIN")
        invalid_month = self.client.patch(
            "/api/youth-budget/scenario/",
            {"year": 2026, "vacancy_start_month": 13},
            format="json",
        )
        negative = self.client.patch(
            "/api/youth-budget/scenario/",
            {"year": 2026, "mentor_reserve": -1},
            format="json",
        )
        self.assertEqual(invalid_month.status_code, 400)
        self.assertEqual(negative.status_code, 400)

    @patch("api.views.youth_budget.timezone.localdate", return_value=date(2026, 9, 1))
    def test_authenticated_preview_recalculates_without_saving(self, _localdate):
        self._auth("MENTOR")
        saved = BudgetScenario.objects.create(
            year=2026,
            **youth_budget.default_scenario_values(2026),
        )
        for month, amount in ((5, "10"), (6, "20"), (7, "40"), (8, "60")):
            MonthlyYouthExpenditure.objects.create(
                year=2026,
                month=month,
                mentor_amount=Decimal(amount),
            )

        response = self.client.post(
            "/api/youth-budget/preview/",
            {
                "year": 2026,
                "last_paid_programme_date": "2026-11-14",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(
            set(body),
            {
                "projections",
                "ringfenced_projections",
                "ringfenced_pots",
                "spend_forecast",
                "feasibility",
                "subsidy_plan",
            },
        )
        self.assertEqual(
            body["projections"]["committed"]["months"][-1]["school_days"],
            10,
        )
        self.assertEqual(
            body["spend_forecast"]["mentor_estimate"]["source_actuals"],
            [
                {"month": 6, "amount": 20.0},
                {"month": 7, "amount": 40.0},
                {"month": 8, "amount": 60.0},
            ],
        )
        self.assertEqual(
            body["spend_forecast"]["mentor_estimate"]["monthly_amount"],
            40.0,
        )
        saved.refresh_from_db()
        self.assertEqual(saved.last_paid_programme_date, date(2026, 11, 30))

    def test_preview_rejects_an_end_date_after_the_supported_horizon(self):
        self._auth("MENTOR")
        response = self.client.post(
            "/api/youth-budget/preview/",
            {
                "year": 2026,
                "last_paid_programme_date": "2026-12-01",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_project_manager_can_create_patch_and_delete_pot(self):
        self._auth("PROJECT MANAGER")
        created = self.client.post(
            "/api/youth-budget/pots/",
            {
                "year": 2026,
                "funder_name": "Endpoint Funder",
                "amount": "1000.00",
                "as_of": "2026-07-27",
                "schools": [self.school.id],
                "is_ringfenced": True,
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        pot_id = created.json()["id"]
        self.assertTrue(created.json()["is_ringfenced"])
        self.assertEqual(
            created.json()["schools"],
            [{"id": self.school.id, "name": self.school.name}],
        )
        patched = self.client.patch(
            f"/api/youth-budget/pots/{pot_id}/",
            {
                "amount": "900.00",
                "schools": [],
                "is_ringfenced": False,
            },
            format="json",
        )
        self.assertEqual(patched.status_code, 200)
        self.assertEqual(patched.json()["amount"], 900.0)
        self.assertEqual(patched.json()["schools"], [])
        self.assertFalse(patched.json()["is_ringfenced"])
        deleted = self.client.delete(
            f"/api/youth-budget/pots/{pot_id}/"
        )
        self.assertEqual(deleted.status_code, 204)
        self.assertFalse(FundingPot.objects.filter(pk=pot_id).exists())

    def test_project_manager_can_create_and_patch_expenditure(self):
        self._auth("PROJECT MANAGER")
        created = self.client.post(
            "/api/youth-budget/expenditure/",
            {
                "year": 2026,
                "month": 7,
                "core_amount": "100.00",
                "mentor_amount": "20.00",
                "rural_amount": "5.00",
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["total"], 125.0)
        patched = self.client.patch(
            f"/api/youth-budget/expenditure/{created.json()['id']}/",
            {"mentor_amount": "30.00"},
            format="json",
        )
        self.assertEqual(patched.status_code, 200)
        self.assertEqual(patched.json()["total"], 135.0)

    def test_pot_rejects_unknown_school_id(self):
        self._auth("ADMIN")
        response = self.client.post(
            "/api/youth-budget/pots/",
            {
                "year": 2026,
                "funder_name": "Bad restriction",
                "amount": 100,
                "as_of": "2026-07-27",
                "schools": [999999],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(
            FundingPot.objects.filter(funder_name="Bad restriction").exists()
        )

    def test_pot_rejects_non_boolean_ringfenced_flag(self):
        self._auth("ADMIN")
        response = self.client.post(
            "/api/youth-budget/pots/",
            {
                "year": 2026,
                "funder_name": "Bad ringfenced flag",
                "amount": 100,
                "as_of": "2026-07-27",
                "is_ringfenced": "true",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(
            FundingPot.objects.filter(
                funder_name="Bad ringfenced flag",
            ).exists()
        )


class FundingPotSeedTests(TestCase):
    """The known balances and UTS restriction must be reproducible."""

    def setUp(self):
        self.active_schools = []
        for index, name in enumerate(
            ("Astra", "Isaac Booi", "Green Apple", "Noluthando"),
            start=1,
        ):
            if name == "Astra":
                School.objects.create(
                    name=name,
                    school_uid="SCH-YB-INACTIVE",
                    type="Primary School",
                    is_active=False,
                )
            self.active_schools.append(
                School.objects.create(
                    name=name,
                    school_uid=f"SCH-YB-SEED-{index}",
                    type="Primary School",
                    is_active=True,
                )
            )

    def test_seed_creates_exact_pot_total_and_active_restrictions(self):
        call_command("seed_funding_pots_2026", verbosity=0)
        pots = FundingPot.objects.filter(year=2026)
        # 8 urban pots plus 3 rural wind-farm placeholders seeded at R0.
        self.assertEqual(pots.count(), 11)
        self.assertEqual(
            sum((pot.amount for pot in pots), Decimal("0")),
            Decimal("1523777.96"),
        )
        self.assertEqual(
            set(
                pots.filter(is_ringfenced=True).values_list(
                    "funder_name",
                    flat=True,
                )
            ),
            {
                "Kouga Wind Farm",
                "Tsitsikamma Wind Farm",
                "Amakhala Emoyeni Wind Farm",
            },
        )
        uts = pots.get(funder_name="United Through Sport")
        self.assertEqual(
            set(uts.schools.values_list("id", flat=True)),
            {school.id for school in self.active_schools},
        )

    def test_seed_is_idempotent(self):
        call_command("seed_funding_pots_2026", verbosity=0)
        call_command("seed_funding_pots_2026", verbosity=0)
        self.assertEqual(FundingPot.objects.filter(year=2026).count(), 11)


SAMPLE_LEDGER = Path(__file__).resolve().parent / "testdata" / "youth-payments-sample.csv"
# The real ledger holds actual payroll data (names, amounts) and is deliberately
# gitignored, so it exists only on machines that placed it there. Tests that use
# it must skip cleanly everywhere else instead of erroring.
REAL_LEDGER = (
    Path(__file__).resolve().parent.parent
    / "staticfiles" / "data" / "youth-payments-jan-june-2026.csv"
)


class ExpenditureSeedTests(TestCase):
    """The sanitized fixture proves BOM, currency, trailing-space month, and
    classification handling without depending on the gitignored real ledger."""

    def _seed(self):
        call_command(
            "seed_youth_expenditure_2026", path=str(SAMPLE_LEDGER), verbosity=0
        )

    def test_fixture_classifies_core_mentor_and_rural(self):
        self._seed()
        june = MonthlyYouthExpenditure.objects.get(year=2026, month=6)
        self.assertEqual(june.core_amount, Decimal("1000.50"))
        # Mentor beats Rural: an "LC Mentor (Rural)" payment is a mentor salary.
        self.assertEqual(june.mentor_amount, Decimal("2300.00"))
        self.assertEqual(june.rural_amount, Decimal("500.00"))

    def test_fixture_trailing_space_april_is_trimmed(self):
        self._seed()
        april = MonthlyYouthExpenditure.objects.get(year=2026, month=4)
        self.assertEqual(april.core_amount, Decimal("750.25"))

    def test_fixture_seed_is_idempotent(self):
        self._seed()
        self._seed()
        self.assertEqual(
            MonthlyYouthExpenditure.objects.filter(year=2026).count(), 3
        )


@unittest.skipUnless(REAL_LEDGER.exists(), "real payroll ledger not on this machine")
class RealLedgerSeedTests(TestCase):
    """Integration check against the actual (gitignored) finance export."""

    def test_real_csv_parses_june_total_and_trimmed_april(self):
        call_command("seed_youth_expenditure_2026", verbosity=0)
        june = MonthlyYouthExpenditure.objects.get(year=2026, month=6)
        self.assertEqual(
            june.core_amount + june.mentor_amount + june.rural_amount,
            Decimal("408520.12"),
        )
        self.assertTrue(
            MonthlyYouthExpenditure.objects.filter(year=2026, month=4).exists()
        )


class SubsidyOnlyLeverTests(SimpleTestCase):
    """Subsidy-only part-timers work only the hours SEF/NYS pays for and never
    touch Masi payroll: their cost is exactly R0 (no gross, no UIF), not merely
    the R1,600 top-up relief. Interim lever until an Employment Basis column
    exists in Airtable (Jim, 2026-07-28)."""

    def test_subsidy_only_converts_leave_the_costed_population(self):
        base = youth_budget.project(
            _scenario(
                nys_full_time_count=0,
                nys_part_time_count=0,
                nys_start_date=date(2026, 8, 1),
            ),
            [_cohort(headcount=4, nys_eligible_count=4)],
            [],
            date(2026, 8, 1),
        )
        with_lever = youth_budget.project(
            _scenario(
                nys_full_time_count=0,
                nys_part_time_count=2,
                nys_start_date=date(2026, 8, 1),
            ),
            [_cohort(headcount=4, nys_eligible_count=4)],
            [],
            date(2026, 8, 1),
        )
        august_base = base["committed"]["months"][0]
        august_lever = with_lever["committed"]["months"][0]
        # Two of four youth drop off payroll entirely: gross halves, no relief.
        self.assertEqual(august_lever["gross"], august_base["gross"] / 2)
        self.assertEqual(august_lever["subsidy_relief"], Decimal("0.00"))
        self.assertEqual(august_lever["net"], august_base["net"] / 2)

    def test_split_between_zero_cost_and_topup_conversions(self):
        result = youth_budget.project(
            _scenario(
                nys_subsidy_contribution=Decimal("100"),
                nys_full_time_count=2,
                nys_part_time_count=1,
                nys_start_date=date(2026, 8, 1),
            ),
            [_cohort(headcount=4, nys_eligible_count=4)],
            [],
            date(2026, 8, 1),
        )
        august = result["committed"]["months"][0]
        # 1 youth vanishes from payroll; 2 of the remaining 3 earn relief.
        self.assertEqual(august["subsidy_relief"], Decimal("200.00"))
        full_gross = youth_budget.project(
            _scenario(
                nys_full_time_count=0,
                nys_part_time_count=0,
                nys_start_date=date(2026, 8, 1),
            ),
            [_cohort(headcount=4, nys_eligible_count=4)],
            [],
            date(2026, 8, 1),
        )["committed"]["months"][0]["gross"]
        self.assertEqual(august["gross"], full_gross * 3 / 4)

    def test_part_time_clamped_to_eligible_and_starts_in_month(self):
        # PT requested above the eligible pool clamps to it: both eligible
        # youth leave the costed population, but only from the start month.
        result = youth_budget.project(
            _scenario(
                nys_full_time_count=0,
                nys_part_time_count=5,
                nys_start_date=date(2026, 9, 1),
            ),
            [_cohort(headcount=2, nys_eligible_count=2)],
            [],
            date(2026, 8, 1),
        )
        august, september = result["committed"]["months"][:2]
        base = youth_budget.project(
            _scenario(nys_full_time_count=0, nys_part_time_count=0),
            [_cohort(headcount=2, nys_eligible_count=2)],
            [],
            date(2026, 8, 1),
        )["committed"]["months"]
        self.assertEqual(august["gross"], base[0]["gross"])
        self.assertEqual(september["gross"], Decimal("0.00"))
        self.assertEqual(september["subsidy_relief"], Decimal("0.00"))

    def test_part_time_end_date_does_not_reenter_masi_payroll(self):
        common = {
            "nys_full_time_count": 0,
            "nys_part_time_count": 1,
            "nys_start_date": date(2026, 9, 1),
        }
        september_end = youth_budget.project(
            _scenario(**common, nys_end_date=date(2026, 9, 30)),
            [_cohort(headcount=1, nys_eligible_count=1)],
            [],
            date(2026, 10, 1),
        )
        december_end = youth_budget.project(
            _scenario(**common, nys_end_date=date(2026, 12, 31)),
            [_cohort(headcount=1, nys_eligible_count=1)],
            [],
            date(2026, 10, 1),
        )

        self.assertEqual(
            september_end["committed"]["months"],
            december_end["committed"]["months"],
        )


class UtilisationLeverTests(SimpleTestCase):
    """Utilisation discounts full-cap gross for absenteeism and cancelled
    school days (Jim 2026-07-28); relief stays capped at the reduced cost so
    a subsidised youth can never produce negative net."""

    def test_fifty_percent_utilisation_halves_gross(self):
        base = youth_budget.project(
            _scenario(nys_full_time_count=0, nys_part_time_count=0),
            [_cohort(headcount=2)],
            [],
            date(2026, 8, 1),
        )["committed"]["months"][0]
        halved = youth_budget.project(
            _scenario(nys_full_time_count=0,
                nys_part_time_count=0, utilisation_pct=50),
            [_cohort(headcount=2)],
            [],
            date(2026, 8, 1),
        )["committed"]["months"][0]
        self.assertEqual(halved["gross"], base["gross"] / 2)
        self.assertEqual(halved["net"], base["net"] / 2)

    def test_relief_caps_at_reduced_cost(self):
        # At 10% utilisation a youth earns far less than the contribution;
        # relief must cap at their full (reduced) cost, never exceed it.
        result = youth_budget.project(
            _scenario(
                nys_full_time_count=1,
                nys_part_time_count=0,
                utilisation_pct=10,
                nys_subsidy_contribution=Decimal("1600"),
                nys_start_date=date(2026, 8, 1),
            ),
            [_cohort(headcount=1, nys_eligible_count=1)],
            [],
            date(2026, 8, 1),
        )["committed"]["months"][0]
        self.assertEqual(result["net"], Decimal("0.00"))

    def test_zazi_default_hours_are_three_and_a_half(self):
        matrix = youth_budget.HOURS_MATRIX_DEFAULTS
        for site_type in ("primary", "ecd"):
            for title in ("zazi izandi coach", "zz ecd coach", "literacy coaches (zz)"):
                self.assertEqual(
                    matrix[site_type][title]["hours_per_day"], 3.5,
                    f"{site_type}/{title}",
                )
        self.assertEqual(matrix["primary"]["literacy coach"]["hours_per_day"], 4.5)
        self.assertEqual(matrix["ecd"]["literacy coach"]["hours_per_day"], 5.5)
