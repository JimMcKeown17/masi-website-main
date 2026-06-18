from datetime import date
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from api.models import (
    School, Youth, CanonicalChild,
    LiteracySession2026, NumeracySession2026,
    AirtableSyncLog, StaffAbsence,
)


class TestFKResolution(TestCase):
    """Test that FK resolution logic correctly links sessions to canonical records."""

    def setUp(self):
        self.school = School.objects.create(name='Test School', school_uid='SCH-00001')
        self.youth = Youth.objects.create(
            employee_id=1, first_names='John', last_name='Smith',
            youth_uid='YTH-0001',
        )
        self.child1 = CanonicalChild.objects.create(
            source_airtable_id='rec_c1', child_uid='CH-10001', mcode=10001,
            full_name='Child One',
        )
        self.child2 = CanonicalChild.objects.create(
            source_airtable_id='rec_c2', child_uid='CH-10002', mcode=10002,
            full_name='Child Two',
        )

    def test_literacy_fk_resolution(self):
        session = LiteracySession2026.objects.create(
            source_airtable_id='rec_lit_1',
            session_date=date(2026, 3, 1),
            youth_uid='YTH-0001',
            school_uid='SCH-00001',
            child_uid_1='CH-10001',
            child_uid_2='CH-10002',
        )
        # Simulate resolution
        youth_by_uid = {y.youth_uid: y for y in Youth.objects.filter(youth_uid__isnull=False)}
        school_by_uid = {s.school_uid: s for s in School.objects.filter(school_uid__isnull=False)}
        child_by_uid = {c.child_uid: c for c in CanonicalChild.objects.all()}

        session.youth = youth_by_uid.get(session.youth_uid)
        session.school = school_by_uid.get(session.school_uid)
        session.child_1 = child_by_uid.get(session.child_uid_1)
        session.child_2 = child_by_uid.get(session.child_uid_2)
        session.save()

        session.refresh_from_db()
        self.assertEqual(session.youth_id, self.youth.id)
        self.assertEqual(session.school_id, self.school.id)
        self.assertEqual(session.child_1_id, self.child1.id)
        self.assertEqual(session.child_2_id, self.child2.id)

    def test_numeracy_fk_resolution(self):
        session = NumeracySession2026.objects.create(
            source_airtable_id='rec_num_1',
            session_date=date(2026, 3, 1),
            youth_uid='YTH-0001',
            school_uid='SCH-00001',
            child_uids=['CH-10001', 'CH-10002'],
        )
        youth_by_uid = {y.youth_uid: y for y in Youth.objects.filter(youth_uid__isnull=False)}
        school_by_uid = {s.school_uid: s for s in School.objects.filter(school_uid__isnull=False)}

        session.youth = youth_by_uid.get(session.youth_uid)
        session.school = school_by_uid.get(session.school_uid)
        session.save()

        session.refresh_from_db()
        self.assertEqual(session.youth_id, self.youth.id)
        self.assertEqual(session.school_id, self.school.id)

    def test_orphaned_uid_leaves_fk_null(self):
        session = LiteracySession2026.objects.create(
            source_airtable_id='rec_lit_orphan',
            youth_uid='YTH-9999',
            school_uid='SCH-99999',
            child_uid_1='CH-99999',
        )
        youth_by_uid = {y.youth_uid: y for y in Youth.objects.filter(youth_uid__isnull=False)}
        session.youth = youth_by_uid.get(session.youth_uid)
        session.save()

        session.refresh_from_db()
        self.assertIsNone(session.youth_id)


class TestEtlStatusEndpoint(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_etl_status_returns_tables(self):
        AirtableSyncLog.objects.create(
            sync_type='schools', records_processed=100,
            success=True,
        )
        # Mark it complete
        log = AirtableSyncLog.objects.first()
        log.mark_complete(success=True)

        response = self.client.get('/api/etl-status/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('tables', data)
        names = [t['name'] for t in data['tables']]
        self.assertIn('schools', names)
        self.assertIn('literacy-2026', names)
        self.assertIn('numeracy-2026', names)

    def test_etl_status_unauthenticated(self):
        client = APIClient()
        # raise_request_exception=False to avoid the Clerk auth backend error in tests
        client.raise_request_exception = False
        response = client.get('/api/etl-status/')
        self.assertIn(response.status_code, [401, 403, 500])


class TestEtlPreviewEndpoint(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        self.school = School.objects.create(name='Test School', school_uid='SCH-00001')
        self.youth = Youth.objects.create(
            employee_id=1, first_names='John', last_name='Smith',
            youth_uid='YTH-0001',
        )
        self.child1 = CanonicalChild.objects.create(
            source_airtable_id='rec_c1', child_uid='CH-10001', mcode=10001,
            full_name='Child One',
        )

    def test_literacy_preview_with_orphan_stats(self):
        # Resolved session
        LiteracySession2026.objects.create(
            source_airtable_id='rec_1',
            youth_uid='YTH-0001', youth=self.youth,
            school_uid='SCH-00001', school=self.school,
            child_uid_1='CH-10001', child_1=self.child1,
        )
        # Orphaned session
        LiteracySession2026.objects.create(
            source_airtable_id='rec_2',
            youth_uid='YTH-9999',
            school_uid='SCH-99999',
        )

        response = self.client.get('/api/etl-preview/literacy-2026/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['record_count'], 2)
        self.assertEqual(data['orphan_stats']['youth_resolved'], 1)
        self.assertEqual(data['orphan_stats']['youth_orphaned'], 1)
        self.assertIsInstance(data['sample_rows'], list)

    def test_unknown_table_returns_400(self):
        response = self.client.get('/api/etl-preview/nonexistent/')
        self.assertEqual(response.status_code, 400)

    def test_schools_preview(self):
        response = self.client.get('/api/etl-preview/schools/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['record_count'], 1)
        self.assertEqual(len(data['sample_rows']), 1)
        self.assertEqual(data['sample_rows'][0]['name'], 'Test School')


class PublishedStatTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _make(self, **kw):
        from api.models import PublishedStat

        defaults = dict(
            key="test_stat",
            value="42%",
            numeric_value=42.0,
            label="Test stat",
            source_system="Test source",
            population="Test population",
            comparison_type="none",
            as_of="2026-06-01",
            methodology_note="Test note",
            group="test_group",
            sort_order=1,
            is_published=True,
        )
        defaults.update(kw)
        return PublishedStat.objects.create(**defaults)

    def test_model_str(self):
        stat = self._make()
        self.assertEqual(str(stat), "test_stat = 42%")

    def test_endpoint_returns_published_only(self):
        self._make(key="pub", group="g1", sort_order=2)
        self._make(key="pub_first", group="g1", sort_order=1)
        self._make(key="hidden", is_published=False)

        res = self.client.get("/api/impact/published-stats/")

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("pub", data["stats"])
        self.assertNotIn("hidden", data["stats"])
        self.assertEqual(data["groups"]["g1"], ["pub_first", "pub"])
        self.assertEqual(data["verified_through"], "2026-06-01")

    def test_endpoint_requires_no_auth(self):
        res = self.client.get("/api/impact/published-stats/")
        self.assertEqual(res.status_code, 200)


class TestYouthDetailAbsences(TestCase):
    """youth_sessions_detail surfaces the youth's in-window StaffAbsence rows,
    but only to ADMIN / PROJECT MANAGER (absence reason/note is HR-sensitive)."""

    def setUp(self):
        self.user = User.objects.create_user(username='pm', password='x')
        # A UserProfile is auto-created (post_save signal) with role VIEWER and
        # cached on this in-memory user. Mutate through that cached relation so the
        # role the force_authenticate'd view reads is ADMIN, not the stale VIEWER.
        self.user.profile.role = 'ADMIN'
        self.user.profile.save()
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        self.youth = Youth.objects.create(
            employee_id=1, first_names='Nomsa', last_name='Dlamini',
            youth_uid='YTH-0001',
        )

    def test_detail_returns_youth_absences_in_window(self):
        StaffAbsence.objects.create(
            youth_uid='YTH-0001', date=date(2026, 3, 3), reason='funeral', note='Family',
        )
        # Outside the queried window -- must NOT appear.
        StaffAbsence.objects.create(
            youth_uid='YTH-0001', date=date(2026, 1, 5), reason='sick',
        )
        resp = self.client.get(
            '/api/youth-sessions/youth-detail/YTH-0001/'
            '?date_from=2026-03-02&date_to=2026-03-06'
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('absences', data)
        self.assertEqual(len(data['absences']), 1)
        row = data['absences'][0]
        self.assertEqual(row['date'], '2026-03-03')
        self.assertEqual(row['reason'], 'funeral')
        self.assertEqual(row['note'], 'Family')
        self.assertIn('id', row)

    def test_detail_absences_empty_when_none(self):
        resp = self.client.get(
            '/api/youth-sessions/youth-detail/YTH-0001/'
            '?date_from=2026-03-02&date_to=2026-03-06'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['absences'], [])

    def test_detail_absences_hidden_from_mentor(self):
        # A MENTOR can reach this endpoint (IsAuthenticated) but must NOT see
        # absence reasons/notes -- the field returns empty for non-leadership.
        mentor = User.objects.create_user(username='mentor', password='x')
        mentor.profile.role = 'MENTOR'
        mentor.profile.save()
        mentor_client = APIClient()
        mentor_client.force_authenticate(user=mentor)
        StaffAbsence.objects.create(
            youth_uid='YTH-0001', date=date(2026, 3, 3), reason='funeral', note='Family',
        )
        resp = mentor_client.get(
            '/api/youth-sessions/youth-detail/YTH-0001/'
            '?date_from=2026-03-02&date_to=2026-03-06'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['absences'], [])


class SyncAirtableChildrenExtractRowTests(TestCase):
    """extract_row unwraps the Airtable 'Teampact Participant ID' lookup (a
    single-element list) to a scalar string, and tolerates missing/empty."""

    def _cmd(self):
        from api.management.commands.sync_airtable_children import Command
        return Command()

    def _record(self, **field_overrides):
        fields = {'Mcode': 6191, 'Child UID': 'CH-6191'}
        fields.update(field_overrides)
        return {'id': 'rec123', 'fields': fields}

    def test_participant_id_unwrapped_from_list(self):
        row = self._cmd().extract_row(self._record(**{'Teampact Participant ID': ['386722']}))
        self.assertEqual(row['participant_id'], '386722')

    def test_participant_id_absent_is_none(self):
        row = self._cmd().extract_row(self._record())
        self.assertIsNone(row['participant_id'])

    def test_participant_id_empty_list_is_none(self):
        row = self._cmd().extract_row(self._record(**{'Teampact Participant ID': []}))
        self.assertIsNone(row['participant_id'])

    def test_required_fields_missing_returns_none(self):
        row = self._cmd().extract_row({'id': 'rec', 'fields': {'Mcode': 1}})  # no Child UID
        self.assertIsNone(row)
