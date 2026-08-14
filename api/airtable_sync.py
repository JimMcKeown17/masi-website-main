"""Shared reliability primitives for Airtable ingestion commands."""

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as dt_timezone
import hashlib
import time

import requests
from django.db import connection, transaction
from django.utils import timezone

from api.models import AirtableSyncCursor, AirtableSyncLog


DEFAULT_CURSOR_OVERLAP = timedelta(minutes=5)
DEFAULT_REQUEST_TIMEOUT_SECONDS = 30
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class AirtableRequestError(RuntimeError):
    pass


class IncrementalBootstrapRequired(RuntimeError):
    pass


@dataclass(frozen=True)
class CreatedSyncWindow:
    cursor_before: datetime
    query_after: datetime
    upper_bound: datetime


def prepare_created_window(
    sync_type,
    *,
    upper_bound=None,
    overlap=DEFAULT_CURSOR_OVERLAP,
):
    """Return the bounded window for a new-record incremental pass.

    A newly deployed cursor bootstraps from the *start* of the most recent
    successful full sync. A record created while that full scan was running may
    not have appeared in its paginated snapshot, so using the start time plus a
    small overlap closes that race safely. Upserts make overlap replays harmless.
    """

    upper_bound = upper_bound or timezone.now()
    cursor = AirtableSyncCursor.objects.filter(sync_type=sync_type).first()
    cursor_before = cursor.created_through if cursor else None

    if cursor_before is None:
        latest_success = (
            AirtableSyncLog.objects.filter(sync_type=sync_type, success=True)
            .exclude(completed_at__isnull=True)
            .order_by("-started_at")
            .first()
        )
        cursor_before = latest_success.started_at if latest_success else None

    if cursor_before is None:
        raise IncrementalBootstrapRequired(
            f"{sync_type} has no successful full sync to bootstrap its incremental cursor"
        )

    return CreatedSyncWindow(
        cursor_before=cursor_before,
        query_after=cursor_before - overlap,
        upper_bound=upper_bound,
    )


def advance_created_cursor(sync_type, created_through):
    """Advance a cursor without ever allowing it to move backwards."""

    with transaction.atomic():
        cursor, _ = AirtableSyncCursor.objects.select_for_update().get_or_create(
            sync_type=sync_type
        )
        if cursor.created_through is None or created_through > cursor.created_through:
            cursor.created_through = created_through
            cursor.save(update_fields=["created_through", "updated_at"])
        return cursor


def created_time_filter(after):
    """Build an Airtable formula against immutable record creation time."""

    utc_value = after.astimezone(dt_timezone.utc).replace(microsecond=0)
    timestamp = utc_value.isoformat().replace("+00:00", "Z")
    return f"IS_AFTER(CREATED_TIME(), DATETIME_PARSE('{timestamp}'))"


def _retry_delay(response, attempt):
    retry_after = response.headers.get("Retry-After") if response.headers else None
    if retry_after:
        try:
            return min(float(retry_after), 60.0)
        except (TypeError, ValueError):
            pass
    return min(2 ** attempt, 30)


def fetch_airtable_records(
    *,
    base_id,
    table_id,
    token,
    filter_formula=None,
    fields=None,
    timeout=DEFAULT_REQUEST_TIMEOUT_SECONDS,
    max_attempts=3,
):
    """Fetch all Airtable pages while retaining the original query parameters."""

    url = f"https://api.airtable.com/v0/{base_id}/{table_id}"
    headers = {"Authorization": f"Bearer {token}"}
    base_params = {"pageSize": 100}
    if filter_formula:
        base_params["filterByFormula"] = filter_formula
    if fields:
        base_params["fields[]"] = list(fields)

    records = []
    offset = None
    while True:
        params = dict(base_params)
        if offset:
            params["offset"] = offset

        response = None
        for attempt in range(max_attempts):
            try:
                response = requests.get(url, headers=headers, params=params, timeout=timeout)
            except requests.RequestException as exc:
                if attempt + 1 == max_attempts:
                    raise AirtableRequestError(f"Airtable request failed: {exc}") from exc
                time.sleep(min(2 ** attempt, 30))
                continue

            if response.status_code == 200:
                break
            if response.status_code not in RETRYABLE_STATUS_CODES or attempt + 1 == max_attempts:
                body = getattr(response, "text", "")[:200]
                raise AirtableRequestError(
                    f"Airtable API error {response.status_code}: {body}"
                )
            time.sleep(_retry_delay(response, attempt))

        data = response.json()
        records.extend(data.get("records", []))
        offset = data.get("offset")
        if not offset:
            return records


def _window_details(window):
    if window is None:
        return {}
    return {
        "cursor_before": window.cursor_before.isoformat(),
        "query_after": window.query_after.isoformat(),
        "cursor_after": window.upper_bound.isoformat(),
    }


def run_session_import(
    command,
    *,
    sync_type,
    model,
    base_id,
    table_id,
    token,
    fields,
    incremental_new,
    dry_run,
    upper_bound,
    fetcher=fetch_airtable_records,
    verbose_callback=None,
):
    """Execute one full or new-record-only session import.

    The database upsert, cursor acknowledgement, and successful log completion
    share one transaction. A crash therefore replays an overlapped window rather
    than silently skipping records.
    """

    mode = "incremental_new" if incremental_new else "full"
    if dry_run:
        command.stdout.write(
            command.style.WARNING("=== DRY RUN MODE — no changes will be saved ===\n")
        )

    with airtable_sync_lock(sync_type) as acquired:
        if not acquired:
            command.stdout.write(
                command.style.WARNING(
                    f"Skipped {sync_type}: another sync for this feed is already running"
                )
            )
            return None

        sync_log = None
        if not dry_run:
            sync_log = AirtableSyncLog.objects.create(
                sync_type=sync_type,
                details={"mode": mode},
            )
            command.stdout.write(f"Sync log started (ID: {sync_log.id}, mode: {mode})")

        try:
            window = None
            filter_formula = None
            if incremental_new:
                window = prepare_created_window(sync_type, upper_bound=upper_bound)
                filter_formula = created_time_filter(window.query_after)

            records = fetcher(
                base_id=base_id,
                table_id=table_id,
                token=token,
                filter_formula=filter_formula,
                fields=fields,
            )
            command.stdout.write(
                command.style.SUCCESS(f"Fetched {len(records)} records from Airtable ({mode})")
            )
            if verbose_callback:
                verbose_callback(records[:3])

            if dry_run:
                command.stdout.write(f"DRY RUN: would process {len(records)} records")
                command.stdout.write(f"Current row count in DB: {model.objects.count()}")
                return None

            with transaction.atomic():
                stats = command.bulk_upsert(records)
                cursor_after = window.upper_bound if window else sync_log.started_at
                advance_created_cursor(sync_type, cursor_after)

                sync_log.records_processed = len(records)
                sync_log.records_created = stats["created"]
                sync_log.records_updated = stats["updated"]
                sync_log.records_skipped = stats["skipped"]
                sync_log.details = {
                    "mode": mode,
                    **_window_details(window),
                    "cursor_after": cursor_after.isoformat(),
                }
                sync_log.mark_complete(success=True)

            command.stdout.write(
                command.style.SUCCESS(
                    "\nSync complete — "
                    f"mode: {mode}, Airtable records: {len(records)}, "
                    f"created: {stats['created']}, updated: {stats['updated']}, "
                    f"skipped: {stats['skipped']}"
                )
            )
            return stats
        except Exception as exc:
            if sync_log:
                try:
                    sync_log.mark_complete(success=False, error_message=str(exc))
                except Exception:
                    pass
            command.stdout.write(command.style.ERROR(f"Sync failed: {exc}"))
            raise


def _advisory_lock_id(sync_type):
    digest = hashlib.blake2b(sync_type.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, byteorder="big", signed=True)


@contextmanager
def airtable_sync_lock(sync_type):
    """Prevent overlapping runs of one feed on PostgreSQL.

    SQLite is used for local focused tests and has no advisory locks. Production
    is PostgreSQL, where the session-scoped lock is released in `finally` even
    when the importer raises.
    """

    if connection.vendor != "postgresql":
        yield True
        return

    lock_id = _advisory_lock_id(sync_type)
    acquired = False
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s)", [lock_id])
        acquired = bool(cursor.fetchone()[0])
    try:
        yield acquired
    finally:
        if acquired:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s)", [lock_id])
