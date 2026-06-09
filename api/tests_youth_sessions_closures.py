"""Youth-sessions dashboard awareness of the closure calendar (the second pass).

Heatmap tests are deterministic (explicit date_from/date_to). The inactivity test
pins 'today' so it doesn't depend on wall-clock. Window 2026-06-01..05 = Mon-Fri.
"""
from datetime import date, datetime, timezone as dt_timezone
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from api.models import School, Youth, SchoolClosure, StaffAbsence, LiteracySession2026

MON, TUE, WED, THU, FRI = (
    date(2026, 6, 1), date(2026, 6, 2), date(2026, 6, 3), date(2026, 6, 4), date(2026, 6, 5),
)


def authed_client():
    c = APIClient()
    c.force_authenticate(User.objects.create_user("u", password="x"))
    return c


class HeatmapClosureAwarenessTests(TestCase):
    def setUp(self):
        self.client = authed_client()
        self.school = School.objects.create(
            name="P", type="Primary School", school_uid="SCH-P", suburb="Walmer"
        )
        self.youth = Youth.objects.create(
            employee_id=1, first_names="Sip", last_name="V", youth_uid="YTH-1",
            job_title="Literacy Coach", school=self.school,
            employment_status="Active", start_date=date(2026, 1, 1),
        )

    def _row(self):
        resp = self.client.get(
            "/api/youth-sessions/youth-heatmap/?date_from=2026-06-01&date_to=2026-06-05"
        )
        self.assertEqual(resp.data["dates"],
                         ["2026-06-01", "2026-06-02", "2026-06-03", "2026-06-04", "2026-06-05"])
        return next(y for y in resp.data["youth"] if y["youth_uid"] == "YTH-1")

    def test_all_days_expected_without_closures(self):
        row = self._row()
        self.assertEqual(row["expected"], [True, True, True, True, True])
        self.assertEqual(row["eligible_days"], 5)

    def test_global_closure_marks_day_not_expected(self):
        SchoolClosure.objects.create(date=WED, scope_type="global")
        row = self._row()
        self.assertEqual(row["expected"], [True, True, False, True, True])
        self.assertEqual(row["eligible_days"], 4)

    def test_absence_marks_day_not_expected(self):
        StaffAbsence.objects.create(youth=self.youth, date=THU, reason="vacation")
        row = self._row()
        self.assertEqual(row["expected"], [True, True, True, False, True])
        self.assertEqual(row["eligible_days"], 4)


class InactiveClosureAwarenessTests(TestCase):
    def setUp(self):
        self.client = authed_client()
        self.school = School.objects.create(name="P", type="Primary School", school_uid="SCH-P")
        self.youth = Youth.objects.create(
            employee_id=1, first_names="Sip", last_name="V", youth_uid="YTH-1",
            job_title="Literacy Coach", school=self.school,
            employment_status="Active", start_date=date(2026, 1, 1),
        )

    def _inactive_uids(self, days=2):
        # Pin "now" to Fri 2026-06-05 so the last working days are deterministic.
        fixed = datetime(2026, 6, 5, 12, 0, tzinfo=dt_timezone.utc)
        with patch("api.views.youth_sessions.timezone.now", return_value=fixed):
            resp = self.client.get(f"/api/youth-sessions/inactive-youth/?days={days}")
        return {y["youth_uid"] for y in resp.data["inactive_youth"]}

    def test_youth_with_no_sessions_is_inactive(self):
        self.assertIn("YTH-1", self._inactive_uids())

    def test_youth_on_leave_is_not_flagged_inactive(self):
        # Worked Tue + Wed, then on leave Thu + Fri. With absence-awareness their
        # last two *expected* days are Tue/Wed (which had sessions) -> not inactive.
        # Without it, the last two weekdays (Thu/Fri) look empty -> wrongly inactive.
        for d in (TUE, WED):
            LiteracySession2026.objects.create(
                source_airtable_id=f"t-{d.isoformat()}",
                youth=self.youth, youth_uid="YTH-1", school=self.school,
                school_uid="SCH-P", session_date=d,
            )
        StaffAbsence.objects.create(youth=self.youth, date=THU, reason="vacation")
        StaffAbsence.objects.create(youth=self.youth, date=FRI, reason="vacation")
        self.assertNotIn("YTH-1", self._inactive_uids(days=2))
