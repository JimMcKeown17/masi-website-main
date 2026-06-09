"""Tests for the working-days resolution service (api/closures.py) and the
SchoolClosure uniqueness contract.

Calendar anchor: 2026-06-01 is a Monday, so 06-01..06-05 are Mon-Fri and
06-06/06-07 are the weekend.
"""
from datetime import date

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase

from api.models import School, Youth, SchoolClosure, StaffAbsence
from api import closures
from api.wig_metrics import sessions_per_day

MON = date(2026, 6, 1)
TUE = date(2026, 6, 2)
WED = date(2026, 6, 3)
THU = date(2026, 6, 4)
FRI = date(2026, 6, 5)
SAT = date(2026, 6, 6)
SUN = date(2026, 6, 7)
WEEK = (MON, SUN)


def mk_closure(day, scope_type, *, school=None, canonical_type=None, region=None,
               is_open=False, source='manual'):
    return SchoolClosure.objects.create(
        date=day,
        scope_key=closures.build_scope_key(
            scope_type, school_uid=getattr(school, 'school_uid', None),
            canonical_type=canonical_type, region=region,
        ),
        scope_type=scope_type,
        scope_school=school,
        scope_school_type=canonical_type,
        scope_region=closures.normalize_region(region) if region else None,
        is_open=is_open,
        source=source,
    )


class HelperTests(SimpleTestCase):
    def test_canonical_school_type(self):
        self.assertEqual(closures.canonical_school_type('ECDC'), 'ecd')
        self.assertEqual(closures.canonical_school_type('Primary School'), 'primary')
        self.assertEqual(closures.canonical_school_type('Secondary School'), 'secondary')
        self.assertEqual(closures.canonical_school_type('Other'), 'other')
        self.assertEqual(closures.canonical_school_type(None), 'other')

    def test_normalize_region_collapses_and_uppercases(self):
        self.assertEqual(closures.normalize_region('  Walmer  '), 'WALMER')
        self.assertEqual(closures.normalize_region('new   brighton'), 'NEW BRIGHTON')
        self.assertEqual(closures.normalize_region(None), '')

    def test_build_scope_key(self):
        self.assertEqual(closures.build_scope_key('global'), 'global')
        self.assertEqual(closures.build_scope_key('type', canonical_type='primary'), 'type:primary')
        self.assertEqual(closures.build_scope_key('region', region=' Walmer '), 'region:WALMER')
        self.assertEqual(closures.build_scope_key('school', school_uid='SCH-1'), 'school:SCH-1')


class ResolutionTests(TestCase):
    def setUp(self):
        self.primary = School.objects.create(name='Primary A', type='Primary School',
                                             school_uid='SCH-PA', suburb='Walmer')
        self.ecdc = School.objects.create(name='ECDC B', type='ECDC',
                                         school_uid='SCH-EB', suburb='New Brighton')

    def days(self, school, **kw):
        return closures.open_working_days(school, MON, SUN, **kw)

    def test_no_closures_returns_weekdays_only(self):
        self.assertEqual(self.days(self.primary), [MON, TUE, WED, THU, FRI])

    def test_global_closure_excludes_that_day_for_all(self):
        mk_closure(WED, 'global')
        self.assertEqual(self.days(self.primary), [MON, TUE, THU, FRI])
        self.assertEqual(self.days(self.ecdc), [MON, TUE, THU, FRI])

    def test_type_closure_only_hits_matching_type(self):
        mk_closure(TUE, 'type', canonical_type='primary')
        self.assertEqual(self.days(self.primary), [MON, WED, THU, FRI])
        self.assertEqual(self.days(self.ecdc), [MON, TUE, WED, THU, FRI])

    def test_region_closure_only_hits_matching_suburb(self):
        mk_closure(THU, 'region', region='Walmer')
        self.assertEqual(self.days(self.primary), [MON, TUE, WED, FRI])  # Walmer
        self.assertEqual(self.days(self.ecdc), [MON, TUE, WED, THU, FRI])  # New Brighton

    def test_school_closure_only_hits_that_school(self):
        mk_closure(MON, 'school', school=self.primary)
        self.assertEqual(self.days(self.primary), [TUE, WED, THU, FRI])
        self.assertEqual(self.days(self.ecdc), [MON, TUE, WED, THU, FRI])

    def test_school_open_override_beats_global_closure(self):
        mk_closure(WED, 'global')                                   # everyone closed Wed
        mk_closure(WED, 'school', school=self.primary, is_open=True)  # except Primary A
        self.assertEqual(self.days(self.primary), [MON, TUE, WED, THU, FRI])
        self.assertEqual(self.days(self.ecdc), [MON, TUE, THU, FRI])

    def test_public_holiday_is_a_global_row_and_is_overridable(self):
        mk_closure(THU, 'global', source='public_holiday', is_open=False)
        self.assertTrue(closures.is_closed(self.primary, THU))
        mk_closure(THU, 'school', school=self.ecdc, is_open=True)
        self.assertFalse(closures.is_closed(self.ecdc, THU))
        self.assertTrue(closures.is_closed(self.primary, THU))


class ClipAndAbsenceTests(TestCase):
    def setUp(self):
        self.school = School.objects.create(name='S', type='Primary School',
                                           school_uid='SCH-S', suburb='Walmer')
        self.youth = Youth.objects.create(employee_id=1, first_names='F', last_name='One',
                                         youth_uid='YTH-1', school=self.school,
                                         employment_status='Active', start_date=date(2026, 1, 1))

    def test_since_clips_days_before_start(self):
        got = closures.open_working_days(self.school, MON, SUN, since=WED)
        self.assertEqual(got, [WED, THU, FRI])

    def test_youth_absence_subtracts_that_youth_days(self):
        StaffAbsence.objects.create(youth=self.youth, date=TUE, reason='funeral')
        got = closures.open_working_days(self.school, MON, SUN, youth=self.youth)
        self.assertEqual(got, [MON, WED, THU, FRI])

    def test_bulk_matches_per_coach_resolution(self):
        other_school = School.objects.create(name='O', type='ECDC', school_uid='SCH-O', suburb='Korsten')
        coach_b = Youth.objects.create(employee_id=2, first_names='G', last_name='Two',
                                      youth_uid='YTH-2', school=other_school,
                                      employment_status='Active', start_date=date(2026, 1, 1))
        mk_closure(WED, 'global')
        StaffAbsence.objects.create(youth=self.youth, date=MON, reason='sick')

        result = closures.open_working_days_bulk([self.youth, coach_b], MON, SUN)

        self.assertEqual(result[self.youth.id], {TUE, THU, FRI})        # minus Wed (global) minus Mon (absent)
        self.assertEqual(result[coach_b.id], {MON, TUE, THU, FRI})      # minus Wed (global) only


class ClosureConstraintTests(TestCase):
    """[R1] scope_key must dedupe on Postgres where a nullable composite key would not."""

    def test_duplicate_global_closure_same_date_is_rejected(self):
        mk_closure(WED, 'global')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                mk_closure(WED, 'global')


class LoadPublicHolidaysCommandTests(TestCase):
    FREEDOM_DAY = date(2026, 4, 27)

    def test_creates_global_public_holiday_rows(self):
        call_command('load_public_holidays', year=2026)
        freedom = SchoolClosure.objects.get(date=self.FREEDOM_DAY)
        self.assertEqual(freedom.scope_key, 'global')
        self.assertEqual(freedom.source, 'public_holiday')
        self.assertFalse(freedom.is_open)
        self.assertGreaterEqual(SchoolClosure.objects.filter(source='public_holiday').count(), 10)

    def test_is_idempotent(self):
        call_command('load_public_holidays', year=2026)
        n1 = SchoolClosure.objects.filter(source='public_holiday').count()
        call_command('load_public_holidays', year=2026)
        n2 = SchoolClosure.objects.filter(source='public_holiday').count()
        self.assertEqual(n1, n2)

    def test_does_not_clobber_manual_global_closure(self):
        manual = SchoolClosure.objects.create(
            date=self.FREEDOM_DAY, scope_key='global', scope_type='global',
            source='manual', reason='Manual reason',
        )
        call_command('load_public_holidays', year=2026)
        manual.refresh_from_db()
        self.assertEqual(manual.source, 'manual')
        self.assertEqual(manual.reason, 'Manual reason')


class ScopeIntegrityTests(TestCase):
    """[finding 3] scope_key is derived from the scope fields, never hand-set,
    and required scope fields are validated."""

    def setUp(self):
        self.school = School.objects.create(name='X', type='Primary School',
                                            school_uid='SCH-X', suburb='Walmer')

    def test_save_derives_scope_key_ignoring_passed_value(self):
        c = SchoolClosure(date=MON, scope_type='school', scope_school=self.school,
                          scope_key='global')  # deliberately wrong
        c.save()
        self.assertEqual(c.scope_key, 'school:SCH-X')

    def test_save_clears_descriptive_fields_for_broader_scope(self):
        c = SchoolClosure(date=MON, scope_type='global', scope_school=self.school,
                          scope_school_type='primary', scope_region='Walmer')
        c.save()
        self.assertEqual(c.scope_key, 'global')
        self.assertIsNone(c.scope_school_id)
        self.assertIsNone(c.scope_school_type)
        self.assertIsNone(c.scope_region)

    def test_clean_requires_school_for_school_scope(self):
        with self.assertRaises(ValidationError):
            SchoolClosure(date=MON, scope_type='school').full_clean()

    def test_clean_requires_type_for_type_scope(self):
        with self.assertRaises(ValidationError):
            SchoolClosure(date=MON, scope_type='type').full_clean()

    def test_clean_requires_region_for_region_scope(self):
        with self.assertRaises(ValidationError):
            SchoolClosure(date=MON, scope_type='region', scope_region='   ').full_clean()


class AbsenceSurvivesYouthDeletionTests(TestCase):
    """[finding 1] The nightly youth sync hard-deletes orphan Youth rows; absence
    history must survive (FK SET_NULL, keyed by youth_uid)."""

    def test_absence_kept_when_youth_deleted(self):
        school = School.objects.create(name='S', type='Primary School', school_uid='SCH-S')
        youth = Youth.objects.create(employee_id=9, first_names='A', last_name='B',
                                    youth_uid='YTH-9', school=school,
                                    employment_status='Active', start_date=date(2026, 1, 1))
        StaffAbsence.objects.create(youth=youth, date=TUE, reason='vacation')

        youth.delete()  # simulates sync_airtable_youth orphan delete

        absence = StaffAbsence.objects.get(date=TUE)
        self.assertIsNone(absence.youth_id)
        self.assertEqual(absence.youth_uid, 'YTH-9')


class DenominatorIntegrationTests(TestCase):
    """[finding 2] Closures and absences must actually move the WIG
    sessions_per_day denominator (expected coach-days), not just sit in a table.
    Window 2026-05-18..24 = Mon-Sun, 5 working days."""

    START = date(2026, 5, 18)  # Monday
    END = date(2026, 5, 24)    # Sunday
    WED = date(2026, 5, 20)
    THU = date(2026, 5, 21)

    def setUp(self):
        self.primary = School.objects.create(name='P', type='Primary School',
                                             school_uid='SCH-P', suburb='Walmer')
        self.a = Youth.objects.create(employee_id=101, first_names='A', last_name='A',
                                     youth_uid='YTH-101', job_title='Literacy Coach',
                                     school=self.primary, employment_status='Active',
                                     start_date=date(2026, 1, 1))
        self.b = Youth.objects.create(employee_id=102, first_names='B', last_name='B',
                                     youth_uid='YTH-102', job_title='Literacy Coach',
                                     school=self.primary, employment_status='Active',
                                     start_date=date(2026, 1, 1))

    def test_baseline_denominator_is_coaches_times_working_days(self):
        m = sessions_per_day('core_literacy', self.START, self.END)
        self.assertEqual(m['denominator'], 10)  # 2 coaches x 5 working days

    def test_global_closure_reduces_denominator_for_all_coaches(self):
        SchoolClosure.objects.create(date=self.WED, scope_type='global')
        m = sessions_per_day('core_literacy', self.START, self.END)
        self.assertEqual(m['denominator'], 8)  # 2 coaches x 4 open days

    def test_staff_absence_reduces_only_that_coach(self):
        StaffAbsence.objects.create(youth=self.a, date=self.THU, reason='funeral')
        m = sessions_per_day('core_literacy', self.START, self.END)
        self.assertEqual(m['denominator'], 9)  # A:4 + B:5
