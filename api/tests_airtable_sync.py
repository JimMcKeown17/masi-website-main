from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import Mock, call, patch

from django.test import TestCase

from api.airtable_sync import (
    IncrementalBootstrapRequired,
    advance_created_cursor,
    created_time_filter,
    fetch_airtable_records,
    prepare_created_window,
)
from api.models import AirtableSyncCursor, AirtableSyncLog


class AirtablePaginationTests(TestCase):
    @patch("api.airtable_sync.requests.get")
    def test_pagination_preserves_filter_and_selected_fields(self, mock_get):
        first = Mock(
            status_code=200,
            headers={},
            json=Mock(return_value={"records": [{"id": "rec-1"}], "offset": "next-page"}),
        )
        second = Mock(
            status_code=200,
            headers={},
            json=Mock(return_value={"records": [{"id": "rec-2"}]}),
        )
        mock_get.side_effect = [first, second]

        records = fetch_airtable_records(
            base_id="app-test",
            table_id="table-test",
            token="secret",
            filter_formula="IS_AFTER(CREATED_TIME(), '2026-08-04T10:00:00Z')",
            fields=["Session UID", "Session Date"],
        )

        self.assertEqual([record["id"] for record in records], ["rec-1", "rec-2"])
        expected_base_params = {
            "pageSize": 100,
            "filterByFormula": "IS_AFTER(CREATED_TIME(), '2026-08-04T10:00:00Z')",
            "fields[]": ["Session UID", "Session Date"],
        }
        self.assertEqual(
            mock_get.call_args_list,
            [
                call(
                    "https://api.airtable.com/v0/app-test/table-test",
                    headers={"Authorization": "Bearer secret"},
                    params=expected_base_params,
                    timeout=30,
                ),
                call(
                    "https://api.airtable.com/v0/app-test/table-test",
                    headers={"Authorization": "Bearer secret"},
                    params={**expected_base_params, "offset": "next-page"},
                    timeout=30,
                ),
            ],
        )

    @patch("api.airtable_sync.time.sleep")
    @patch("api.airtable_sync.requests.get")
    def test_transient_airtable_failure_is_retried(self, mock_get, mock_sleep):
        unavailable = Mock(status_code=503, headers={}, text="temporarily unavailable")
        success = Mock(
            status_code=200,
            headers={},
            json=Mock(return_value={"records": [{"id": "rec-recovered"}]}),
        )
        mock_get.side_effect = [unavailable, success]

        records = fetch_airtable_records(
            base_id="app-test",
            table_id="table-test",
            token="secret",
        )

        self.assertEqual(records, [{"id": "rec-recovered"}])
        self.assertEqual(mock_get.call_count, 2)
        mock_sleep.assert_called_once_with(1)


class CreatedCursorTests(TestCase):
    def test_incremental_bootstraps_from_last_successful_sync_start(self):
        started = datetime(2026, 8, 4, 10, 0, tzinfo=dt_timezone.utc)
        log = AirtableSyncLog.objects.create(sync_type="literacy_sessions_2026")
        AirtableSyncLog.objects.filter(pk=log.pk).update(
            started_at=started,
            completed_at=started + timedelta(minutes=4),
            success=True,
        )
        upper = datetime(2026, 8, 4, 11, 0, tzinfo=dt_timezone.utc)

        window = prepare_created_window(
            "literacy_sessions_2026",
            upper_bound=upper,
            overlap=timedelta(minutes=5),
        )

        self.assertEqual(window.cursor_before, started)
        self.assertEqual(window.query_after, started - timedelta(minutes=5))
        self.assertEqual(window.upper_bound, upper)
        self.assertFalse(AirtableSyncCursor.objects.exists())

    def test_incremental_requires_a_successful_full_sync_before_first_run(self):
        with self.assertRaises(IncrementalBootstrapRequired):
            prepare_created_window("literacy_sessions_2026")

    def test_cursor_advances_monotonically(self):
        older = datetime(2026, 8, 4, 10, 0, tzinfo=dt_timezone.utc)
        newer = older + timedelta(hours=1)
        AirtableSyncCursor.objects.create(
            sync_type="literacy_sessions_2026",
            created_through=newer,
        )

        advance_created_cursor("literacy_sessions_2026", older)

        cursor = AirtableSyncCursor.objects.get(sync_type="literacy_sessions_2026")
        self.assertEqual(cursor.created_through, newer)

    def test_created_time_formula_uses_utc_airtable_timestamp(self):
        value = datetime(2026, 8, 4, 10, 5, 6, tzinfo=dt_timezone.utc)
        self.assertEqual(
            created_time_filter(value),
            "IS_AFTER(CREATED_TIME(), DATETIME_PARSE('2026-08-04T10:05:06Z'))",
        )
