"""Endpoint tests for the closure calendar API (api/views/closures.py)."""
from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from api.models import School, Youth, SchoolClosure, StaffAbsence
from core.models import UserProfile


def make_user(username, role):
    user = User.objects.create_user(username=username, password='x')
    UserProfile.objects.update_or_create(user=user, defaults={'role': role})
    # Re-fetch so the reverse `profile` relation isn't a stale cached object.
    return User.objects.get(pk=user.pk)


class ClosureAuthAndScopeTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = make_user('admin', 'ADMIN')
        self.viewer = make_user('viewer', 'VIEWER')

    def test_admin_create_derives_scope_key_and_source(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post('/api/closures/',
                                {'date': '2026-06-03', 'scope_type': 'global', 'reason': 'Holiday'},
                                format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data['scope_key'], 'global')
        self.assertEqual(resp.data['source'], 'manual')

    def test_viewer_is_forbidden(self):
        self.client.force_authenticate(self.viewer)
        resp = self.client.post('/api/closures/',
                                {'date': '2026-06-03', 'scope_type': 'global'}, format='json')
        self.assertEqual(resp.status_code, 403)

    def test_school_scope_without_school_is_rejected(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.post('/api/closures/',
                                {'date': '2026-06-03', 'scope_type': 'school'}, format='json')
        self.assertEqual(resp.status_code, 400)


class ClosureBulkTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(make_user('admin', 'ADMIN'))

    def test_bulk_fans_out_weekdays_per_suburb(self):
        # Mon 2026-06-01 .. Sun 06-07 -> 5 weekdays; 2 suburbs -> 10 rows.
        resp = self.client.post('/api/closures/bulk/', {
            'date_from': '2026-06-01', 'date_to': '2026-06-07',
            'scope_type': 'region', 'scope_values': ['Walmer', 'Korsten'],
            'reason': 'Floods',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data['created'], 10)
        self.assertTrue(SchoolClosure.objects.filter(scope_key='region:WALMER').exists())

    def test_bulk_is_idempotent(self):
        body = {'date_from': '2026-06-01', 'date_to': '2026-06-05', 'scope_type': 'global'}
        self.client.post('/api/closures/bulk/', body, format='json')
        resp = self.client.post('/api/closures/bulk/', body, format='json')
        self.assertEqual(resp.data['created'], 0)
        self.assertEqual(resp.data['updated'], 5)
        self.assertEqual(SchoolClosure.objects.filter(scope_key='global').count(), 5)


@override_settings(MASI_INTERNAL_API_SECRET='test-secret')
class ClosureExportAuthTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        SchoolClosure.objects.create(date=date(2026, 6, 3), scope_type='global')

    def test_export_rejects_missing_secret(self):
        self.assertEqual(self.client.get('/api/closures/export/').status_code, 403)

    def test_export_rejects_wrong_secret(self):
        resp = self.client.get('/api/closures/export/', HTTP_X_INTERNAL_AUTH='nope')
        self.assertEqual(resp.status_code, 403)

    def test_export_accepts_right_secret(self):
        resp = self.client.get('/api/closures/export/', HTTP_X_INTERNAL_AUTH='test-secret')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]['scope_key'], 'global')

    def test_staff_crud_still_requires_user_auth(self):
        # The shared secret must not open the authoring endpoints.
        resp = self.client.get('/api/closures/', HTTP_X_INTERNAL_AUTH='test-secret')
        self.assertIn(resp.status_code, (401, 403))


class AbsenceApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(make_user('admin', 'ADMIN'))
        school = School.objects.create(name='S', type='Primary School', school_uid='SCH-S')
        self.youth = Youth.objects.create(employee_id=1, first_names='A', last_name='B',
                                         youth_uid='YTH-1', school=school,
                                         employment_status='Active', start_date=date(2026, 1, 1))

    def test_create_absence_derives_youth_uid(self):
        resp = self.client.post('/api/absences/',
                                {'date': '2026-06-02', 'youth': self.youth.id, 'reason': 'funeral'},
                                format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data['youth_uid'], 'YTH-1')

    def test_bulk_absence_fans_out_weekdays(self):
        resp = self.client.post('/api/absences/bulk/', {
            'youth_uids': ['YTH-1'], 'date_from': '2026-06-01', 'date_to': '2026-06-07',
            'reason': 'vacation',
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.data['created'], 5)
        self.assertEqual(StaffAbsence.objects.filter(youth_uid='YTH-1').count(), 5)


class ClosureLookupsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(make_user('admin', 'ADMIN'))
        School.objects.create(name='Walmer Primary', type='Primary School',
                             school_uid='SCH-W', suburb='Walmer', is_active=True)
        School.objects.create(name='Closed', type='ECDC', school_uid='SCH-I',
                             suburb='Korsten', is_active=False)
        Youth.objects.create(employee_id=7, first_names='Loyiso', last_name='Coach',
                            youth_uid='YTH-7', employment_status='Active',
                            start_date=date(2026, 1, 1))

    def test_returns_active_schools_suburbs_and_youth(self):
        resp = self.client.get('/api/closures/lookups/')
        self.assertEqual(resp.status_code, 200)
        uids = [s['school_uid'] for s in resp.data['schools']]
        self.assertIn('SCH-W', uids)
        self.assertNotIn('SCH-I', uids)  # inactive school excluded
        self.assertIn('WALMER', resp.data['suburbs'])
        self.assertEqual(resp.data['schools'][0]['canonical_type'], 'primary')
        self.assertTrue(any(y['youth_uid'] == 'YTH-7' for y in resp.data['youth']))

    def test_lookups_gated_to_admin_pm(self):
        viewer = APIClient()
        viewer.force_authenticate(make_user('viewer', 'VIEWER'))
        self.assertEqual(viewer.get('/api/closures/lookups/').status_code, 403)


@override_settings(MASI_INTERNAL_API_SECRET='test-secret')
class IdentityExportTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        School.objects.create(name='Walmer P', type='Primary School', school_uid='SCH-W',
                             suburb='Walmer', is_active=True)
        Youth.objects.create(employee_id=5, first_names='Sip', last_name='V', youth_uid='YTH-5',
                            email='Sip.V@masinyusane.org', employment_status='Active',
                            start_date=date(2026, 1, 1))

    def test_requires_secret(self):
        self.assertEqual(self.client.get('/api/identity/export/').status_code, 403)

    def test_returns_school_and_youth_identity(self):
        resp = self.client.get('/api/identity/export/', HTTP_X_INTERNAL_AUTH='test-secret')
        self.assertEqual(resp.status_code, 200)
        school = resp.data['schools'][0]
        self.assertEqual(school['school_uid'], 'SCH-W')
        self.assertEqual(school['suburb'], 'WALMER')
        self.assertEqual(school['canonical_type'], 'primary')
        youth = resp.data['youth'][0]
        self.assertEqual(youth['youth_uid'], 'YTH-5')
        self.assertEqual(youth['email'], 'sip.v@masinyusane.org')  # normalised
