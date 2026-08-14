from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from api.models import (
    AirtableSyncCursor,
    AirtableSyncLog,
    LiteracySession2026,
    NumeracySession2026,
)


class IncrementalSessionCommandTests(TestCase):
    now = datetime(2026, 8, 4, 12, 0, tzinfo=dt_timezone.utc)

    def _run_incremental(self, command_name, module_name, env, record):
        sync_type = env["sync_type"]
        AirtableSyncCursor.objects.create(
            sync_type=sync_type,
            created_through=self.now - timedelta(minutes=15),
        )
        environment = {
            env["base_key"]: "app-test",
            env["table_key"]: "table-test",
            "AIRTABLE_TOKEN": "secret",
        }
        with (
            patch.dict("os.environ", environment, clear=False),
            patch(f"{module_name}.timezone.now", return_value=self.now),
            patch(f"{module_name}.fetch_airtable_records", return_value=[record]) as fetch,
        ):
            call_command(command_name, incremental_new=True)
        return fetch

    def test_incremental_literacy_sync_inserts_new_record_and_advances_cursor(self):
        sync_type = "literacy_sessions_2026"
        fetch = self._run_incremental(
            "sync_airtable_literacy_sessions_2026",
            "api.management.commands.sync_airtable_literacy_sessions_2026",
            {
                "sync_type": sync_type,
                "base_key": "AIRTABLE_LITERACY_2026_BASE_ID",
                "table_key": "AIRTABLE_LITERACY_2026_TABLE_ID",
            },
            {
                "id": "rec-literacy-new",
                "createdTime": "2026-08-04T11:58:00.000Z",
                "fields": {"Session Date": "2026-08-04", "Session UID": "SES-L-1"},
            },
        )

        self.assertTrue(LiteracySession2026.objects.filter(source_airtable_id="rec-literacy-new").exists())
        self.assertEqual(AirtableSyncCursor.objects.get(sync_type=sync_type).created_through, self.now)
        self.assertIn("CREATED_TIME()", fetch.call_args.kwargs["filter_formula"])
        log = AirtableSyncLog.objects.filter(sync_type=sync_type).latest("started_at")
        self.assertTrue(log.success)
        self.assertEqual(log.details["mode"], "incremental_new")

    def test_full_sync_bootstraps_cursor_and_remains_idempotent(self):
        sync_type = "literacy_sessions_2026"
        environment = {
            "AIRTABLE_LITERACY_2026_BASE_ID": "app-test",
            "AIRTABLE_LITERACY_2026_TABLE_ID": "table-test",
            "AIRTABLE_TOKEN": "secret",
        }
        module = "api.management.commands.sync_airtable_literacy_sessions_2026"
        record = {
            "id": "rec-full",
            "createdTime": "2026-08-04T11:58:00.000Z",
            "fields": {"Session Date": "2026-08-04", "Session UID": "SES-FULL"},
        }

        with (
            patch.dict("os.environ", environment, clear=False),
            patch(f"{module}.timezone.now", return_value=self.now),
            patch(f"{module}.fetch_airtable_records", return_value=[record]),
        ):
            call_command("sync_airtable_literacy_sessions_2026")
            call_command("sync_airtable_literacy_sessions_2026")

        self.assertEqual(
            LiteracySession2026.objects.filter(source_airtable_id="rec-full").count(),
            1,
        )
        logs = AirtableSyncLog.objects.filter(sync_type=sync_type).order_by("started_at")
        self.assertEqual(logs.count(), 2)
        self.assertEqual(logs[0].records_created, 1)
        self.assertEqual(logs[1].records_updated, 1)
        self.assertEqual(logs[1].details["mode"], "full")
        self.assertEqual(
            AirtableSyncCursor.objects.get(sync_type=sync_type).created_through,
            logs[1].started_at,
        )

    def test_incremental_numeracy_sync_inserts_new_record_and_advances_cursor(self):
        sync_type = "numeracy_sessions_2026"
        fetch = self._run_incremental(
            "sync_airtable_numeracy_sessions_2026",
            "api.management.commands.sync_airtable_numeracy_sessions_2026",
            {
                "sync_type": sync_type,
                "base_key": "AIRTABLE_NUMERACY_2026_BASE_ID",
                "table_key": "AIRTABLE_NUMERACY_2026_TABLE_ID",
            },
            {
                "id": "rec-numeracy-new",
                "createdTime": "2026-08-04T11:58:00.000Z",
                "fields": {"Session Date": "2026-08-04", "Session UID": "SES-N-1"},
            },
        )

        self.assertTrue(NumeracySession2026.objects.filter(source_airtable_id="rec-numeracy-new").exists())
        self.assertEqual(AirtableSyncCursor.objects.get(sync_type=sync_type).created_through, self.now)
        self.assertIn("CREATED_TIME()", fetch.call_args.kwargs["filter_formula"])

    def test_failed_database_write_does_not_advance_cursor(self):
        sync_type = "literacy_sessions_2026"
        old_cursor = self.now - timedelta(minutes=15)
        AirtableSyncCursor.objects.create(sync_type=sync_type, created_through=old_cursor)
        environment = {
            "AIRTABLE_LITERACY_2026_BASE_ID": "app-test",
            "AIRTABLE_LITERACY_2026_TABLE_ID": "table-test",
            "AIRTABLE_TOKEN": "secret",
        }
        module = "api.management.commands.sync_airtable_literacy_sessions_2026"

        with (
            patch.dict("os.environ", environment, clear=False),
            patch(f"{module}.timezone.now", return_value=self.now),
            patch(f"{module}.fetch_airtable_records", return_value=[]),
            patch(f"{module}.Command.bulk_upsert", side_effect=RuntimeError("database unavailable")),
            self.assertRaisesMessage(RuntimeError, "database unavailable"),
        ):
            call_command("sync_airtable_literacy_sessions_2026", incremental_new=True)

        self.assertEqual(AirtableSyncCursor.objects.get(sync_type=sync_type).created_through, old_cursor)
        log = AirtableSyncLog.objects.filter(sync_type=sync_type).latest("started_at")
        self.assertFalse(log.success)
        self.assertEqual(log.error_message, "database unavailable")
