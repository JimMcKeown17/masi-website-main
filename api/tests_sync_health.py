from datetime import datetime, timedelta, timezone as dt_timezone

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from api.models import AirtableSyncLog


LITERACY = "literacy_sessions_2026"
NUMERACY = "numeracy_sessions_2026"


def create_log(sync_type, *, started_at, completed_at, success, error_message=None):
    log = AirtableSyncLog.objects.create(
        sync_type=sync_type,
        completed_at=completed_at,
        success=success,
        error_message=error_message,
    )
    AirtableSyncLog.objects.filter(pk=log.pk).update(started_at=started_at)
    return AirtableSyncLog.objects.get(pk=log.pk)


@override_settings(
    YOUTH_SESSIONS_SYNC_CADENCE_MINUTES=15,
    YOUTH_SESSIONS_STALE_AFTER_MINUTES=30,
)
class YouthSessionFreshnessTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(User.objects.create_user("freshness-user"))
        self.now = datetime(2026, 8, 4, 12, 0, tzinfo=dt_timezone.utc)

    def get_freshness(self):
        from unittest.mock import patch

        with patch("api.sync_health.timezone.now", return_value=self.now):
            return self.client.get("/api/youth-sessions/freshness/")

    def test_reports_fresh_when_both_feeds_succeeded_within_threshold(self):
        create_log(
            LITERACY,
            started_at=self.now - timedelta(minutes=8),
            completed_at=self.now - timedelta(minutes=6),
            success=True,
        )
        create_log(
            NUMERACY,
            started_at=self.now - timedelta(minutes=7),
            completed_at=self.now - timedelta(minutes=5),
            success=True,
        )

        response = self.get_freshness()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "fresh")
        self.assertFalse(response.data["is_stale"])
        self.assertEqual(
            response.data["last_successful_sync"],
            (self.now - timedelta(minutes=6)).isoformat().replace("+00:00", "Z"),
        )
        self.assertIn("literacy", response.data["sources"])
        self.assertIn("numeracy", response.data["sources"])

    def test_reports_stale_when_a_feed_is_older_than_promised_threshold(self):
        for sync_type in (LITERACY, NUMERACY):
            create_log(
                sync_type,
                started_at=self.now - timedelta(minutes=45),
                completed_at=self.now - timedelta(minutes=40),
                success=True,
            )

        response = self.get_freshness()

        self.assertEqual(response.data["status"], "stale")
        self.assertTrue(response.data["is_stale"])

    def test_newer_failed_attempt_overrides_an_older_success(self):
        for sync_type in (LITERACY, NUMERACY):
            create_log(
                sync_type,
                started_at=self.now - timedelta(minutes=20),
                completed_at=self.now - timedelta(minutes=18),
                success=True,
            )
        create_log(
            LITERACY,
            started_at=self.now - timedelta(minutes=4),
            completed_at=self.now - timedelta(minutes=3),
            success=False,
            error_message="Airtable unavailable",
        )

        response = self.get_freshness()

        self.assertEqual(response.data["status"], "failed")
        self.assertTrue(response.data["is_stale"])
        self.assertEqual(response.data["sources"]["literacy"]["status"], "failed")
        self.assertEqual(
            response.data["sources"]["literacy"]["error_message"],
            "Airtable unavailable",
        )

    def test_active_attempt_is_syncing_not_failed(self):
        for sync_type in (LITERACY, NUMERACY):
            create_log(
                sync_type,
                started_at=self.now - timedelta(minutes=20),
                completed_at=self.now - timedelta(minutes=18),
                success=True,
            )
        create_log(
            LITERACY,
            started_at=self.now - timedelta(minutes=1),
            completed_at=None,
            success=False,
        )

        response = self.get_freshness()

        self.assertEqual(response.data["status"], "syncing")
        self.assertFalse(response.data["is_stale"])

    def test_missing_feed_fails_closed_as_never_synced(self):
        create_log(
            LITERACY,
            started_at=self.now - timedelta(minutes=5),
            completed_at=self.now - timedelta(minutes=4),
            success=True,
        )

        response = self.get_freshness()

        self.assertEqual(response.data["status"], "never")
        self.assertTrue(response.data["is_stale"])
        self.assertIsNone(response.data["last_successful_sync"])

    def test_endpoint_requires_authentication(self):
        client = APIClient()
        response = client.get("/api/youth-sessions/freshness/")
        self.assertIn(response.status_code, (401, 403))
