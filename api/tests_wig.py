"""Tests for the WIG dashboard metric service (api/wig_metrics.py)."""
from datetime import datetime, date, timezone as dt_timezone

from django.contrib.auth.models import User, AnonymousUser
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIRequestFactory, APIClient

from api.models import School, Youth, LiteracySession2026, NumeracySession2026
from api.permissions import IsAdminOrProjectManager
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


class AssemblyTests(TestCase):
    """The endpoint payloads: a window envelope + measures keyed by source."""

    def test_lead_measures_window_and_keys(self):
        ref = datetime(2026, 5, 30, 12, 0, tzinfo=dt_timezone.utc)  # Saturday
        payload = build_lead_measures(ref)
        self.assertEqual(payload['window']['date_from'], '2026-05-18')
        self.assertEqual(payload['window']['date_to'], '2026-05-24')
        self.assertEqual(payload['window']['working_days'], 5)
        for key in ('core_literacy.sessions_per_day', 'ecd_literacy.sessions_per_day',
                    'numeracy.sessions_per_week', 'core_literacy.school_coverage'):
            self.assertIn(key, payload['measures'])

    def test_data_quality_has_sub_gauges(self):
        dq = build_data_quality()
        self.assertEqual(dq['scope'], 'full_dataset')
        for key in ('dq.capture_on_time', 'dq.duplicate_rate', 'dq.site_job_mismatch'):
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
