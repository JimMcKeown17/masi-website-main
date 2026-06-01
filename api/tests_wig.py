"""Tests for the WIG dashboard metric service (api/wig_metrics.py)."""
from datetime import datetime, date, timezone as dt_timezone
from unittest.mock import patch

from django.contrib.auth.models import User, AnonymousUser
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIRequestFactory, APIClient

from api.models import (
    School, Youth, LiteracySession2026, NumeracySession2026, MentorVisit, CanonicalChild,
    ZaziOverviewSnapshot,
)
from api.permissions import IsAdminOrProjectManager
from api.zazi_client import build_zazi_measures, refresh_zazi_snapshot
from api.wig_detail import build_wig_detail
from core.models import UserProfile
from api.wig_metrics import (
    classify_literacy_site,
    last_completed_week,
    eligible_coaches,
    sessions_per_day,
    active_coaches,
    school_coverage,
    capture_on_time,
    duplicate_rate,
    site_job_mismatch,
    build_lead_measures,
    build_data_quality,
    visit_compliance,
    school_visits,
    child_fk_resolution,
)


class ClassifyLiteracySiteTests(SimpleTestCase):
    """A literacy session's programme is decided by its school's site type,
    not the coach's job title (site-type-first cohort model)."""

    def test_primary_school_is_core_literacy(self):
        self.assertEqual(classify_literacy_site('Primary School'), 'core_literacy')

    def test_ecdc_is_ecd_literacy(self):
        self.assertEqual(classify_literacy_site('ECDC'), 'ecd_literacy')

    def test_ecd_spelling_variant_is_ecd_literacy(self):
        self.assertEqual(classify_literacy_site('ECD'), 'ecd_literacy')

    def test_secondary_school_is_not_a_literacy_programme(self):
        self.assertIsNone(classify_literacy_site('Secondary School'))

    def test_blank_or_missing_site_type_is_none(self):
        self.assertIsNone(classify_literacy_site(None))
        self.assertIsNone(classify_literacy_site(''))


class LastCompletedWeekTests(SimpleTestCase):
    """The WIG window is the last completed Mon-Sun week, in Africa/Johannesburg
    (the server runs UTC, which mis-buckets the boundary)."""

    def test_returns_previous_monday_to_sunday(self):
        ref = datetime(2026, 5, 30, 12, 0, tzinfo=dt_timezone.utc)  # a Saturday
        start, end = last_completed_week(ref)
        self.assertEqual(start, date(2026, 5, 18))  # Monday
        self.assertEqual(end, date(2026, 5, 24))    # Sunday

    def test_uses_sast_not_utc_at_day_boundary(self):
        # Sun 23:00 UTC == Mon 01:00 SAST. In SAST the Mon-Sun week that ended
        # on that Sunday is complete; using UTC would pick the week before.
        ref = datetime(2026, 5, 31, 23, 0, tzinfo=dt_timezone.utc)
        start, end = last_completed_week(ref)
        self.assertEqual(start, date(2026, 5, 25))
        self.assertEqual(end, date(2026, 5, 31))


class EligibleCoachesTests(TestCase):
    """Programme cohorts are site-type-first: the same job title (Literacy Coach)
    is Core at a Primary site and ECD at an ECDC site. Active + started only.
    Zazi iZandi is NOT a Masi cohort (it comes from the Zazi backend)."""

    AS_OF = date(2026, 5, 24)

    def setUp(self):
        self.primary = School.objects.create(name='P', type='Primary School', school_uid='SCH-P')
        self.ecdc = School.objects.create(name='E', type='ECDC', school_uid='SCH-E')

    def _coach(self, eid, title, school, status='Active', start=date(2026, 1, 1)):
        return Youth.objects.create(
            employee_id=eid, first_names='F', last_name=str(eid),
            job_title=title, school=school, employment_status=status, start_date=start,
        )

    def test_core_literacy_includes_primary_literacy_coach(self):
        y = self._coach(1, 'Literacy Coach', self.primary)
        self.assertIn(y, eligible_coaches('core_literacy', self.AS_OF))

    def test_core_literacy_excludes_ecdc_literacy_coach(self):
        y = self._coach(2, 'Literacy Coach', self.ecdc)
        self.assertNotIn(y, eligible_coaches('core_literacy', self.AS_OF))

    def test_ecd_literacy_includes_ecdc_literacy_coach(self):
        y = self._coach(3, 'Literacy Coach', self.ecdc)
        self.assertIn(y, eligible_coaches('ecd_literacy', self.AS_OF))

    def test_excludes_inactive_coach(self):
        y = self._coach(4, 'Literacy Coach', self.primary, status='Inactive')
        self.assertNotIn(y, eligible_coaches('core_literacy', self.AS_OF))

    def test_excludes_coach_starting_after_window(self):
        y = self._coach(5, 'Literacy Coach', self.primary, start=date(2026, 6, 1))
        self.assertNotIn(y, eligible_coaches('core_literacy', self.AS_OF))

    def test_zazi_izandi_coach_is_in_no_masi_cohort(self):
        y = self._coach(6, 'Zazi Izandi Coach', self.primary)
        self.assertNotIn(y, eligible_coaches('core_literacy', self.AS_OF))
        self.assertNotIn(y, eligible_coaches('ecd_literacy', self.AS_OF))


class SessionsPerDayTests(TestCase):
    """sessions/day = sessions in window / (eligible coaches x working days).
    Window 2026-05-18..24 is a Mon-Sun week = 5 working days."""

    START = date(2026, 5, 18)
    END = date(2026, 5, 24)

    def setUp(self):
        self.primary = School.objects.create(name='P', type='Primary School', school_uid='SCH-P')
        self.ecdc = School.objects.create(name='E', type='ECDC', school_uid='SCH-E')
        self.coach = Youth.objects.create(
            employee_id=1, first_names='F', last_name='1', job_title='Literacy Coach',
            school=self.primary, start_date=date(2026, 1, 1),
        )

    def _session(self, n, school, day):
        return LiteracySession2026.objects.create(
            source_airtable_id=f's{n}', session_date=day, youth=self.coach, school=school,
        )

    def test_value_is_sessions_over_eligible_times_working_days(self):
        for i in range(10):
            self._session(i, self.primary, date(2026, 5, 20))  # Wednesday, in window
        m = sessions_per_day('core_literacy', self.START, self.END)
        self.assertEqual(m['numerator'], 10)
        self.assertEqual(m['eligible_entity_count'], 1)
        self.assertEqual(m['value'], 2.0)  # 10 / (1 coach x 5 working days)

    def test_excludes_sessions_outside_window(self):
        self._session(1, self.primary, date(2026, 5, 10))  # before window
        self.assertEqual(sessions_per_day('core_literacy', self.START, self.END)['numerator'], 0)

    def test_ecdc_session_not_counted_for_core(self):
        self._session(1, self.ecdc, date(2026, 5, 20))
        self.assertEqual(sessions_per_day('core_literacy', self.START, self.END)['numerator'], 0)

    def test_zero_eligible_coaches_gives_none_value(self):
        m = sessions_per_day('numeracy', self.START, self.END)
        self.assertEqual(m['eligible_entity_count'], 0)
        self.assertIsNone(m['value'])


class ActiveCoachesTests(TestCase):
    """% of eligible coaches who taught at least one session this window."""

    START = date(2026, 5, 18)
    END = date(2026, 5, 24)

    def setUp(self):
        self.primary = School.objects.create(name='P', type='Primary School', school_uid='SCH-P')
        self.a = Youth.objects.create(employee_id=1, first_names='A', last_name='1',
                                      job_title='Literacy Coach', school=self.primary, start_date=date(2026, 1, 1))
        self.b = Youth.objects.create(employee_id=2, first_names='B', last_name='2',
                                      job_title='Literacy Coach', school=self.primary, start_date=date(2026, 1, 1))

    def test_fraction_of_eligible_that_taught(self):
        LiteracySession2026.objects.create(source_airtable_id='s1', session_date=date(2026, 5, 20),
                                            youth=self.a, school=self.primary)
        m = active_coaches('core_literacy', self.START, self.END)
        self.assertEqual(m['numerator'], 1)    # only A taught
        self.assertEqual(m['denominator'], 2)  # A and B eligible
        self.assertEqual(m['value'], 0.5)


class SchoolCoverageTests(TestCase):
    """Coverage = schools reached this window / schools with >=1 assigned coach."""

    START = date(2026, 5, 18)
    END = date(2026, 5, 24)

    def setUp(self):
        self.p1 = School.objects.create(name='P1', type='Primary School', school_uid='SCH-1')
        self.p2 = School.objects.create(name='P2', type='Primary School', school_uid='SCH-2')
        self.a = Youth.objects.create(employee_id=1, first_names='A', last_name='1',
                                      job_title='Literacy Coach', school=self.p1, start_date=date(2026, 1, 1))
        self.b = Youth.objects.create(employee_id=2, first_names='B', last_name='2',
                                      job_title='Literacy Coach', school=self.p2, start_date=date(2026, 1, 1))

    def test_covered_over_assigned_schools(self):
        LiteracySession2026.objects.create(source_airtable_id='s1', session_date=date(2026, 5, 20),
                                            youth=self.a, school=self.p1)
        m = school_coverage('core_literacy', self.START, self.END)
        self.assertEqual(m['numerator'], 1)    # p1 reached
        self.assertEqual(m['denominator'], 2)  # p1 + p2 assigned
        self.assertEqual(m['value'], 0.5)


class DataQualityTests(TestCase):
    """Data-team accuracy sub-gauges, computed over the full dataset."""

    def setUp(self):
        self.primary = School.objects.create(name='P', type='Primary School', school_uid='SCH-P')
        self.ecdc = School.objects.create(name='E', type='ECDC', school_uid='SCH-E')

    def _lit(self, n, delay=None, dup=None):
        return LiteracySession2026.objects.create(
            source_airtable_id=f'd{n}', capture_delay=delay, duplicate_status=dup,
        )

    def test_capture_on_time_is_within_two_days(self):
        self._lit(1, delay=0)
        self._lit(2, delay=2)
        self._lit(3, delay=5)
        m = capture_on_time()
        self.assertEqual(m['numerator'], 2)
        self.assertEqual(m['denominator'], 3)

    def test_duplicate_rate_counts_only_duplicate_status(self):
        self._lit(1, dup='Duplicate')
        self._lit(2, dup='Unique')
        self._lit(3, dup='Unique')
        self._lit(4, dup=None)
        m = duplicate_rate()
        self.assertEqual(m['numerator'], 1)
        self.assertEqual(m['denominator'], 4)

    def test_site_job_mismatch_flags_ecd_title_at_primary_site(self):
        Youth.objects.create(employee_id=1, first_names='A', last_name='1',
                             job_title='ZZ ECD Coach', school=self.primary)   # mismatch
        Youth.objects.create(employee_id=2, first_names='B', last_name='2',
                             job_title='ZZ ECD Coach', school=self.ecdc)      # correct
        Youth.objects.create(employee_id=3, first_names='C', last_name='3',
                             job_title='Literacy Coach', school=self.primary)  # correct
        m = site_job_mismatch()
        self.assertEqual(m['numerator'], 1)

    def test_child_fk_resolution_counts_both_slots(self):
        c1 = CanonicalChild.objects.create(source_airtable_id='c1', child_uid='CH-1', mcode=1)
        c2 = CanonicalChild.objects.create(source_airtable_id='c2', child_uid='CH-2', mcode=2)
        LiteracySession2026.objects.create(source_airtable_id='s1', child_1=c1, child_2=c2)
        LiteracySession2026.objects.create(source_airtable_id='s2', child_1=c1, child_2=None)
        m = child_fk_resolution()
        self.assertEqual(m['numerator'], 3)    # 3 resolved child slots
        self.assertEqual(m['denominator'], 4)  # 2 sessions x 2 slots
        self.assertEqual(m['value'], 0.75)


class VisitComplianceTests(TestCase):
    """% of observation visits where all tracker booleans are true. Attributed
    to a programme by the visited school's site type; nulls = non-compliant."""

    START = date(2026, 5, 18)
    END = date(2026, 5, 24)
    FULL = dict(letter_trackers_correct=True, reading_trackers_correct=True,
                sessions_correct=True, admin_correct=True)

    def setUp(self):
        self.primary = School.objects.create(name='P', type='Primary School', school_uid='SCH-P')
        self.ecdc = School.objects.create(name='E', type='ECDC', school_uid='SCH-E')
        self.m = User.objects.create(username='mentor')

    def _visit(self, school, day, vtype='observation', **bools):
        return MentorVisit.objects.create(mentor=self.m, school=school, visit_date=day,
                                          visit_type=vtype, **bools)

    def test_compliance_is_all_true_over_observations(self):
        self._visit(self.primary, date(2026, 5, 20), **self.FULL)
        self._visit(self.primary, date(2026, 5, 21), **self.FULL)
        self._visit(self.primary, date(2026, 5, 22), **{**self.FULL, 'admin_correct': False})
        m = visit_compliance('core_literacy', self.START, self.END)
        self.assertEqual(m['numerator'], 2)
        self.assertEqual(m['denominator'], 3)

    def test_excludes_non_observation_and_other_site_types(self):
        self._visit(self.primary, date(2026, 5, 20), vtype='meeting', **self.FULL)
        self._visit(self.ecdc, date(2026, 5, 20), **self.FULL)
        self.assertEqual(visit_compliance('core_literacy', self.START, self.END)['denominator'], 0)

    def test_null_boolean_is_incomplete_and_noncompliant(self):
        self._visit(self.primary, date(2026, 5, 20), letter_trackers_correct=True,
                    reading_trackers_correct=True, sessions_correct=True)  # admin_correct null
        m = visit_compliance('core_literacy', self.START, self.END)
        self.assertEqual(m['numerator'], 0)
        self.assertEqual(m['denominator'], 1)
        self.assertEqual(m['incomplete_count'], 1)


class SchoolVisitsTests(TestCase):
    """Average observation visits per mentor this window (per-mentor target)."""

    START = date(2026, 5, 18)
    END = date(2026, 5, 24)

    def setUp(self):
        self.primary = School.objects.create(name='P', type='Primary School', school_uid='SCH-P')
        self.m1 = User.objects.create(username='m1')
        self.m2 = User.objects.create(username='m2')

    def _visit(self, mentor, day):
        MentorVisit.objects.create(mentor=mentor, school=self.primary, visit_date=day,
                                   visit_type='observation')

    def test_avg_visits_per_mentor(self):
        for d in (20, 21, 22, 23):
            self._visit(self.m1, date(2026, 5, d))
        for d in (20, 21):
            self._visit(self.m2, date(2026, 5, d))
        m = school_visits('core_literacy', self.START, self.END)
        self.assertEqual(m['numerator'], 6)     # 4 + 2 visits
        self.assertEqual(m['denominator'], 2)   # 2 mentors
        self.assertEqual(m['value'], 3.0)


class AssemblyTests(TestCase):
    """The endpoint payloads: a window envelope + measures keyed by source."""

    def test_lead_measures_window_and_keys(self):
        ref = datetime(2026, 5, 30, 12, 0, tzinfo=dt_timezone.utc)  # Saturday
        payload = build_lead_measures(ref)
        self.assertEqual(payload['window']['date_from'], '2026-05-18')
        self.assertEqual(payload['window']['date_to'], '2026-05-24')
        self.assertEqual(payload['window']['working_days'], 5)
        for key in ('core_literacy.sessions_per_day', 'ecd_literacy.sessions_per_day',
                    'numeracy.sessions_per_week', 'core_literacy.school_coverage',
                    'core_literacy.tracker_compliance', 'core_literacy.school_visits',
                    'numeracy.admin_compliance'):
            self.assertIn(key, payload['measures'])

    def test_data_quality_has_sub_gauges(self):
        dq = build_data_quality()
        self.assertEqual(dq['scope'], 'full_dataset')
        for key in ('dq.capture_on_time', 'dq.duplicate_rate', 'dq.site_job_mismatch',
                    'dq.child_fk_resolution'):
            self.assertIn(key, dq['measures'])


class PermissionTests(TestCase):
    """WIG is leadership-only: ADMIN + PROJECT MANAGER, enforced server-side."""

    def _request_for(self, user):
        req = APIRequestFactory().get('/api/wig/lead-measures/')
        req.user = user
        return req

    def _user(self, name, role=None):
        u = User.objects.create(username=name)
        if role is not None:
            # A profile is auto-created by a post_save signal; update it.
            u.profile.role = role
            u.profile.save()
        return u

    def test_admin_allowed(self):
        ok = IsAdminOrProjectManager().has_permission(self._request_for(self._user('a', 'ADMIN')), None)
        self.assertTrue(ok)

    def test_project_manager_allowed(self):
        ok = IsAdminOrProjectManager().has_permission(self._request_for(self._user('pm', 'PROJECT MANAGER')), None)
        self.assertTrue(ok)

    def test_mentor_denied(self):
        ok = IsAdminOrProjectManager().has_permission(self._request_for(self._user('m', 'MENTOR')), None)
        self.assertFalse(ok)

    def test_user_without_profile_denied(self):
        u = User.objects.create(username='np')
        UserProfile.objects.filter(user=u).delete()
        ok = IsAdminOrProjectManager().has_permission(self._request_for(u), None)
        self.assertFalse(ok)

    def test_anonymous_denied(self):
        ok = IsAdminOrProjectManager().has_permission(self._request_for(AnonymousUser()), None)
        self.assertFalse(ok)


class WigEndpointTests(TestCase):
    """End-to-end: the wired endpoints return the payloads and enforce roles."""

    def _client_as(self, name, role):
        u = User.objects.create(username=name)
        u.profile.role = role
        u.profile.save()
        c = APIClient()
        c.force_authenticate(u)
        return c

    def test_admin_gets_lead_measures(self):
        r = self._client_as('a', 'ADMIN').get('/api/wig/lead-measures/')
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertIn('window', body)
        self.assertIn('core_literacy.sessions_per_day', body['measures'])

    def test_admin_gets_data_quality(self):
        r = self._client_as('a2', 'ADMIN').get('/api/wig/data-quality/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['scope'], 'full_dataset')

    def test_mentor_forbidden(self):
        r = self._client_as('m', 'MENTOR').get('/api/wig/lead-measures/')
        self.assertEqual(r.status_code, 403)

    def test_anonymous_unauthorized(self):
        r = APIClient().get('/api/wig/lead-measures/')
        self.assertIn(r.status_code, (401, 403))


# Sample of the Zazi backend's /api/programme-overview/ response (trimmed).
ZAZI_OVERVIEW = {
    'generated_at': '2026-06-01T00:36:48Z',
    'targets': {'dosage': 2.5, 'on_track_pct': 80.0},
    'kpis': {'pct_eas_on_track': 76.3, 'avg_sessions_per_day_worked': 3.2, 'weighted_dosage': 1.69},
}


class ZaziNormalizeTests(SimpleTestCase):
    """The Zazi backend already computes the metrics; we map its overview into
    the WIG measure shape (value + Zazi's own target)."""

    def test_maps_kpis_and_targets(self):
        ms = build_zazi_measures(ZAZI_OVERVIEW)['measures']
        self.assertEqual(ms['zazi.pct_eas_on_track']['value'], 76.3)
        self.assertEqual(ms['zazi.pct_eas_on_track']['target'], 80.0)
        self.assertEqual(ms['zazi.sessions_per_day']['value'], 3.2)
        self.assertEqual(ms['zazi.sessions_per_day']['target'], 2.5)


class RefreshZaziSnapshotTests(TestCase):
    """The Zazi overview is slow (~10s/call), so a cron refreshes a single
    cached snapshot row out-of-band. refresh_zazi_snapshot() does that fetch."""

    @patch('api.zazi_client.fetch_zazi_programme_overview', return_value=ZAZI_OVERVIEW)
    def test_refresh_stores_payload(self, _mock):
        snap = refresh_zazi_snapshot()
        self.assertEqual(ZaziOverviewSnapshot.objects.count(), 1)
        self.assertTrue(snap.ok)
        self.assertEqual(snap.payload, ZAZI_OVERVIEW)
        self.assertIsNotNone(snap.fetched_at)

    @patch('api.zazi_client.fetch_zazi_programme_overview')
    def test_refresh_keeps_last_good_on_error(self, mock_fetch):
        mock_fetch.return_value = ZAZI_OVERVIEW
        refresh_zazi_snapshot()  # seed a good snapshot
        mock_fetch.side_effect = Exception('zazi down')
        snap = refresh_zazi_snapshot()  # now fails
        # Still one row; last-good payload preserved, but flagged not-ok.
        self.assertEqual(ZaziOverviewSnapshot.objects.count(), 1)
        self.assertFalse(snap.ok)
        self.assertEqual(snap.payload, ZAZI_OVERVIEW)
        self.assertIn('zazi down', snap.error_message)


class ZaziEndpointTests(TestCase):
    """The Zazi tile endpoint serves the cached snapshot (never a live call on a
    board load), is role-gated, and degrades to 'unavailable' with no snapshot."""

    def _client_as(self, name, role):
        u = User.objects.create(username=name)
        u.profile.role = role
        u.profile.save()
        c = APIClient()
        c.force_authenticate(u)
        return c

    @patch('api.zazi_client.fetch_zazi_programme_overview', side_effect=Exception('must not be called'))
    def test_admin_gets_cached_measures_without_live_fetch(self, mock_fetch):
        ZaziOverviewSnapshot.objects.create(payload=ZAZI_OVERVIEW, ok=True)
        r = self._client_as('za', 'ADMIN').get('/api/wig/zazi/')
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body['available'])
        self.assertIn('zazi.pct_eas_on_track', body['measures'])
        mock_fetch.assert_not_called()  # served from cache, no slow live call

    @patch('api.zazi_client.fetch_zazi_programme_overview', side_effect=Exception('down'))
    def test_zazi_unavailable_is_graceful(self, _mock):
        # No snapshot row and the lazy populate fails -> graceful unavailable.
        r = self._client_as('zb', 'ADMIN').get('/api/wig/zazi/')
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()['available'])

    def test_mentor_forbidden(self):
        r = self._client_as('zm', 'MENTOR').get('/api/wig/zazi/')
        self.assertEqual(r.status_code, 403)


# Saturday 2026-05-30 -> last completed week is Mon 2026-05-18..Sun 2026-05-24.
DETAIL_REF = datetime(2026, 5, 30, 12, 0, tzinfo=dt_timezone.utc)


class WigDetailBuilderTests(TestCase):
    """The drill-down builders return per-metric supporting data, scoped by the
    same site-type-first cohorts as the headline measures."""

    def setUp(self):
        self.primary = School.objects.create(name='Primary A', type='Primary School', school_uid='SCH-PA')
        self.primary2 = School.objects.create(name='Primary B', type='Primary School', school_uid='SCH-PB')
        self.coach = Youth.objects.create(
            employee_id=1, first_names='Ada', last_name='Lovelace', youth_uid='YTH-1',
            job_title='Literacy Coach', school=self.primary, start_date=date(2026, 1, 1),
        )

    def _lit(self, n, day, **extra):
        extra.setdefault('youth', self.coach)
        extra.setdefault('school', self.primary)
        return LiteracySession2026.objects.create(source_airtable_id=f's{n}', session_date=day, **extra)

    def test_session_heatmap_buckets_by_week(self):
        for i in range(3):
            self._lit(f'a{i}', date(2026, 5, 20))   # last completed week (Wed)
        for i in range(2):
            self._lit(f'b{i}', date(2026, 5, 13))   # week before
        d = build_wig_detail('core_literacy', 'core_literacy.sessions_per_day', DETAIL_REF)
        self.assertEqual(d['kind'], 'session_heatmap')
        self.assertEqual(len(d['weeks']), 8)
        row = next(r for r in d['rows'] if r['youth_uid'] == 'YTH-1')
        self.assertEqual(row['weekly_counts'][-1], 3)   # most recent week
        self.assertEqual(row['weekly_counts'][-2], 2)
        self.assertEqual(row['total'], 5)

    def test_coverage_splits_covered_and_uncovered(self):
        Youth.objects.create(employee_id=2, first_names='B', last_name='B', youth_uid='YTH-2',
                             job_title='Literacy Coach', school=self.primary2, start_date=date(2026, 1, 1))
        self._lit('c1', date(2026, 5, 20))  # reaches primary A only
        d = build_wig_detail('core_literacy', 'core_literacy.school_coverage', DETAIL_REF)
        self.assertEqual(d['kind'], 'coverage')
        self.assertIn('SCH-PA', {s['school_uid'] for s in d['covered']})
        self.assertIn('SCH-PB', {s['school_uid'] for s in d['uncovered']})

    def test_visit_table_lists_observation_visits_with_flags(self):
        u = User.objects.create(username='mentor1', first_name='M', last_name='One')
        MentorVisit.objects.create(
            mentor=u, school=self.primary, visit_date=date(2026, 5, 20), visit_type='observation',
            letter_trackers_correct=True, reading_trackers_correct=True,
            sessions_correct=True, admin_correct=True,
        )
        d = build_wig_detail('core_literacy', 'core_literacy.tracker_compliance', DETAIL_REF)
        self.assertEqual(d['kind'], 'visit_table')
        self.assertEqual(len(d['visits']), 1)
        self.assertTrue(d['visits'][0]['compliant'])

    def test_dq_duplicate_records_lists_flagged_sessions(self):
        self._lit('d1', date(2026, 5, 20), duplicate_status='Duplicate')
        self._lit('d2', date(2026, 5, 20))  # clean
        d = build_wig_detail('data_team', 'dq.duplicate_rate', DETAIL_REF)
        self.assertEqual(d['kind'], 'dq_records')
        self.assertEqual(d['total_flagged'], 1)
        self.assertEqual(len(d['rows']), 1)

    def test_unknown_measure_is_kind_none(self):
        d = build_wig_detail('core_literacy', 'core_literacy.nonsense', DETAIL_REF)
        self.assertEqual(d['kind'], 'none')

    def test_rejects_mismatched_programme_and_measure(self):
        # programme says core, measure says ecd -> don't silently serve core data.
        d = build_wig_detail('core_literacy', 'ecd_literacy.school_coverage', DETAIL_REF)
        self.assertEqual(d['kind'], 'none')

    def test_child_fk_counts_unresolved_slots_not_rows(self):
        self._lit('cf', date(2026, 5, 20))  # both child slots null -> 2 unresolved slots
        d = build_wig_detail('data_team', 'dq.child_fk_resolution', DETAIL_REF)
        self.assertEqual(len(d['rows']), 1)        # one session
        self.assertEqual(d['total_flagged'], 2)    # two slots (matches the gauge)

    def test_heatmap_includes_session_bearing_non_roster_coach(self):
        former = Youth.objects.create(
            employee_id=9, first_names='Gone', last_name='Coach', youth_uid='YTH-9',
            job_title='Literacy Coach', school=self.primary,
            employment_status='Inactive', start_date=date(2026, 1, 1))
        LiteracySession2026.objects.create(
            source_airtable_id='f1', session_date=date(2026, 5, 20), youth=former, school=self.primary)
        d = build_wig_detail('core_literacy', 'core_literacy.sessions_per_day', DETAIL_REF)
        self.assertIn('YTH-9', {r['youth_uid'] for r in d['rows']})

    def test_active_coaches_drilldown_is_roster_only(self):
        # A former coach with a session reconciles session-COUNT rings, but the
        # active-coaches ring is a roster fraction, so they must not appear there.
        former = Youth.objects.create(
            employee_id=8, first_names='Left', last_name='Coach', youth_uid='YTH-8',
            job_title='Literacy Coach', school=self.primary,
            employment_status='Inactive', start_date=date(2026, 1, 1))
        LiteracySession2026.objects.create(
            source_airtable_id='ac', session_date=date(2026, 5, 20), youth=former, school=self.primary)
        active = build_wig_detail('core_literacy', 'core_literacy.active_coaches', DETAIL_REF)
        sessions = build_wig_detail('core_literacy', 'core_literacy.sessions_per_day', DETAIL_REF)
        self.assertNotIn('YTH-8', {r['youth_uid'] for r in active['rows']})
        self.assertIn('YTH-8', {r['youth_uid'] for r in sessions['rows']})

    def test_coverage_only_counts_assigned_schools(self):
        # Coach assigned to P1 (SCH-PA) teaches at unassigned P2 (SCH-PB).
        self._lit('x1', date(2026, 5, 20), school=self.primary2)
        d = build_wig_detail('core_literacy', 'core_literacy.school_coverage', DETAIL_REF)
        covered = {s['school_uid'] for s in d['covered']}
        uncovered = {s['school_uid'] for s in d['uncovered']}
        self.assertEqual(covered, set())                    # P1 assigned but not reached
        self.assertIn('SCH-PA', uncovered)
        self.assertNotIn('SCH-PB', covered | uncovered)     # reached but unassigned -> excluded

    def test_dq_requires_data_team_programme(self):
        self.assertEqual(build_wig_detail('core_literacy', 'dq.duplicate_rate', DETAIL_REF)['kind'], 'none')
        self.assertEqual(build_wig_detail('data_team', 'dq.duplicate_rate', DETAIL_REF)['kind'], 'dq_records')


class WigDetailEndpointTests(TestCase):
    """/api/wig/detail/ is role-gated and dispatches by measure key."""

    def _client_as(self, name, role):
        u = User.objects.create(username=name)
        u.profile.role = role
        u.profile.save()
        c = APIClient()
        c.force_authenticate(u)
        return c

    def test_admin_gets_dispatched_kind(self):
        r = self._client_as('da', 'ADMIN').get(
            '/api/wig/detail/?programme=core_literacy&measure=core_literacy.school_coverage')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['kind'], 'coverage')

    def test_mentor_forbidden(self):
        r = self._client_as('dm', 'MENTOR').get(
            '/api/wig/detail/?programme=core_literacy&measure=core_literacy.school_coverage')
        self.assertEqual(r.status_code, 403)
