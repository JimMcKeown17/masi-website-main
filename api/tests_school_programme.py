"""Tests for the School Programme Grid (Increment 1, within-Masi).

Logic under test lives in api/school_programme.py. Mirrors the house pattern of
per-feature test modules (tests_wig.py, tests_closures.py).
"""
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase

from api.school_programme import normalize_site_type, is_grid_eligible


def _make_user(username, role):
    """Create a User with a UserProfile role. The profile is auto-created by a
    post-save signal; we mutate the role on the cached relation (house pattern)."""
    user = User.objects.create_user(username=username, password="x")
    user.profile.role = role
    user.profile.save()
    return user


class NormalizeSiteTypeTests(SimpleTestCase):
    """Canonical site-type = normalize(School.type) -> {Primary, ECD, Secondary}.

    Prod-verified inputs (2026-06-18): Primary School (167), ECDC (121),
    Secondary School (49), ECD (3), Primary (1), blank (1). See plan section 6.
    """

    def test_maps_primary_variants(self):
        self.assertEqual(normalize_site_type("Primary School"), "Primary")
        self.assertEqual(normalize_site_type("Primary"), "Primary")

    def test_maps_ecd_variants(self):
        self.assertEqual(normalize_site_type("ECDC"), "ECD")
        self.assertEqual(normalize_site_type("ECD"), "ECD")

    def test_maps_secondary(self):
        self.assertEqual(normalize_site_type("Secondary School"), "Secondary")

    def test_tolerates_case_and_whitespace(self):
        self.assertEqual(normalize_site_type("  primary school "), "Primary")
        self.assertEqual(normalize_site_type("ecdc"), "ECD")

    def test_returns_none_for_blank_or_unknown(self):
        self.assertIsNone(normalize_site_type(""))
        self.assertIsNone(normalize_site_type(None))
        self.assertIsNone(normalize_site_type("Other"))
        self.assertIsNone(normalize_site_type("Office"))


class IsGridEligibleTests(SimpleTestCase):
    """The programme grid covers Primary + ECD sites only; Secondary
    (Top Learners high schools) and unknown types are excluded (plan section 6.4).
    """

    def test_primary_and_ecd_are_eligible(self):
        self.assertTrue(is_grid_eligible("Primary School"))
        self.assertTrue(is_grid_eligible("ECDC"))

    def test_secondary_excluded(self):
        self.assertFalse(is_grid_eligible("Secondary School"))

    def test_unknown_or_blank_excluded(self):
        self.assertFalse(is_grid_eligible(None))
        self.assertFalse(is_grid_eligible(""))
        self.assertFalse(is_grid_eligible("Other"))


class SchoolProgrammeYearModelTests(TestCase):
    """Line-item grain: school x programme x year (plan section 4a)."""

    def setUp(self):
        from api.models import School

        self.school = School.objects.create(
            name="Test Primary", school_uid="SCH-09001", type="Primary School"
        )

    def test_unique_school_programme_year(self):
        from api.models import SchoolProgrammeYear

        SchoolProgrammeYear.objects.create(
            school=self.school, programme="masi_literacy", year=2026
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            SchoolProgrammeYear.objects.create(
                school=self.school, programme="masi_literacy", year=2026
            )

    def test_same_programme_distinct_years_allowed(self):
        from api.models import SchoolProgrammeYear

        SchoolProgrammeYear.objects.create(
            school=self.school, programme="numeracy", year=2025
        )
        SchoolProgrammeYear.objects.create(
            school=self.school, programme="numeracy", year=2026
        )
        self.assertEqual(SchoolProgrammeYear.objects.count(), 2)

    def test_system_and_human_defaults(self):
        from api.models import SchoolProgrammeYear

        row = SchoolProgrammeYear.objects.create(
            school=self.school, programme="numeracy", year=2026
        )
        # Human-owned fields start empty (awaiting entry / computation).
        self.assertIsNone(row.children_count)
        self.assertIsNone(row.youth_planned)
        self.assertIsNone(row.percent_of_school)
        # System-owned youth_active defaults to 0 (no staff = zero, not unknown).
        self.assertEqual(row.youth_active, 0)
        # Conservative ownership default: manual unless the config marks computed.
        self.assertEqual(row.count_source, "manual")

    def test_str_includes_school_programme_year(self):
        from api.models import SchoolProgrammeYear

        row = SchoolProgrammeYear.objects.create(
            school=self.school, programme="edutech", year=2026
        )
        text = str(row)
        self.assertIn("edutech", text)
        self.assertIn("2026", text)


class SchoolYearStatsModelTests(TestCase):
    """School grain: school x year (plan section 4b)."""

    def setUp(self):
        from api.models import School

        self.school = School.objects.create(
            name="Test ECD", school_uid="SCH-09002", type="ECDC"
        )

    def test_unique_school_year(self):
        from api.models import SchoolYearStats

        SchoolYearStats.objects.create(school=self.school, year=2026)
        with self.assertRaises(IntegrityError), transaction.atomic():
            SchoolYearStats.objects.create(school=self.school, year=2026)

    def test_derived_and_human_fields_start_null(self):
        from api.models import SchoolYearStats

        stats = SchoolYearStats.objects.create(school=self.school, year=2026)
        self.assertIsNone(stats.total_kids_in_school)
        self.assertIsNone(stats.pct_female)
        self.assertIsNone(stats.unique_beneficiaries)
        self.assertIsNone(stats.pct_african)


class ProgrammeForJobTitleTests(SimpleTestCase):
    """The section 5 job-title -> programme lookup. All 14 prod titles covered."""

    def test_maps_core_titles(self):
        from api.school_programme import programme_for_job_title

        cases = {
            "Literacy Coach": "masi_literacy",
            "Numeracy Coach": "numeracy",
            "Count Coach": "numeracy",
            "Zazi Izandi Coach": "zazi_izandi",
            "ZZ ECD Coach": "zazi_izandi",
            "1000 Stories Youth": "thousand_stories",
            "EduTech Coach": "edutech",
            "Yeboneer": "yebo",
            "Sport & Arts Coach": "sport_arts",
            "Homework Coach": "homework",
            "Practitioner": "preschool",
            "ECD Practitioner": "preschool",
        }
        for title, programme in cases.items():
            self.assertEqual(programme_for_job_title(title), programme, title)

    def test_zz_mislabel_routes_to_zazi(self):
        from api.school_programme import programme_for_job_title

        self.assertEqual(programme_for_job_title("Literacy Coaches (ZZ)"), "zazi_izandi")

    def test_site_unassigned_titles(self):
        from api.school_programme import programme_for_job_title, SITE_UNASSIGNED

        self.assertEqual(programme_for_job_title("Assessor"), SITE_UNASSIGNED)
        self.assertEqual(programme_for_job_title("Yes Intern"), SITE_UNASSIGNED)

    def test_unmapped_returns_none(self):
        from api.school_programme import programme_for_job_title

        self.assertIsNone(programme_for_job_title("Chief Vibes Officer"))
        self.assertIsNone(programme_for_job_title(""))
        self.assertIsNone(programme_for_job_title(None))

    def test_case_and_whitespace_tolerant(self):
        from api.school_programme import programme_for_job_title

        self.assertEqual(programme_for_job_title("  literacy coach "), "masi_literacy")


class ComputeYouthActiveTests(TestCase):
    """youth_active snapshot per school x programme from the Youth table (section 5)."""

    def setUp(self):
        from api.models import School

        self.primary = School.objects.create(
            name="P1", school_uid="SCH-09100", type="Primary School"
        )
        self._next_eid = 90000

    def _youth(self, **kw):
        from api.models import Youth

        self._next_eid += 1
        defaults = dict(
            employee_id=self._next_eid,
            first_names="A",
            last_name="B",
            employment_status="Active",
        )
        defaults.update(kw)
        return Youth.objects.create(**defaults)

    def test_counts_active_site_assigned_per_school_programme(self):
        from api.school_programme import compute_youth_active

        self._youth(job_title="Literacy Coach", school=self.primary)
        self._youth(job_title="Literacy Coach", school=self.primary)
        self._youth(job_title="Numeracy Coach", school=self.primary)
        result = compute_youth_active()
        self.assertEqual(
            result["by_school_programme"][(self.primary.id, "masi_literacy")], 2
        )
        self.assertEqual(
            result["by_school_programme"][(self.primary.id, "numeracy")], 1
        )

    def test_inactive_youth_with_null_end_date_not_counted(self):
        # Plan section 12: an Inactive youth (even with null end_date) is not active
        # and must not produce a false vacancy/active count.
        from api.school_programme import compute_youth_active

        self._youth(
            job_title="Literacy Coach",
            school=self.primary,
            employment_status="Inactive",
            end_date=None,
        )
        result = compute_youth_active()
        self.assertNotIn(
            (self.primary.id, "masi_literacy"), result["by_school_programme"]
        )

    def test_site_unassigned_youth_go_to_roster_not_grid(self):
        from api.school_programme import compute_youth_active

        self._youth(job_title="Assessor", school=None)
        self._youth(job_title="Yes Intern", school=None)
        result = compute_youth_active()
        self.assertEqual(result["roster"]["Assessor"], 1)
        self.assertEqual(result["roster"]["Yes Intern"], 1)
        self.assertEqual(result["by_school_programme"], {})

    def test_unmapped_title_surfaced_not_dropped(self):
        from api.school_programme import compute_youth_active

        self._youth(job_title="Mystery Role", school=self.primary)
        result = compute_youth_active()
        self.assertEqual(result["unmapped"]["Mystery Role"], 1)

    def test_site_assigned_youth_without_school_flagged(self):
        from api.school_programme import compute_youth_active

        self._youth(job_title="Literacy Coach", school=None)
        result = compute_youth_active()
        self.assertEqual(result["site_assigned_no_school"]["Literacy Coach"], 1)
        self.assertEqual(result["by_school_programme"], {})


class UniqueBeneficiariesTests(SimpleTestCase):
    """The section 7 dedup rule -- the #1 Codex finding: count DISTINCT identities,
    never sum aggregate counts (which double-counts a child on two programmes).
    """

    def test_cross_programme_duplicate_counted_once(self):
        from api.school_programme import unique_beneficiaries_from_identities

        literacy = {"CH-1", "CH-2", "CH-3"}
        numeracy = {"CH-3", "CH-4"}  # CH-3 is on both programmes
        result = unique_beneficiaries_from_identities(
            [literacy, numeracy], has_whole_school=False, total_kids=None
        )
        self.assertEqual(result, 4)  # CH-1..CH-4, CH-3 only once (NOT 3+2=5)

    def test_whole_school_programme_uses_total_kids(self):
        from api.school_programme import unique_beneficiaries_from_identities

        result = unique_beneficiaries_from_identities(
            [{"CH-1"}], has_whole_school=True, total_kids=200
        )
        self.assertEqual(result, 200)

    def test_capped_at_total_kids(self):
        from api.school_programme import unique_beneficiaries_from_identities

        result = unique_beneficiaries_from_identities(
            [{"CH-1", "CH-2", "CH-3"}], has_whole_school=False, total_kids=2
        )
        self.assertEqual(result, 2)

    def test_no_total_kids_returns_union_count(self):
        from api.school_programme import unique_beneficiaries_from_identities

        result = unique_beneficiaries_from_identities(
            [{"CH-1", "CH-2"}], has_whole_school=False, total_kids=None
        )
        self.assertEqual(result, 2)

    def test_whole_school_without_total_kids_falls_back_to_union(self):
        # The whole-school override needs an enrolment figure; absent it, we cannot
        # claim "everyone", so fall back to the honest identity union.
        from api.school_programme import unique_beneficiaries_from_identities

        result = unique_beneficiaries_from_identities(
            [{"CH-1", "CH-2"}], has_whole_school=True, total_kids=None
        )
        self.assertEqual(result, 2)


class MasiChildIdentitiesTests(TestCase):
    """Distinct child identities per within-Masi computed programme, per school/year."""

    def setUp(self):
        from api.models import School

        self.school = School.objects.create(
            name="P", school_uid="SCH-09200", type="Primary School"
        )
        self._next_sa = 90000

    def _lit(self, **kw):
        from api.models import LiteracySession2026

        self._next_sa += 1
        defaults = dict(source_airtable_id=f"litsa-{self._next_sa}", school_uid="SCH-09200")
        defaults.update(kw)
        return LiteracySession2026.objects.create(**defaults)

    def _num(self, **kw):
        from api.models import NumeracySession2026

        self._next_sa += 1
        defaults = dict(source_airtable_id=f"numsa-{self._next_sa}", school_uid="SCH-09200")
        defaults.update(kw)
        return NumeracySession2026.objects.create(**defaults)

    def test_literacy_identities_union_both_child_slots(self):
        from api.school_programme import masi_child_identities

        self._lit(session_date="2026-02-01", child_uid_1="CH-1", child_uid_2="CH-2")
        self._lit(session_date="2026-03-01", child_uid_1="CH-1", child_uid_2="CH-3")
        ids = masi_child_identities("SCH-09200", 2026)
        self.assertEqual(ids["masi_literacy"], {"CH-1", "CH-2", "CH-3"})

    def test_numeracy_identities_from_json_array(self):
        from api.school_programme import masi_child_identities

        self._num(session_date="2026-02-01", child_uids=["CH-5", "CH-6"])
        self._num(session_date="2026-03-01", child_uids=["CH-6", "CH-7"])
        ids = masi_child_identities("SCH-09200", 2026)
        self.assertEqual(ids["numeracy"], {"CH-5", "CH-6", "CH-7"})

    def test_filters_by_year(self):
        from api.school_programme import masi_child_identities

        self._lit(session_date="2025-02-01", child_uid_1="CH-OLD")
        self._lit(session_date="2026-02-01", child_uid_1="CH-NEW")
        ids = masi_child_identities("SCH-09200", 2026)
        self.assertEqual(ids["masi_literacy"], {"CH-NEW"})

    def test_filters_by_school(self):
        from api.school_programme import masi_child_identities

        self._num(source_airtable_id="other-1", school_uid="SCH-OTHER",
                  session_date="2026-02-01", child_uids=["CH-X"])
        ids = masi_child_identities("SCH-09200", 2026)
        self.assertEqual(ids["numeracy"], set())


class ComputePctFemaleTests(TestCase):
    """pct_female from CanonicalChild.gender. Prod uses 'F' / 'M', mostly blank."""

    def setUp(self):
        self._n = 0

    def _child(self, child_uid, gender):
        from api.models import CanonicalChild

        self._n += 1
        return CanonicalChild.objects.create(
            source_airtable_id=f"cc-{self._n}",
            child_uid=child_uid,
            mcode=900000 + self._n,
            gender=gender,
        )

    def test_pct_female_over_gendered_children(self):
        from api.school_programme import compute_pct_female

        self._child("CH-1", "F")
        self._child("CH-2", "F")
        self._child("CH-3", "F")
        self._child("CH-4", "M")
        result = compute_pct_female({"CH-1", "CH-2", "CH-3", "CH-4"})
        self.assertEqual(result, 75.0)

    def test_blank_and_unknown_excluded_from_denominator(self):
        from api.school_programme import compute_pct_female

        self._child("CH-1", "F")
        self._child("CH-2", "M")
        self._child("CH-3", "")
        self._child("CH-4", None)
        result = compute_pct_female({"CH-1", "CH-2", "CH-3", "CH-4"})
        self.assertEqual(result, 50.0)

    def test_none_when_no_gendered_children(self):
        from api.school_programme import compute_pct_female

        self._child("CH-1", "")
        self._child("CH-2", None)
        self.assertIsNone(compute_pct_female({"CH-1", "CH-2"}))

    def test_only_counts_children_in_the_set(self):
        from api.school_programme import compute_pct_female

        self._child("CH-1", "F")
        self._child("CH-OUTSIDE", "M")  # not in the requested set
        result = compute_pct_female({"CH-1"})
        self.assertEqual(result, 100.0)

    def test_empty_set_returns_none(self):
        from api.school_programme import compute_pct_female

        self.assertIsNone(compute_pct_female(set()))


class ProgrammesFromSiteTypeTests(SimpleTestCase):
    """site_type is a comma-joined programme-membership list -- a non-authoritative
    cross-check (plan section 6). Parse known tokens; flag unknown ones.
    """

    def test_parses_multi_programme_list(self):
        from api.school_programme import programmes_from_site_type

        result = programmes_from_site_type("Literacy, Zazi Izandi, 1000 Stories")
        self.assertEqual(
            result["programmes"], {"masi_literacy", "zazi_izandi", "thousand_stories"}
        )
        self.assertEqual(result["unknown_tokens"], set())

    def test_yearbeyond_maps_to_yebo(self):
        from api.school_programme import programmes_from_site_type

        result = programmes_from_site_type("Zazi Izandi, YearBeyond")
        self.assertEqual(result["programmes"], {"zazi_izandi", "yebo"})

    def test_edutech_token(self):
        from api.school_programme import programmes_from_site_type

        result = programmes_from_site_type("Literacy, 1000 Stories, EduTech")
        self.assertEqual(
            result["programmes"], {"masi_literacy", "thousand_stories", "edutech"}
        )

    def test_noise_tokens_ignored_not_flagged(self):
        from api.school_programme import programmes_from_site_type

        result = programmes_from_site_type("Top Learners High School")
        self.assertEqual(result["programmes"], set())
        self.assertEqual(result["unknown_tokens"], set())

    def test_plural_site_type_leakage_is_noise(self):
        # Real prod data leaks 'ECDCs' / 'Primary Schools' (plurals) into site_type;
        # these are site-type noise, not unknown programmes (found via smoke test).
        from api.school_programme import programmes_from_site_type

        result = programmes_from_site_type("ECDCs, Primary Schools")
        self.assertEqual(result["programmes"], set())
        self.assertEqual(result["unknown_tokens"], set())

    def test_blank_and_none(self):
        from api.school_programme import programmes_from_site_type

        self.assertEqual(programmes_from_site_type("")["programmes"], set())
        self.assertEqual(programmes_from_site_type(None)["programmes"], set())

    def test_unknown_token_flagged(self):
        from api.school_programme import programmes_from_site_type

        result = programmes_from_site_type("Literacy, Quidditch")
        self.assertEqual(result["programmes"], {"masi_literacy"})
        self.assertEqual(result["unknown_tokens"], {"Quidditch"})


class ProgrammeConfigTests(SimpleTestCase):
    """count_source / count_basis policy (Jim, 2026-06-18). Computed = Literacy +
    Numeracy. Whole-school = EduTech, Preschool, and 1000 Stories at an ECD.
    """

    def test_computed_programmes(self):
        from api.school_programme import count_source_for

        self.assertEqual(count_source_for("masi_literacy"), "computed")
        self.assertEqual(count_source_for("numeracy"), "computed")

    def test_manual_programmes(self):
        from api.school_programme import count_source_for

        for programme in ("zazi_izandi", "edutech", "yebo", "sport_arts",
                          "homework", "preschool", "thousand_stories"):
            self.assertEqual(count_source_for(programme), "manual", programme)

    def test_thousand_stories_basis_varies_by_site_type(self):
        from api.school_programme import count_basis_for

        self.assertEqual(count_basis_for("thousand_stories", "ECD"), "whole_school")
        self.assertEqual(
            count_basis_for("thousand_stories", "Primary"), "percent_of_school"
        )

    def test_fixed_whole_school_programmes(self):
        from api.school_programme import count_basis_for

        self.assertEqual(count_basis_for("edutech", "Primary"), "whole_school")
        self.assertEqual(count_basis_for("preschool", "ECD"), "whole_school")

    def test_child_level_programmes(self):
        from api.school_programme import count_basis_for

        for programme in ("masi_literacy", "numeracy", "yebo", "sport_arts", "homework"):
            self.assertEqual(
                count_basis_for(programme, "Primary"), "child_level", programme
            )

    def test_is_whole_school(self):
        from api.school_programme import is_whole_school

        self.assertTrue(is_whole_school("edutech", "Primary"))
        self.assertTrue(is_whole_school("preschool", "ECD"))
        self.assertTrue(is_whole_school("thousand_stories", "ECD"))
        self.assertFalse(is_whole_school("thousand_stories", "Primary"))
        self.assertFalse(is_whole_school("masi_literacy", "Primary"))
        self.assertFalse(is_whole_school("yebo", "Primary"))


class RefreshGridTests(TestCase):
    """The nightly orchestrator: composes the computation functions, writes
    system-owned columns ONLY, and surfaces integrity checks (plan section 8)."""

    YEAR = 2026

    def setUp(self):
        from api.models import School

        self.primary = School.objects.create(
            name="Refresh Primary", school_uid="SCH-09300",
            type="Primary School", site_type="Literacy, EduTech", is_active=True,
        )
        self._eid = 95000
        self._sa = 95000

    def _youth(self, **kw):
        from api.models import Youth

        self._eid += 1
        defaults = dict(employee_id=self._eid, first_names="Y", last_name="C",
                        employment_status="Active")
        defaults.update(kw)
        return Youth.objects.create(**defaults)

    def _lit(self, child_uid_1=None, child_uid_2=None, date="2026-02-01"):
        from api.models import LiteracySession2026

        self._sa += 1
        return LiteracySession2026.objects.create(
            source_airtable_id=f"r-lit-{self._sa}", school_uid="SCH-09300",
            session_date=date, child_uid_1=child_uid_1, child_uid_2=child_uid_2,
        )

    def _child(self, child_uid, gender=""):
        from api.models import CanonicalChild

        self._sa += 1
        return CanonicalChild.objects.create(
            source_airtable_id=f"r-cc-{self._sa}", child_uid=child_uid,
            mcode=950000 + self._sa, gender=gender,
        )

    def test_creates_rows_with_system_columns(self):
        from api.models import SchoolProgrammeYear
        from api.school_programme import refresh_school_programme_grid

        self._youth(job_title="Literacy Coach", school=self.primary)
        self._child("CH-1", "F")
        self._child("CH-2", "M")
        self._lit(child_uid_1="CH-1", child_uid_2="CH-2")

        refresh_school_programme_grid(self.YEAR)

        lit = SchoolProgrammeYear.objects.get(
            school=self.primary, programme="masi_literacy", year=self.YEAR
        )
        self.assertEqual(lit.youth_active, 1)
        self.assertEqual(lit.children_count, 2)  # computed reach = distinct identities
        self.assertEqual(lit.count_source, "computed")
        self.assertEqual(lit.count_basis, "child_level")
        self.assertIsNotNone(lit.as_of)

    def test_manual_programme_children_count_not_computed(self):
        from api.models import SchoolProgrammeYear
        from api.school_programme import refresh_school_programme_grid

        refresh_school_programme_grid(self.YEAR)

        edutech = SchoolProgrammeYear.objects.get(
            school=self.primary, programme="edutech", year=self.YEAR
        )
        self.assertEqual(edutech.count_source, "manual")
        self.assertEqual(edutech.count_basis, "whole_school")
        self.assertIsNone(edutech.children_count)  # cron must not invent a manual count

    def test_does_not_overwrite_human_columns(self):
        from api.models import SchoolProgrammeYear, SchoolYearStats
        from api.school_programme import refresh_school_programme_grid

        # Human-entered values pre-exist.
        SchoolProgrammeYear.objects.create(
            school=self.primary, programme="edutech", year=self.YEAR,
            count_source="manual", count_basis="whole_school",
            children_count=99, youth_planned=5,
        )
        SchoolYearStats.objects.create(
            school=self.primary, year=self.YEAR, total_kids_in_school=200,
            pct_african=90, demographic_source="school estimate",
        )

        refresh_school_programme_grid(self.YEAR)

        edutech = SchoolProgrammeYear.objects.get(
            school=self.primary, programme="edutech", year=self.YEAR
        )
        self.assertEqual(edutech.children_count, 99)  # manual count untouched
        self.assertEqual(edutech.youth_planned, 5)  # human allocation untouched
        stats = SchoolYearStats.objects.get(school=self.primary, year=self.YEAR)
        self.assertEqual(stats.total_kids_in_school, 200)  # human enrolment untouched
        self.assertEqual(stats.pct_african, 90)  # human race estimate untouched
        self.assertEqual(stats.demographic_source, "school estimate")

    def test_computes_unique_and_pct_female(self):
        from api.models import SchoolYearStats
        from api.school_programme import refresh_school_programme_grid

        for uid, g in [("CH-1", "F"), ("CH-2", "M"), ("CH-3", "F")]:
            self._child(uid, g)
        self._lit(child_uid_1="CH-1", child_uid_2="CH-2")
        self._lit(child_uid_1="CH-2", child_uid_2="CH-3")  # CH-2 repeats

        refresh_school_programme_grid(self.YEAR)

        stats = SchoolYearStats.objects.get(school=self.primary, year=self.YEAR)
        # No total_kids set here, but EduTech (whole-school) is present in site_type;
        # without a total_kids figure the override falls back to the identity union.
        self.assertEqual(stats.unique_beneficiaries, 3)  # CH-1,2,3 deduped
        self.assertEqual(float(stats.pct_female), 66.67)  # 2F of 3 gendered

    def test_whole_school_override_uses_total_kids(self):
        from api.models import SchoolYearStats
        from api.school_programme import refresh_school_programme_grid

        SchoolYearStats.objects.create(
            school=self.primary, year=self.YEAR, total_kids_in_school=200
        )
        self._child("CH-1", "F")
        self._lit(child_uid_1="CH-1")  # only 1 identity, but EduTech is whole-school

        refresh_school_programme_grid(self.YEAR)

        stats = SchoolYearStats.objects.get(school=self.primary, year=self.YEAR)
        self.assertEqual(stats.unique_beneficiaries, 200)  # whole-school -> total kids

    def test_flags_unmatched_school_with_null_uid(self):
        from api.models import School
        from api.school_programme import refresh_school_programme_grid

        School.objects.create(
            name="No UID Primary", school_uid=None, type="Primary School",
            site_type="Literacy", is_active=True,
        )
        result = refresh_school_programme_grid(self.YEAR)
        self.assertIn("No UID Primary", result["integrity"]["unmatched_schools"])

    def test_flags_unmapped_title(self):
        from api.school_programme import refresh_school_programme_grid

        self._youth(job_title="Wizard", school=self.primary)
        result = refresh_school_programme_grid(self.YEAR)
        self.assertIn("Wizard", result["integrity"]["unmapped_titles"])

    def test_excludes_secondary_schools(self):
        from api.models import School, SchoolProgrammeYear
        from api.school_programme import refresh_school_programme_grid

        sec = School.objects.create(
            name="Top Learners HS", school_uid="SCH-09399",
            type="Secondary School", site_type="Top Learners High School",
            is_active=True,
        )
        refresh_school_programme_grid(self.YEAR)
        self.assertFalse(
            SchoolProgrammeYear.objects.filter(school=sec, year=self.YEAR).exists()
        )

    def test_idempotent_rerun(self):
        from api.models import SchoolProgrammeYear
        from api.school_programme import refresh_school_programme_grid

        self._youth(job_title="Literacy Coach", school=self.primary)
        self._lit(child_uid_1="CH-1")
        refresh_school_programme_grid(self.YEAR)
        count_after_first = SchoolProgrammeYear.objects.filter(
            school=self.primary, year=self.YEAR
        ).count()
        refresh_school_programme_grid(self.YEAR)
        count_after_second = SchoolProgrammeYear.objects.filter(
            school=self.primary, year=self.YEAR
        ).count()
        self.assertEqual(count_after_first, count_after_second)


class RefreshGridCommandTests(TestCase):
    """The nightly management command: AirtableSyncLog logging + fail-closed."""

    _FETCH = (
        "api.management.commands.refresh_school_programme_grid"
        ".fetch_school_programme_export"
    )
    _REFRESH = (
        "api.management.commands.refresh_school_programme_grid"
        ".refresh_school_programme_grid"
    )

    def test_logs_success(self):
        from unittest.mock import patch
        from django.core.management import call_command
        from api.models import AirtableSyncLog

        # Mock the Zazi fetch so the unit test never touches the network.
        with patch(self._FETCH, return_value={"schools": []}):
            call_command("refresh_school_programme_grid", "--year", "2026")
        log = AirtableSyncLog.objects.filter(
            sync_type="school_programme_grid"
        ).latest("started_at")
        self.assertTrue(log.success)
        self.assertIsNotNone(log.completed_at)

    def test_fails_closed_and_rolls_back_partial_writes(self):
        from unittest.mock import patch
        from django.core.management import call_command
        from api.models import AirtableSyncLog, School, SchoolProgrammeYear

        school = School.objects.create(
            name="X", school_uid="SCH-1", type="Primary School", is_active=True
        )

        def boom(year, zazi_export=None):
            # A partial write, then a failure mid-refresh (e.g. an input vanished).
            SchoolProgrammeYear.objects.create(
                school=school, programme="edutech", year=year
            )
            raise RuntimeError("required input missing")

        with patch(self._REFRESH, side_effect=boom), \
                patch(self._FETCH, return_value={"schools": []}):
            with self.assertRaises(RuntimeError):
                call_command("refresh_school_programme_grid", "--year", "2026")

        # Fail-closed: the partial row is rolled back -- nothing published.
        self.assertFalse(
            SchoolProgrammeYear.objects.filter(programme="edutech").exists()
        )
        # The failure is recorded, not swallowed.
        log = AirtableSyncLog.objects.filter(
            sync_type="school_programme_grid"
        ).latest("started_at")
        self.assertFalse(log.success)
        self.assertIn("required input missing", log.error_message)

    def test_fails_closed_when_zazi_unreachable(self):
        # Plan section 8.6: if Zazi is unreachable the refresh fails closed
        # (no partial publish) rather than silently undercounting.
        import requests
        from unittest.mock import patch
        from django.core.management import call_command
        from api.models import AirtableSyncLog, SchoolProgrammeYear

        with patch(self._FETCH, side_effect=requests.RequestException("zazi down")):
            with self.assertRaises(requests.RequestException):
                call_command("refresh_school_programme_grid", "--year", "2026")

        self.assertFalse(SchoolProgrammeYear.objects.exists())  # nothing written
        log = AirtableSyncLog.objects.filter(
            sync_type="school_programme_grid"
        ).latest("started_at")
        self.assertFalse(log.success)
        self.assertIn("zazi down", log.error_message)

    def test_skip_zazi_flag_skips_the_fetch(self):
        from unittest.mock import patch
        from django.core.management import call_command
        from api.models import AirtableSyncLog

        with patch(self._FETCH) as mfetch:
            call_command(
                "refresh_school_programme_grid", "--year", "2026", "--skip-zazi"
            )
            mfetch.assert_not_called()
        log = AirtableSyncLog.objects.filter(
            sync_type="school_programme_grid"
        ).latest("started_at")
        self.assertTrue(log.success)


class RollupToPublishedStatsTests(TestCase):
    """Increment 1 rolls up to NEW, unpublished keys (Jim, 2026-06-18) so the live
    donor hero_* stats are never regressed by within-Masi-only partial numbers."""

    YEAR = 2026

    def _school(self, name, uid, type_):
        from api.models import School

        return School.objects.create(
            name=name, school_uid=uid, type=type_, is_active=True
        )

    def _stats(self, school, unique):
        from api.models import SchoolYearStats

        return SchoolYearStats.objects.create(
            school=school, year=self.YEAR, unique_beneficiaries=unique
        )

    def test_children_rollup_sums_unique_beneficiaries(self):
        from api.school_programme import rollup_to_published_stats

        self._stats(self._school("A", "SCH-A", "Primary School"), 100)
        self._stats(self._school("B", "SCH-B", "ECDC"), 40)
        result = rollup_to_published_stats(self.YEAR)
        self.assertEqual(result["children"], 140)

    def test_active_schools_split_by_type(self):
        from api.school_programme import rollup_to_published_stats

        self._stats(self._school("A", "SCH-A", "Primary School"), 100)
        self._stats(self._school("B", "SCH-B", "Primary School"), 50)
        self._stats(self._school("C", "SCH-C", "ECDC"), 40)
        self._stats(self._school("D", "SCH-D", "ECDC"), 0)  # no beneficiaries -> inactive
        result = rollup_to_published_stats(self.YEAR)
        self.assertEqual(result["schools_primary"], 2)
        self.assertEqual(result["schools_ecd"], 1)
        self.assertEqual(result["sites_total"], 3)

    def test_writes_unpublished_stats(self):
        from api.models import PublishedStat
        from api.school_programme import rollup_to_published_stats

        self._stats(self._school("A", "SCH-A", "Primary School"), 100)
        rollup_to_published_stats(self.YEAR)
        stat = PublishedStat.objects.get(key="grid_children")
        self.assertEqual(stat.numeric_value, 100)
        self.assertFalse(stat.is_published)  # internal, not donor-facing
        self.assertIn("zazi-inclusive", stat.methodology_note.lower())

    def test_does_not_touch_live_hero_keys(self):
        from api.models import PublishedStat
        from api.school_programme import rollup_to_published_stats

        PublishedStat.objects.create(
            key="hero_children", value="19,444", numeric_value=19444,
            label="children on programme", source_system="impact",
            as_of="2026-01-01", is_published=True,
        )
        self._stats(self._school("A", "SCH-A", "Primary School"), 100)
        rollup_to_published_stats(self.YEAR)
        hero = PublishedStat.objects.get(key="hero_children")
        self.assertEqual(hero.numeric_value, 19444)  # untouched
        self.assertTrue(hero.is_published)

    def test_idempotent_upsert(self):
        from api.models import PublishedStat
        from api.school_programme import rollup_to_published_stats

        self._stats(self._school("A", "SCH-A", "Primary School"), 100)
        rollup_to_published_stats(self.YEAR)
        rollup_to_published_stats(self.YEAR)
        self.assertEqual(
            PublishedStat.objects.filter(key="grid_children").count(), 1
        )


class GridServiceTests(TestCase):
    """build_grid (read) + apply_*_edit (writes) + rollover_grid."""

    YEAR = 2026

    def setUp(self):
        from api.models import School, SchoolProgrammeYear, SchoolYearStats

        self.school = School.objects.create(
            name="Svc Primary", school_uid="SCH-09400",
            type="Primary School", is_active=True,
        )
        self.lit = SchoolProgrammeYear.objects.create(
            school=self.school, programme="masi_literacy", year=self.YEAR,
            count_source="computed", count_basis="child_level",
            children_count=20, youth_active=2,
        )
        self.edutech = SchoolProgrammeYear.objects.create(
            school=self.school, programme="edutech", year=self.YEAR,
            count_source="manual", count_basis="whole_school",
        )
        self.stats = SchoolYearStats.objects.create(
            school=self.school, year=self.YEAR, unique_beneficiaries=20,
        )

    def _sa(self, n):
        return f"svc-{n}"

    def test_build_grid_structure(self):
        from api.school_programme import build_grid

        grid = build_grid(self.YEAR)
        self.assertEqual(grid["year"], self.YEAR)
        self.assertEqual(len(grid["schools"]), 1)
        row = grid["schools"][0]
        self.assertEqual(row["name"], "Svc Primary")
        self.assertEqual(row["site_type"], "Primary")
        self.assertEqual(row["cells"]["masi_literacy"]["children_count"], 20)
        self.assertFalse(row["cells"]["masi_literacy"]["editable"])  # computed
        self.assertTrue(row["cells"]["edutech"]["editable"])  # manual
        self.assertEqual(row["stats"]["unique_beneficiaries"], 20)

    def test_apply_cell_edit_manual_children_count(self):
        from api.models import SchoolProgrammeYear
        from api.school_programme import apply_cell_edit

        user = _make_user("pm", "PROJECT MANAGER")
        apply_cell_edit(self.edutech.id, {"children_count": 150}, user)
        self.edutech.refresh_from_db()
        self.assertEqual(self.edutech.children_count, 150)
        self.assertEqual(self.edutech.updated_by, user)
        # System fields untouched.
        self.assertEqual(self.edutech.count_source, "manual")

    def test_apply_cell_edit_rejects_computed_children_count(self):
        from api.school_programme import apply_cell_edit

        user = _make_user("pm", "PROJECT MANAGER")
        with self.assertRaises(ValueError):
            apply_cell_edit(self.lit.id, {"children_count": 999}, user)
        self.lit.refresh_from_db()
        self.assertEqual(self.lit.children_count, 20)  # unchanged

    def test_apply_cell_edit_youth_planned(self):
        from api.school_programme import apply_cell_edit

        user = _make_user("pm", "PROJECT MANAGER")
        apply_cell_edit(self.lit.id, {"youth_planned": 3}, user)
        self.lit.refresh_from_db()
        self.assertEqual(self.lit.youth_planned, 3)
        self.assertEqual(self.lit.youth_active, 2)  # system field untouched

    def test_editing_total_kids_recomputes_unique_immediately(self):
        # Plan section 12: a human edit to total_kids recomputes the dependent
        # rollup in the same call, not at the next cron.
        from api.models import LiteracySession2026, SchoolYearStats
        from api.school_programme import apply_stats_edit

        for i, uid in enumerate(["CH-1", "CH-2", "CH-3"]):
            LiteracySession2026.objects.create(
                source_airtable_id=self._sa(i), school_uid="SCH-09400",
                session_date="2026-02-01", child_uid_1=uid,
            )
        user = _make_user("pm", "PROJECT MANAGER")
        # Cap below the identity union (3) -> unique recomputes to total_kids (2).
        apply_stats_edit(self.stats.id, {"total_kids_in_school": 2}, user)
        self.stats.refresh_from_db()
        self.assertEqual(self.stats.total_kids_in_school, 2)
        self.assertEqual(self.stats.unique_beneficiaries, 2)

    def test_rollover_copies_structure_blank_counts(self):
        from api.models import SchoolProgrammeYear
        from api.school_programme import rollover_grid

        rollover_grid(self.YEAR, self.YEAR + 1)
        new_lit = SchoolProgrammeYear.objects.get(
            school=self.school, programme="masi_literacy", year=self.YEAR + 1
        )
        self.assertEqual(new_lit.count_source, "computed")  # structure carried
        self.assertEqual(new_lit.count_basis, "child_level")
        self.assertIsNone(new_lit.children_count)  # counts reset blank
        self.assertEqual(new_lit.youth_active, 0)

    def test_rollover_idempotent(self):
        from api.models import SchoolProgrammeYear
        from api.school_programme import rollover_grid

        rollover_grid(self.YEAR, self.YEAR + 1)
        rollover_grid(self.YEAR, self.YEAR + 1)
        self.assertEqual(
            SchoolProgrammeYear.objects.filter(
                school=self.school, year=self.YEAR + 1
            ).count(),
            2,
        )


class ResolveZaziExportTests(TestCase):
    """Increment 2: resolve a Zazi per-school export into Masi identities."""

    def setUp(self):
        self._n = 0

    def _canon(self, child_uid, participant_id):
        from api.models import CanonicalChild

        self._n += 1
        return CanonicalChild.objects.create(
            source_airtable_id=f"z-{self._n}", child_uid=child_uid,
            mcode=970000 + self._n, participant_id=str(participant_id),
        )

    def test_resolves_participant_ids_and_counts_unresolved(self):
        from api.school_programme import resolve_zazi_export

        self._canon("CH-1", 5001)
        self._canon("CH-2", 5002)
        export = {"schools": [{
            "program_name": "X", "school_uid": "SCH-1", "child_count": 3,
            "children": [{"participant_id": 5001}, {"participant_id": 5002},
                         {"participant_id": 9999}],
        }]}
        result = resolve_zazi_export(export)
        entry = result["by_uid"]["SCH-1"]
        self.assertEqual(entry["reach"], 3)  # full reach, incl unresolved
        self.assertEqual(entry["child_uids"], {"CH-1", "CH-2"})
        self.assertEqual(entry["unresolved"], 1)  # 9999 not in canonical

    def test_unmapped_schools_listed(self):
        from api.school_programme import resolve_zazi_export

        export = {"schools": [{
            "program_name": "Unmapped", "school_uid": None, "child_count": 5,
            "children": [{"participant_id": 1}],
        }]}
        result = resolve_zazi_export(export)
        self.assertIn("Unmapped", result["unmapped_schools"])
        self.assertEqual(result["by_uid"], {})


class FetchSchoolProgrammeExportTests(SimpleTestCase):
    """Increment 2: the zazi_client call to the ZZ export endpoint."""

    def test_calls_endpoint_with_auth_and_year(self):
        from unittest.mock import patch, MagicMock
        from api import zazi_client

        with patch.dict("os.environ", {"ZAZI_API_BASE_URL": "http://zz.test",
                                       "ZAZI_INTERNAL_API_SECRET": "sek"}):
            with patch("api.zazi_client.requests.get") as mget:
                resp = MagicMock()
                resp.json.return_value = {"schools": []}
                mget.return_value = resp
                result = zazi_client.fetch_school_programme_export(2026)
        args, kwargs = mget.call_args
        self.assertIn("/api/school-programme-export/", args[0])
        self.assertEqual(kwargs["params"], {"year": 2026})
        self.assertEqual(kwargs["headers"]["X-Internal-Auth"], "sek")
        self.assertEqual(result, {"schools": []})


class RefreshGridZaziTests(TestCase):
    """Increment 2: the cron folds Zazi reach + identities into the grid."""

    YEAR = 2026

    def setUp(self):
        from api.models import School

        self.school = School.objects.create(
            name="Z Primary", school_uid="SCH-09600",
            type="Primary School", is_active=True,
        )
        self._n = 0

    def _canon(self, child_uid, participant_id):
        from api.models import CanonicalChild

        self._n += 1
        return CanonicalChild.objects.create(
            source_airtable_id=f"zc-{self._n}", child_uid=child_uid,
            mcode=980000 + self._n, participant_id=str(participant_id),
        )

    def test_zazi_reach_and_identities_folded(self):
        from api.models import SchoolProgrammeYear, SchoolYearStats
        from api.school_programme import refresh_school_programme_grid

        self._canon("CH-Z1", 7001)
        self._canon("CH-Z2", 7002)
        export = {"schools": [{
            "program_name": "Z Primary", "school_uid": "SCH-09600", "child_count": 3,
            "children": [{"participant_id": 7001}, {"participant_id": 7002},
                         {"participant_id": 7003}],  # 7003 unresolved
        }]}
        refresh_school_programme_grid(self.YEAR, zazi_export=export)
        zrow = SchoolProgrammeYear.objects.get(
            school=self.school, programme="zazi_izandi", year=self.YEAR
        )
        self.assertEqual(zrow.children_count, 3)  # reach = full child_count
        self.assertEqual(zrow.count_source, "computed")
        stats = SchoolYearStats.objects.get(school=self.school, year=self.YEAR)
        self.assertEqual(stats.unique_beneficiaries, 2)  # only resolved CH-Z1/Z2

    def test_zazi_dedups_against_masi(self):
        from api.models import LiteracySession2026, SchoolYearStats
        from api.school_programme import refresh_school_programme_grid

        self._canon("CH-SHARED", 7001)
        self._canon("CH-ZONLY", 7002)
        LiteracySession2026.objects.create(
            source_airtable_id="zl-1", school_uid="SCH-09600",
            session_date="2026-02-01", child_uid_1="CH-SHARED", child_uid_2="CH-MASI",
        )
        export = {"schools": [{
            "program_name": "Z", "school_uid": "SCH-09600", "child_count": 2,
            "children": [{"participant_id": 7001}, {"participant_id": 7002}],
        }]}
        refresh_school_programme_grid(self.YEAR, zazi_export=export)
        stats = SchoolYearStats.objects.get(school=self.school, year=self.YEAR)
        # literacy {CH-SHARED, CH-MASI} U zazi {CH-SHARED, CH-ZONLY} = 3 (SHARED once)
        self.assertEqual(stats.unique_beneficiaries, 3)

    def test_unresolved_and_unmapped_flagged(self):
        from api.school_programme import refresh_school_programme_grid

        export = {"schools": [
            {"program_name": "Z", "school_uid": "SCH-09600", "child_count": 1,
             "children": [{"participant_id": 9999}]},
            {"program_name": "Unmapped ECD", "school_uid": None, "child_count": 4,
             "children": []},
        ]}
        result = refresh_school_programme_grid(self.YEAR, zazi_export=export)
        self.assertEqual(result["integrity"]["unresolved_zazi_participants"], 1)
        self.assertIn("Unmapped ECD", result["integrity"]["unmapped_zazi_schools"])

    def test_no_zazi_export_leaves_zazi_staffing_only(self):
        # Without an export, zazi children are NOT computed (Increment-1 behaviour).
        from api.models import SchoolProgrammeYear
        from api.school_programme import refresh_school_programme_grid

        self.school.site_type = "Zazi Izandi"
        self.school.save()
        refresh_school_programme_grid(self.YEAR)  # no zazi_export
        zrow = SchoolProgrammeYear.objects.filter(
            school=self.school, programme="zazi_izandi", year=self.YEAR
        ).first()
        if zrow:  # row may exist from site_type seed
            self.assertIsNone(zrow.children_count)
            self.assertEqual(zrow.count_source, "manual")


class GridEndpointAuthzTests(TestCase):
    """Reads = any authenticated user; writes = ADMIN / PROJECT MANAGER only
    (plan section 3 / 12). These cells become official grant numbers."""

    def setUp(self):
        from rest_framework.test import APIClient
        from api.models import School, SchoolProgrammeYear

        self.school = School.objects.create(
            name="E Primary", school_uid="SCH-09500",
            type="Primary School", is_active=True,
        )
        self.cell = SchoolProgrammeYear.objects.create(
            school=self.school, programme="edutech", year=2026,
            count_source="manual", count_basis="whole_school",
        )
        self.client = APIClient()

    def _auth(self, role):
        user = _make_user(f"u_{role.replace(' ', '_').lower()}", role)
        self.client.force_authenticate(user=user)
        return user

    def test_authenticated_non_admin_can_read(self):
        self._auth("MENTOR")
        resp = self.client.get("/api/school-programme-grid/?year=2026")
        self.assertEqual(resp.status_code, 200)

    def test_non_admin_cannot_edit_cell(self):
        self._auth("MENTOR")
        resp = self.client.patch(
            f"/api/school-programme-grid/cell/{self.cell.id}/",
            {"children_count": 50}, format="json",
        )
        self.assertEqual(resp.status_code, 403)
        self.cell.refresh_from_db()
        self.assertIsNone(self.cell.children_count)  # write blocked

    def test_non_admin_cannot_rollover(self):
        self._auth("MENTOR")
        resp = self.client.post(
            "/api/school-programme-grid/rollover/",
            {"from_year": 2026, "to_year": 2027}, format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_admin_can_edit_cell(self):
        self._auth("ADMIN")
        resp = self.client.patch(
            f"/api/school-programme-grid/cell/{self.cell.id}/",
            {"children_count": 50}, format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.cell.refresh_from_db()
        self.assertEqual(self.cell.children_count, 50)

    def test_editing_computed_cell_rejected(self):
        from api.models import SchoolProgrammeYear

        computed = SchoolProgrammeYear.objects.create(
            school=self.school, programme="masi_literacy", year=2026,
            count_source="computed", count_basis="child_level", children_count=10,
        )
        self._auth("ADMIN")
        resp = self.client.patch(
            f"/api/school-programme-grid/cell/{computed.id}/",
            {"children_count": 999}, format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_unauthenticated_rejected(self):
        resp = self.client.get("/api/school-programme-grid/?year=2026")
        self.assertIn(resp.status_code, (401, 403))


class CreateCellTests(TestCase):
    """create_cell: management declares a programme at a school on demand. Seeds
    the system-owned config (count_source/count_basis) the same way the cron does,
    leaves human-owned counts blank, and is idempotent (double-click is harmless).
    """

    YEAR = 2026

    def setUp(self):
        from api.models import School

        self.primary = School.objects.create(
            name="Add Primary", school_uid="SCH-09700",
            type="Primary School", is_active=True,
        )
        self.ecd = School.objects.create(
            name="Add ECD", school_uid="SCH-09701", type="ECDC", is_active=True,
        )

    def test_creates_row_with_manual_config_and_blank_counts(self):
        from api.school_programme import create_cell

        user = _make_user("pm", "PROJECT MANAGER")
        row = create_cell("SCH-09700", "edutech", self.YEAR, user)
        self.assertEqual(row.school, self.primary)
        self.assertEqual(row.programme, "edutech")
        self.assertEqual(row.year, self.YEAR)
        # Manual programme: count_source manual, EduTech is whole-school.
        self.assertEqual(row.count_source, "manual")
        self.assertEqual(row.count_basis, "whole_school")
        # children_count is NOT invented on create; humans / cron fill it later.
        self.assertIsNone(row.children_count)
        self.assertIsNone(row.youth_planned)
        self.assertIsNone(row.percent_of_school)
        self.assertEqual(row.youth_active, 0)
        self.assertEqual(row.updated_by, user)

    def test_creates_computed_programme_config(self):
        # A computed programme (Literacy) still seeds count_source=computed, but the
        # count itself stays NULL until the cron computes the distinct-identity reach.
        from api.school_programme import create_cell

        user = _make_user("pm", "PROJECT MANAGER")
        row = create_cell("SCH-09700", "masi_literacy", self.YEAR, user)
        self.assertEqual(row.count_source, "computed")
        self.assertEqual(row.count_basis, "child_level")
        self.assertIsNone(row.children_count)

    def test_count_basis_reflects_site_type(self):
        # 1000 Stories is whole-school at an ECD but percent-of-school at a primary.
        from api.school_programme import create_cell

        user = _make_user("pm", "PROJECT MANAGER")
        prim = create_cell("SCH-09700", "thousand_stories", self.YEAR, user)
        self.assertEqual(prim.count_basis, "percent_of_school")
        ecd = create_cell("SCH-09701", "thousand_stories", self.YEAR, user)
        self.assertEqual(ecd.count_basis, "whole_school")

    def test_idempotent_returns_existing_row_unchanged(self):
        from api.models import SchoolProgrammeYear
        from api.school_programme import create_cell

        user = _make_user("pm", "PROJECT MANAGER")
        first = create_cell("SCH-09700", "edutech", self.YEAR, user)
        # Pretend a human typed a count between clicks; the 2nd add must not stomp it.
        first.children_count = 42
        first.save(update_fields=["children_count"])

        second = create_cell("SCH-09700", "edutech", self.YEAR, user)
        self.assertEqual(second.pk, first.pk)
        self.assertEqual(second.children_count, 42)  # unchanged
        self.assertEqual(
            SchoolProgrammeYear.objects.filter(
                school=self.primary, programme="edutech", year=self.YEAR
            ).count(),
            1,  # no duplicate
        )

    def test_rejects_unknown_programme(self):
        from api.school_programme import create_cell

        user = _make_user("pm", "PROJECT MANAGER")
        with self.assertRaises(ValueError):
            create_cell("SCH-09700", "quidditch", self.YEAR, user)

    def test_rejects_missing_school(self):
        from api.school_programme import create_cell

        user = _make_user("pm", "PROJECT MANAGER")
        with self.assertRaises(ValueError):
            create_cell("SCH-DOES-NOT-EXIST", "edutech", self.YEAR, user)


class DeleteCellTests(TestCase):
    """delete_cell: undo an accidental add. Only a TRULY-empty row may be removed,
    so a real (data-bearing) cell can never be destroyed by an errant delete.
    """

    YEAR = 2026

    def setUp(self):
        from api.models import School

        self.school = School.objects.create(
            name="Del Primary", school_uid="SCH-09800",
            type="Primary School", is_active=True,
        )

    def _cell(self, **kw):
        from api.models import SchoolProgrammeYear

        defaults = dict(
            school=self.school, programme="edutech", year=self.YEAR,
            count_source="manual", count_basis="whole_school",
        )
        defaults.update(kw)
        return SchoolProgrammeYear.objects.create(**defaults)

    def test_deletes_truly_empty_row(self):
        from api.models import SchoolProgrammeYear
        from api.school_programme import delete_cell

        user = _make_user("pm", "PROJECT MANAGER")
        cell = self._cell()
        self.assertIsNone(delete_cell(cell.id, user))
        self.assertFalse(
            SchoolProgrammeYear.objects.filter(pk=cell.id).exists()
        )

    def test_refuses_when_children_count_set(self):
        from api.models import SchoolProgrammeYear
        from api.school_programme import delete_cell

        user = _make_user("pm", "PROJECT MANAGER")
        cell = self._cell(children_count=0)  # even 0 is "has data" -> not empty
        with self.assertRaises(ValueError):
            delete_cell(cell.id, user)
        self.assertTrue(SchoolProgrammeYear.objects.filter(pk=cell.id).exists())

    def test_refuses_when_youth_planned_set(self):
        from api.models import SchoolProgrammeYear
        from api.school_programme import delete_cell

        user = _make_user("pm", "PROJECT MANAGER")
        cell = self._cell(youth_planned=3)
        with self.assertRaises(ValueError):
            delete_cell(cell.id, user)
        self.assertTrue(SchoolProgrammeYear.objects.filter(pk=cell.id).exists())

    def test_refuses_when_youth_active_positive(self):
        from api.models import SchoolProgrammeYear
        from api.school_programme import delete_cell

        user = _make_user("pm", "PROJECT MANAGER")
        cell = self._cell(youth_active=1)
        with self.assertRaises(ValueError):
            delete_cell(cell.id, user)
        self.assertTrue(SchoolProgrammeYear.objects.filter(pk=cell.id).exists())


class CreateDeleteEndpointTests(TestCase):
    """The HTTP contract: POST collection to add, DELETE detail to remove. Writes
    are ADMIN / PROJECT MANAGER only; the create response matches the grid-read
    cell shape so the frontend can drop it straight into the board.
    """

    YEAR = 2026

    def setUp(self):
        from rest_framework.test import APIClient
        from api.models import School

        self.school = School.objects.create(
            name="Ep Primary", school_uid="SCH-09900",
            type="Primary School", is_active=True,
        )
        self.client = APIClient()

    def _auth(self, role):
        user = _make_user(f"u_{role.replace(' ', '_').lower()}", role)
        self.client.force_authenticate(user=user)
        return user

    def test_admin_can_create_cell_returns_grid_shape(self):
        from api.models import SchoolProgrammeYear

        self._auth("ADMIN")
        resp = self.client.post(
            "/api/school-programme-grid/cell/",
            {"school_uid": "SCH-09900", "programme": "edutech", "year": self.YEAR},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        body = resp.json()
        # Same cell shape the grid read returns.
        self.assertEqual(
            set(body.keys()),
            {"id", "children_count", "count_source", "count_basis",
             "percent_of_school", "youth_planned", "youth_active",
             "as_of", "updated_at", "editable"},
        )
        self.assertEqual(body["count_source"], "manual")
        self.assertEqual(body["count_basis"], "whole_school")
        self.assertIsNone(body["children_count"])
        self.assertEqual(body["youth_active"], 0)
        self.assertTrue(body["editable"])  # manual cell is human-editable
        self.assertTrue(
            SchoolProgrammeYear.objects.filter(
                school=self.school, programme="edutech", year=self.YEAR
            ).exists()
        )

    def test_create_unknown_programme_is_400(self):
        self._auth("ADMIN")
        resp = self.client.post(
            "/api/school-programme-grid/cell/",
            {"school_uid": "SCH-09900", "programme": "quidditch", "year": self.YEAR},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("detail", resp.json())

    def test_create_missing_school_is_400(self):
        self._auth("ADMIN")
        resp = self.client.post(
            "/api/school-programme-grid/cell/",
            {"school_uid": "SCH-NOPE", "programme": "edutech", "year": self.YEAR},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("detail", resp.json())

    def test_non_admin_cannot_create(self):
        from api.models import SchoolProgrammeYear

        self._auth("MENTOR")
        resp = self.client.post(
            "/api/school-programme-grid/cell/",
            {"school_uid": "SCH-09900", "programme": "edutech", "year": self.YEAR},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)
        self.assertFalse(
            SchoolProgrammeYear.objects.filter(
                school=self.school, programme="edutech"
            ).exists()
        )

    def test_admin_can_delete_empty_cell(self):
        from api.models import SchoolProgrammeYear

        cell = SchoolProgrammeYear.objects.create(
            school=self.school, programme="edutech", year=self.YEAR,
            count_source="manual", count_basis="whole_school",
        )
        self._auth("ADMIN")
        resp = self.client.delete(f"/api/school-programme-grid/cell/{cell.id}/")
        self.assertEqual(resp.status_code, 204)
        self.assertFalse(SchoolProgrammeYear.objects.filter(pk=cell.id).exists())

    def test_delete_cell_with_data_is_400(self):
        from api.models import SchoolProgrammeYear

        cell = SchoolProgrammeYear.objects.create(
            school=self.school, programme="edutech", year=self.YEAR,
            count_source="manual", count_basis="whole_school", children_count=12,
        )
        self._auth("ADMIN")
        resp = self.client.delete(f"/api/school-programme-grid/cell/{cell.id}/")
        self.assertEqual(resp.status_code, 400)
        self.assertTrue(SchoolProgrammeYear.objects.filter(pk=cell.id).exists())

    def test_delete_missing_cell_is_404(self):
        self._auth("ADMIN")
        resp = self.client.delete("/api/school-programme-grid/cell/99999999/")
        self.assertEqual(resp.status_code, 404)

    def test_non_admin_cannot_delete(self):
        from api.models import SchoolProgrammeYear

        cell = SchoolProgrammeYear.objects.create(
            school=self.school, programme="edutech", year=self.YEAR,
            count_source="manual", count_basis="whole_school",
        )
        self._auth("MENTOR")
        resp = self.client.delete(f"/api/school-programme-grid/cell/{cell.id}/")
        self.assertEqual(resp.status_code, 403)
        self.assertTrue(SchoolProgrammeYear.objects.filter(pk=cell.id).exists())

    def test_patch_still_works_on_detail_route(self):
        # Adding DELETE to the detail route must not break the existing PATCH edit.
        from api.models import SchoolProgrammeYear

        cell = SchoolProgrammeYear.objects.create(
            school=self.school, programme="edutech", year=self.YEAR,
            count_source="manual", count_basis="whole_school",
        )
        self._auth("ADMIN")
        resp = self.client.patch(
            f"/api/school-programme-grid/cell/{cell.id}/",
            {"children_count": 77}, format="json",
        )
        self.assertEqual(resp.status_code, 200)
        cell.refresh_from_db()
        self.assertEqual(cell.children_count, 77)


class ParsePlannedYouthTests(SimpleTestCase):
    """parse_planned_youth: fold the staff CSV (static/data/2026_feb_youth_numbers.csv)
    into {(name_lower, bucket): {programme: planned}}. The CSV splits three
    programmes into Primary/ECD sub-columns that sum into one grid programme; the
    'Total Youth' column is staff-maintained and not the row sum, so it's ignored.
    """

    def _row(self, name, ctype, **cols):
        base = {
            "School or ECD": name, "Center Type": ctype,
            "YearBeyond": "", "Masi Lit Primary": "", "ZZ Primary": "",
            "Masi Lit ECD": "", "1000 Stories": "", "ZZ ECD": "",
            "Primary Numeracy": "", "Edu Tech": "", "ECD Numeracy": "",
            "Total Youth": "",
        }
        base.update(cols)
        return base

    def test_sums_phase_split_subcolumns_into_one_programme(self):
        from api.school_programme import parse_planned_youth

        rows = [self._row("Aaron Gqadu", "Primary School",
                          **{"Masi Lit Primary": "4", "Masi Lit ECD": "2",
                             "Primary Numeracy": "1", "1000 Stories": "1"})]
        out = parse_planned_youth(rows)
        self.assertEqual(out[("aaron gqadu", "Primary")], {
            "masi_literacy": 6, "numeracy": 1, "thousand_stories": 1,
        })

    def test_yearbeyond_maps_to_yebo(self):
        from api.school_programme import parse_planned_youth

        rows = [self._row("Astra", "Primary School",
                          **{"YearBeyond": "8", "ZZ Primary": "4", "1000 Stories": "1"})]
        out = parse_planned_youth(rows)
        self.assertEqual(out[("astra", "Primary")],
                         {"yebo": 8, "zazi_izandi": 4, "thousand_stories": 1})

    def test_ignores_untrustworthy_total_youth_column(self):
        from api.school_programme import parse_planned_youth

        # Total Youth says 15 but the programme columns sum to 4.
        rows = [self._row("Somewhere", "Primary School",
                          **{"Masi Lit Primary": "4", "Total Youth": "15"})]
        out = parse_planned_youth(rows)
        self.assertEqual(out[("somewhere", "Primary")], {"masi_literacy": 4})

    def test_merges_duplicate_name_bucket_rows(self):
        from api.school_programme import parse_planned_youth

        # The CSV has Lukhanyiso [ECDC] twice: ZZ ECD=1 and ECD Numeracy=2.
        rows = [
            self._row("Lukhanyiso", "ECDC", **{"ZZ ECD": "1"}),
            self._row("Lukhanyiso", "ECDC", **{"ECD Numeracy": "2"}),
        ]
        out = parse_planned_youth(rows)
        self.assertEqual(out[("lukhanyiso", "ECD")],
                         {"zazi_izandi": 1, "numeracy": 2})

    def test_same_name_different_bucket_stays_separate(self):
        from api.school_programme import parse_planned_youth

        rows = [
            self._row("Msobomvu", "Primary School", **{"ZZ Primary": "5"}),
            self._row("Msobomvu", "ECDC", **{"ZZ ECD": "1"}),
        ]
        out = parse_planned_youth(rows)
        self.assertEqual(out[("msobomvu", "Primary")], {"zazi_izandi": 5})
        self.assertEqual(out[("msobomvu", "ECD")], {"zazi_izandi": 1})

    def test_skips_non_grid_center_types_and_blank_names(self):
        from api.school_programme import parse_planned_youth

        rows = [
            self._row("WIND FARMS", "", **{"Masi Lit Primary": "3"}),
            self._row("", "Primary School", **{"Masi Lit Primary": "3"}),
            self._row("Some High", "Secondary School", **{"Masi Lit Primary": "3"}),
        ]
        self.assertEqual(parse_planned_youth(rows), {})

    def test_drops_sites_with_no_planned_youth(self):
        from api.school_programme import parse_planned_youth

        # All programme columns blank/zero -> the site is omitted entirely.
        rows = [self._row("Empty Site", "Primary School", **{"Total Youth": "0"})]
        self.assertEqual(parse_planned_youth(rows), {})

    def test_tolerates_typo_center_types(self):
        from api.school_programme import parse_planned_youth

        # Real CSV noise: "Primary Schoo" and "ECDC0".
        rows = [
            self._row("Fumisukoma", "Primary Schoo", **{"YearBeyond": "6"}),
            self._row("Nomtha", "ECDC0", **{"1000 Stories": "0"}),
        ]
        out = parse_planned_youth(rows)
        self.assertEqual(out[("fumisukoma", "Primary")], {"yebo": 6})
        self.assertNotIn(("nomtha", "ECD"), out)  # zero -> dropped


class SeedYouthPlannedCommandTests(TestCase):
    """seed_youth_planned: load management's planned-youth allocations from the
    Feb-2026 CSV into the human-owned youth_planned column. Names resolve through
    a frozen, Jim-reviewed (name, bucket) -> school_uid map; cells that don't yet
    exist are created (so a planned-but-unstaffed programme shows as a vacancy);
    idempotent and re-runnable. Uses real frozen-map uids on test schools.
    """

    YEAR = 2026
    HEADER = ("School or ECD,Center Type,YearBeyond,Masi Lit Primary,ZZ Primary,"
              "Masi Lit ECD,1000 Stories,ZZ ECD,Primary Numeracy,Edu Tech,"
              "ECD Numeracy,Total Youth")

    def setUp(self):
        from api.models import School

        # uids are the real Jim-approved matches for these CSV names.
        self.aaron = School.objects.create(
            name="Aaron Gqadu", school_uid="SCH-00276",
            type="Primary School", is_active=True,
        )
        self.astra = School.objects.create(
            name="Astra", school_uid="SCH-00278",
            type="Primary School", is_active=True,
        )
        self.lukhanyiso = School.objects.create(
            name="Lukhanyiso", school_uid="SCH-00229",
            type="ECDC", is_active=True,
        )

    def _csv(self, *lines):
        import os, tempfile

        fd, path = tempfile.mkstemp(suffix=".csv")
        with os.fdopen(fd, "w") as f:
            f.write(self.HEADER + "\n")
            for line in lines:
                f.write(line + "\n")
        self.addCleanup(os.remove, path)
        return path

    def _run(self, path, **kw):
        from io import StringIO
        from django.core.management import call_command

        out = StringIO()
        call_command("seed_youth_planned", csv=path, year=self.YEAR,
                     stdout=out, stderr=out, **kw)
        return out.getvalue()

    def test_creates_cells_with_summed_youth_planned(self):
        from api.models import SchoolProgrammeYear

        # Aaron Gqadu: Masi Lit Primary 4 + Masi Lit ECD 2 = 6 literacy, 1 numeracy.
        path = self._csv("Aaron Gqadu,Primary School,,4,,2,,,1,,,15")
        self._run(path)

        lit = SchoolProgrammeYear.objects.get(
            school=self.aaron, programme="masi_literacy", year=self.YEAR)
        num = SchoolProgrammeYear.objects.get(
            school=self.aaron, programme="numeracy", year=self.YEAR)
        self.assertEqual(lit.youth_planned, 6)
        self.assertEqual(num.youth_planned, 1)

    def test_created_cell_is_an_unstaffed_vacancy(self):
        # The whole point: a planned programme with no active youth yet still gets
        # a cell, with youth_active 0 and the cron-consistent config.
        from api.models import SchoolProgrammeYear

        path = self._csv("Astra,Primary School,8,,,,,,,,,8")
        self._run(path)

        cell = SchoolProgrammeYear.objects.get(
            school=self.astra, programme="yebo", year=self.YEAR)
        self.assertEqual(cell.youth_planned, 8)
        self.assertEqual(cell.youth_active, 0)
        self.assertEqual(cell.count_source, "manual")

    def test_sets_planned_without_touching_existing_youth_active(self):
        # A cell the cron already wrote (active staff present) keeps its
        # youth_active; the seed only fills the human-owned youth_planned.
        from api.models import SchoolProgrammeYear

        existing = SchoolProgrammeYear.objects.create(
            school=self.aaron, programme="masi_literacy", year=self.YEAR,
            count_source="computed", count_basis="child_level", youth_active=5,
        )
        path = self._csv("Aaron Gqadu,Primary School,,6,,,,,,,,6")
        self._run(path)

        existing.refresh_from_db()
        self.assertEqual(existing.youth_planned, 6)
        self.assertEqual(existing.youth_active, 5)  # untouched

    def test_is_idempotent(self):
        from api.models import SchoolProgrammeYear

        path = self._csv("Lukhanyiso,ECDC,,,,,,1,,,2,3")  # zazi 1, numeracy 2
        self._run(path)
        self._run(path)  # second run must not duplicate or change

        rows = SchoolProgrammeYear.objects.filter(
            school=self.lukhanyiso, year=self.YEAR)
        self.assertEqual(rows.count(), 2)
        self.assertEqual(rows.get(programme="zazi_izandi").youth_planned, 1)
        self.assertEqual(rows.get(programme="numeracy").youth_planned, 2)

    def test_skips_unmapped_site_and_reports_it(self):
        from api.models import SchoolProgrammeYear

        # Wittekleibosch has no canonical match -> skipped, not a crash.
        path = self._csv(
            "Aaron Gqadu,Primary School,,4,,,,,,,,4",
            "Wittekleibosch,ECDC,,,,,,1,,,,1",
        )
        output = self._run(path)
        self.assertTrue(SchoolProgrammeYear.objects.filter(
            school=self.aaron, programme="masi_literacy").exists())
        self.assertIn("wittekleibosch", output.lower())

    def test_dry_run_writes_nothing(self):
        from api.models import SchoolProgrammeYear

        path = self._csv("Aaron Gqadu,Primary School,,4,,,,,,,,4")
        self._run(path, dry_run=True)
        self.assertEqual(
            SchoolProgrammeYear.objects.filter(year=self.YEAR).count(), 0)


class ParseChildrenServedTests(SimpleTestCase):
    """parse_children_served: fold the 1000 Stories / EduTech children CSV into
    {(name_lower, bucket): {programme: count}}. The file stacks an ECD block then a
    PRIMARY block under one header (no Center Type column), so bucket is read from
    block position -- the Primary block starts at the first repeated name. Primary
    1000 Stories reach is a percent of enrolment, so it arrives as a decimal and is
    rounded; blanks / non-positive values and blank-name rows are dropped.
    """

    def test_block_position_sets_bucket(self):
        from api.school_programme import parse_children_served

        rows = [
            ["Ekhaya", "35", ""],            # ECD block
            ["Aaron Gqadu", "33", ""],       # ECD block
            ["Aaron Gqadu", "153.6", "81"],  # repeat -> Primary block starts here
            ["Astra", "651", ""],            # Primary block
        ]
        out = parse_children_served(rows)
        self.assertEqual(out[("ekhaya", "ECD")], {"thousand_stories": 35})
        self.assertEqual(out[("astra", "Primary")], {"thousand_stories": 651})

    def test_same_name_in_both_blocks_stays_separate(self):
        from api.school_programme import parse_children_served

        rows = [
            ["Aaron Gqadu", "33", ""],
            ["Aaron Gqadu", "153.6", "81"],
        ]
        out = parse_children_served(rows)
        self.assertEqual(out[("aaron gqadu", "ECD")], {"thousand_stories": 33})
        self.assertEqual(out[("aaron gqadu", "Primary")],
                         {"thousand_stories": 154, "edutech": 81})

    def test_rounds_decimal_reach_to_int(self):
        from api.school_programme import parse_children_served

        # 615.6 -> 616. The 2nd "A" repeats -> that row is the Primary block.
        rows = [["A", "1", ""], ["A", "615.6", ""]]
        out = parse_children_served(rows)
        self.assertEqual(out[("a", "Primary")]["thousand_stories"], 616)

    def test_blank_and_nonpositive_values_dropped(self):
        from api.school_programme import parse_children_served

        rows = [
            ["Lukhanyiso", "", ""],  # blank -> no key
            ["Zero Site", "0", ""],  # zero -> dropped
        ]
        out = parse_children_served(rows)
        self.assertNotIn(("lukhanyiso", "ECD"), out)
        self.assertNotIn(("zero site", "ECD"), out)

    def test_blank_name_row_skipped(self):
        from api.school_programme import parse_children_served

        self.assertEqual(parse_children_served([["", "10", ""]]), {})


class SeedChildrenServedCommandTests(TestCase):
    """seed_children_served: load 1000 Stories + EduTech children counts into the
    human-owned children_count column through a frozen (name, bucket) -> school_uid
    map. Cells absent from the grid are created (the create_cell path), carrying the
    per-programme count_basis; the cron's youth columns are never touched; the seed
    is idempotent. Uses real frozen-map uids on test schools.
    """

    YEAR = 2026
    HEADER = "All Sites,1000 stories,EduTech"

    def setUp(self):
        from api.models import School

        # uids are the real Jim-approved matches for these CSV names.
        self.ekhaya = School.objects.create(
            name="Ekhaya", school_uid="SCH-00282", type="ECDC", is_active=True)
        self.aaron = School.objects.create(
            name="Aaron Gqadu", school_uid="SCH-00276",
            type="Primary School", is_active=True)
        self.charles = School.objects.create(
            name="Charles Duna", school_uid="SCH-00281",
            type="Primary School", is_active=True)
        self.aaron_ecd = School.objects.create(
            name="Aaron Gqadu ECD", school_uid="SCH-00332",
            type="ECDC", is_active=True)

    def _csv(self, *lines):
        import os
        import tempfile

        fd, path = tempfile.mkstemp(suffix=".csv")
        with os.fdopen(fd, "w") as f:
            f.write(self.HEADER + "\n")
            for line in lines:
                f.write(line + "\n")
        self.addCleanup(os.remove, path)
        return path

    def _run(self, path, **kw):
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command("seed_children_served", csv=path, year=self.YEAR,
                     stdout=out, stderr=out, **kw)
        return out.getvalue()

    def test_seeds_all_buckets_including_colocated_ecd(self):
        from api.models import SchoolProgrammeYear

        path = self._csv(
            "Ekhaya,35,",               # ECD: 1000 Stories whole-school
            "Aaron Gqadu,33,",          # ECD block: the co-located ECD
            "Aaron Gqadu,154,81",       # repeat -> Primary block starts here
            "Charles Duna,615.6,1001",  # Primary: 1000 Stories (%) + EduTech
        )
        self._run(path)

        ekhaya = SchoolProgrammeYear.objects.get(
            school=self.ekhaya, programme="thousand_stories", year=self.YEAR)
        self.assertEqual(ekhaya.children_count, 35)
        self.assertEqual(ekhaya.count_basis, "whole_school")
        self.assertEqual(ekhaya.count_source, "manual")

        colocated = SchoolProgrammeYear.objects.get(
            school=self.aaron_ecd, programme="thousand_stories", year=self.YEAR)
        self.assertEqual(colocated.children_count, 33)

        aaron_ts = SchoolProgrammeYear.objects.get(
            school=self.aaron, programme="thousand_stories", year=self.YEAR)
        self.assertEqual(aaron_ts.children_count, 154)
        self.assertEqual(aaron_ts.count_basis, "percent_of_school")
        aaron_et = SchoolProgrammeYear.objects.get(
            school=self.aaron, programme="edutech", year=self.YEAR)
        self.assertEqual(aaron_et.children_count, 81)
        self.assertEqual(aaron_et.count_basis, "whole_school")

        charles_ts = SchoolProgrammeYear.objects.get(
            school=self.charles, programme="thousand_stories", year=self.YEAR)
        self.assertEqual(charles_ts.children_count, 616)  # 615.6 rounded

    def test_is_idempotent(self):
        from api.models import SchoolProgrammeYear

        path = self._csv("Ekhaya,35,")
        self._run(path)
        self._run(path)
        rows = SchoolProgrammeYear.objects.filter(school=self.ekhaya, year=self.YEAR)
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.get(programme="thousand_stories").children_count, 35)

    def test_does_not_touch_cron_youth_columns(self):
        from api.models import SchoolProgrammeYear

        existing = SchoolProgrammeYear.objects.create(
            school=self.aaron, programme="thousand_stories", year=self.YEAR,
            count_source="manual", count_basis="percent_of_school",
            youth_active=3, youth_planned=2,
        )
        path = self._csv(
            "Ekhaya,1,",
            "Aaron Gqadu,5,",      # ECD block (co-located ECD)
            "Aaron Gqadu,154,",    # repeat -> Primary block (the existing cell)
        )
        self._run(path)

        existing.refresh_from_db()
        self.assertEqual(existing.children_count, 154)
        self.assertEqual(existing.youth_active, 3)   # untouched
        self.assertEqual(existing.youth_planned, 2)  # untouched

    def test_skips_unmapped_site_and_reports_it(self):
        from api.models import SchoolProgrammeYear

        output = self._run(self._csv("Nowhere Educare,9,"))
        self.assertEqual(
            SchoolProgrammeYear.objects.filter(year=self.YEAR).count(), 0)
        self.assertIn("nowhere", output.lower())

    def test_dry_run_writes_nothing(self):
        from api.models import SchoolProgrammeYear

        self._run(self._csv("Ekhaya,35,"), dry_run=True)
        self.assertEqual(
            SchoolProgrammeYear.objects.filter(year=self.YEAR).count(), 0)
