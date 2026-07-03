"""Tests for the literacy WIG outcome measures (api/wig_outcomes.py)."""
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from api.models import AirtableSyncLog, LiteracyAssessment2026, OnTheProgramme2026
from api.wig_outcomes import REQUIRED_SYNCS, check_sources, build_outcomes

_seq = {"n": 0}


def make_logs(hours_ago=1, success=True, details=None, only=None):
    """Create a sync log per required sync type (or `only` a subset)."""
    for sync_type in (only or REQUIRED_SYNCS):
        AirtableSyncLog.objects.create(
            sync_type=sync_type, success=success,
            completed_at=timezone.now() - timedelta(hours=hours_ago),
            details=details,
        )


def roster(uid, grade="Grade 1", on_programme=True, active=True):
    _seq["n"] += 1
    return OnTheProgramme2026.objects.create(
        source_airtable_id=f"rec-r{_seq['n']}", child_uid=uid,
        on_the_programme=on_programme, grade=grade, is_active=active)


def assess(uid, term="Jun", read_words=None, letter_sounds=None, grade=None,
           duplicate_status="Single", year=2026, active=True):
    _seq["n"] += 1
    return LiteracyAssessment2026.objects.create(
        source_airtable_id=f"rec-a{_seq['n']}", child_uid=uid, year=year, term=term,
        grade=grade, read_words=read_words, letter_sounds=letter_sounds,
        duplicate_status=duplicate_status, is_active=active)


class CheckSourcesTests(TestCase):
    """Fail-closed source gate: exporter's _assert_synced rules + 48h dead-cron age."""

    def test_no_logs_fails(self):
        ok, note = check_sources(timezone.now())
        self.assertFalse(ok)
        self.assertIn("literacy_assessments_2026", note)

    def test_failed_latest_sync_fails(self):
        make_logs(success=False)
        ok, note = check_sources(timezone.now())
        self.assertFalse(ok)
        self.assertIn("failed", note)

    def test_newer_failed_sync_not_masked_by_older_success(self):
        make_logs(hours_ago=5, success=True)
        make_logs(hours_ago=1, success=False, only=("literacy_assessments_2026",))
        ok, _ = check_sources(timezone.now())
        self.assertFalse(ok)

    def test_flagged_details_fail(self):
        make_logs(details={"retire_skipped": 2})
        ok, note = check_sources(timezone.now())
        self.assertFalse(ok)
        self.assertIn("flagged", note)

    def test_stale_sync_fails(self):
        make_logs(hours_ago=72)
        ok, note = check_sources(timezone.now())
        self.assertFalse(ok)
        self.assertIn("48", note)

    def test_one_fresh_one_stale_fails(self):
        make_logs(hours_ago=1, only=("literacy_assessments_2026",))
        make_logs(hours_ago=72, only=("on_the_programme_2026",))
        ok, _ = check_sources(timezone.now())
        self.assertFalse(ok)

    def test_healthy_logs_pass(self):
        make_logs(hours_ago=1)
        ok, note = check_sources(timezone.now())
        self.assertTrue(ok)
        self.assertIsNone(note)


class OutcomeComputationTests(TestCase):
    def setUp(self):
        make_logs()

    def test_healthy_logs_no_rows_available_with_null_outcomes(self):
        payload = build_outcomes()
        self.assertTrue(payload["available"])
        self.assertIsNone(payload["outcomes"]["core_literacy"])
        self.assertIsNone(payload["outcomes"]["ecd_literacy"])

    def test_threshold_boundary_exactly_16_passes(self):
        roster("CH-1")
        assess("CH-1", read_words=16.0)
        out = build_outcomes()["outcomes"]["core_literacy"]
        self.assertEqual(out["value"], 1.0)
        self.assertEqual((out["numerator"], out["denominator"]), (1, 1))
        self.assertEqual(out["term"], "Jun")

    def test_below_threshold_fails(self):
        roster("CH-1")
        assess("CH-1", read_words=15.9)
        out = build_outcomes()["outcomes"]["core_literacy"]
        self.assertEqual(out["value"], 0.0)

    def test_null_score_excluded_from_denominator(self):
        roster("CH-1"); roster("CH-2")
        assess("CH-1", read_words=20.0)
        assess("CH-2", read_words=None, letter_sounds=5.0)  # assessed, but no Read Words
        out = build_outcomes()["outcomes"]["core_literacy"]
        self.assertEqual(out["denominator"], 1)

    def test_off_roster_child_excluded(self):
        roster("CH-1")
        assess("CH-1", read_words=20.0)
        assess("CH-99", read_words=20.0, grade="Grade 1")  # not on roster
        out = build_outcomes()["outcomes"]["core_literacy"]
        self.assertEqual(out["denominator"], 1)

    def test_inactive_or_off_programme_roster_rows_excluded(self):
        roster("CH-1")
        roster("CH-2", on_programme=False)
        roster("CH-3", active=False)
        assess("CH-1", read_words=20.0)
        assess("CH-2", read_words=20.0)
        assess("CH-3", read_words=20.0)
        out = build_outcomes()["outcomes"]["core_literacy"]
        self.assertEqual(out["denominator"], 1)
        self.assertEqual(out["cohort_total"], 1)

    def test_latest_term_jun_over_jan_with_baseline(self):
        roster("CH-1")
        assess("CH-1", term="Jan", read_words=10.0)
        assess("CH-1", term="Jun", read_words=20.0)
        out = build_outcomes()["outcomes"]["core_literacy"]
        self.assertEqual(out["term"], "Jun")
        self.assertEqual(out["value"], 1.0)
        self.assertEqual(out["baseline"]["term"], "Jan")
        self.assertEqual(out["baseline"]["value"], 0.0)

    def test_nov_rows_ignored_until_parity_surfaces_support_endline(self):
        # Enabled together with the exporter/portal Nov support (see TERM_ORDER).
        roster("CH-1")
        assess("CH-1", term="Jun", read_words=10.0)
        assess("CH-1", term="Nov", read_words=20.0)
        out = build_outcomes()["outcomes"]["core_literacy"]
        self.assertEqual(out["term"], "Jun")
        self.assertEqual(out["value"], 0.0)

    def test_out_of_range_read_words_treated_as_missing(self):
        roster("CH-1"); roster("CH-2")
        assess("CH-1", read_words=41.0)   # above instrument max 40: data error
        assess("CH-2", read_words=40.0)   # boundary value is in range and passes
        out = build_outcomes()["outcomes"]["core_literacy"]
        self.assertEqual((out["numerator"], out["denominator"]), (1, 1))

    def test_out_of_range_letter_sounds_treated_as_missing(self):
        roster("CH-1", grade="PreR")
        assess("CH-1", letter_sounds=61.0)  # above instrument max 60
        self.assertIsNone(build_outcomes()["outcomes"]["ecd_literacy"])

    def test_only_jan_data_has_no_baseline_field(self):
        roster("CH-1")
        assess("CH-1", term="Jan", read_words=20.0)
        out = build_outcomes()["outcomes"]["core_literacy"]
        self.assertEqual(out["term"], "Jan")
        self.assertIsNone(out["baseline"])

    def test_cohort_total_counts_unassessed_roster_children(self):
        roster("CH-1"); roster("CH-2"); roster("CH-3")
        assess("CH-1", read_words=20.0)
        out = build_outcomes()["outcomes"]["core_literacy"]
        self.assertEqual(out["cohort_total"], 3)
        self.assertEqual(out["denominator"], 1)

    def test_ecd_uses_letter_sounds_threshold_20(self):
        roster("CH-1", grade="PreR")
        assess("CH-1", letter_sounds=20.0)
        out = build_outcomes()["outcomes"]["ecd_literacy"]
        self.assertEqual(out["value"], 1.0)

    def test_prior_year_rows_ignored(self):
        roster("CH-1")
        assess("CH-1", read_words=20.0, year=2025)
        self.assertIsNone(build_outcomes()["outcomes"]["core_literacy"])


class DedupeFailClosedTests(TestCase):
    def setUp(self):
        make_logs()
        roster("CH-1")

    def test_duplicate_row_cannot_flip_child_to_passing(self):
        assess("CH-1", read_words=10.0, duplicate_status="Single")
        assess("CH-1", read_words=30.0, duplicate_status="Duplicate")
        payload = build_outcomes()
        self.assertTrue(payload["available"])  # equal completeness: no exception
        self.assertEqual(payload["outcomes"]["core_literacy"]["value"], 0.0)

    def test_duplicate_more_complete_fails_closed(self):
        assess("CH-1", read_words=10.0, duplicate_status="Single")
        assess("CH-1", read_words=30.0, letter_sounds=5.0, duplicate_status="Duplicate")
        payload = build_outcomes()
        self.assertFalse(payload["available"])
        self.assertIn("dedupe", payload["source_note"])

    def test_unresolved_tie_fails_closed(self):
        assess("CH-1", read_words=10.0, duplicate_status="Single")
        assess("CH-1", read_words=30.0, duplicate_status="Single")
        payload = build_outcomes()
        self.assertFalse(payload["available"])


class GradeCohortTests(TestCase):
    def setUp(self):
        make_logs()

    def test_roster_grade_wins_over_assessment_grade(self):
        roster("CH-1", grade="Grade 1")
        assess("CH-1", read_words=20.0, letter_sounds=20.0, grade="PreR")
        payload = build_outcomes()["outcomes"]
        self.assertEqual(payload["core_literacy"]["denominator"], 1)
        self.assertIsNone(payload["ecd_literacy"])

    def test_alias_roster_grade_normalized(self):
        roster("CH-1", grade="gr 1")
        assess("CH-1", read_words=20.0)
        self.assertEqual(build_outcomes()["outcomes"]["core_literacy"]["denominator"], 1)

    def test_missing_roster_grade_falls_back_to_assessment_grade(self):
        roster("CH-1", grade=None)
        assess("CH-1", read_words=20.0, grade="Grade 1")
        self.assertEqual(build_outcomes()["outcomes"]["core_literacy"]["denominator"], 1)

    def test_fallback_grade_lands_in_prer_and_is_counted(self):
        roster("CH-1", grade="Little Stars Centre")
        assess("CH-1", letter_sounds=20.0)
        out = build_outcomes()["outcomes"]["ecd_literacy"]
        self.assertEqual(out["denominator"], 1)
        self.assertIn("1 grade fallback", out["calculation_note"])


class BuildOutcomesSourceGateTests(TestCase):
    """build_outcomes() itself fails closed when sources are unhealthy."""

    def test_unavailable_with_no_sync_logs(self):
        payload = build_outcomes()
        self.assertFalse(payload["available"])
        self.assertIn("literacy_assessments_2026", payload["source_note"])
        self.assertEqual(payload["outcomes"], {})

    def test_unavailable_when_one_sync_is_stale(self):
        make_logs(hours_ago=1, only=("literacy_assessments_2026",))
        make_logs(hours_ago=72, only=("on_the_programme_2026",))
        payload = build_outcomes()
        self.assertFalse(payload["available"])
        self.assertEqual(payload["outcomes"], {})


class OutcomeEndpointTests(TestCase):
    """/api/wig/outcomes/ is wired and role-gated (ADMIN / PROJECT MANAGER only)."""

    def _client_as(self, name, role):
        u = User.objects.create(username=name)
        u.profile.role = role
        u.profile.save()
        c = APIClient()
        c.force_authenticate(u)
        return c

    def test_admin_gets_payload_via_url(self):
        make_logs()
        roster("CH-1")
        assess("CH-1", read_words=20.0)
        r = self._client_as('a', 'ADMIN').get('/api/wig/outcomes/')
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body['available'])
        self.assertEqual(body['outcomes']['core_literacy']['numerator'], 1)

    def test_project_manager_allowed(self):
        r = self._client_as('pm', 'PROJECT MANAGER').get('/api/wig/outcomes/')
        self.assertEqual(r.status_code, 200)

    def test_mentor_denied(self):
        r = self._client_as('m', 'MENTOR').get('/api/wig/outcomes/')
        self.assertEqual(r.status_code, 403)

    def test_anonymous_denied(self):
        r = APIClient().get('/api/wig/outcomes/')
        self.assertIn(r.status_code, (401, 403))
