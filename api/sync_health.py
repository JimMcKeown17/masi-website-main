"""Freshness semantics for the two Airtable feeds behind Youth Sessions."""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from api.models import AirtableSyncLog


SESSION_SYNC_TYPES = {
    "literacy": "literacy_sessions_2026",
    "numeracy": "numeracy_sessions_2026",
}


def _isoformat(value):
    if value is None:
        return None
    return value.isoformat().replace("+00:00", "Z")


def _source_health(sync_type, *, now, stale_after):
    logs = AirtableSyncLog.objects.filter(sync_type=sync_type)
    latest_attempt = logs.order_by("-started_at").first()
    latest_success = (
        logs.filter(success=True)
        .exclude(completed_at__isnull=True)
        .order_by("-completed_at")
        .first()
    )

    last_success_at = latest_success.completed_at if latest_success else None
    success_is_stale = last_success_at is None or now - last_success_at > stale_after

    status = "never"
    error_message = None
    if latest_attempt and (latest_success is None or latest_attempt.started_at > latest_success.started_at):
        if latest_attempt.completed_at is None:
            attempt_is_stuck = now - latest_attempt.started_at > stale_after
            status = "stale" if attempt_is_stuck or success_is_stale else "syncing"
        elif not latest_attempt.success:
            status = "failed"
            error_message = latest_attempt.error_message
        else:
            status = "stale" if success_is_stale else "fresh"
    elif latest_success:
        status = "stale" if success_is_stale else "fresh"

    return {
        "status": status,
        "last_successful_sync": _isoformat(last_success_at),
        "last_attempt_started_at": _isoformat(latest_attempt.started_at if latest_attempt else None),
        "last_attempt_completed_at": _isoformat(latest_attempt.completed_at if latest_attempt else None),
        "error_message": error_message,
    }


def build_youth_session_freshness():
    now = timezone.now()
    cadence_minutes = settings.YOUTH_SESSIONS_SYNC_CADENCE_MINUTES
    stale_after_minutes = settings.YOUTH_SESSIONS_STALE_AFTER_MINUTES
    stale_after = timedelta(minutes=stale_after_minutes)
    sources = {
        name: _source_health(sync_type, now=now, stale_after=stale_after)
        for name, sync_type in SESSION_SYNC_TYPES.items()
    }

    statuses = {source["status"] for source in sources.values()}
    if "failed" in statuses:
        status = "failed"
    elif "never" in statuses:
        status = "never"
    elif "stale" in statuses:
        status = "stale"
    elif "syncing" in statuses:
        status = "syncing"
    else:
        status = "fresh"

    successful_values = [
        source["last_successful_sync"] for source in sources.values()
    ]
    all_sources_have_success = all(successful_values)
    last_successful_sync = min(successful_values) if all_sources_have_success else None
    version = "|".join(value or "never" for value in successful_values)

    return {
        "status": status,
        "is_stale": status in {"failed", "never", "stale"},
        "cadence_minutes": cadence_minutes,
        "stale_after_minutes": stale_after_minutes,
        "last_successful_sync": last_successful_sync,
        "checked_at": _isoformat(now),
        "version": version,
        "sources": sources,
    }
