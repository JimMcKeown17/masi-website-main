"""Nightly refresh of the School Programme Grid system-owned columns.

Reuses the house cron pattern (AirtableSyncLog logging + fail-closed transaction):
the whole refresh runs in one transaction, so a mid-run failure rolls back every
write -- no partial rows published under a fresh as_of -- and the failure is
recorded on the sync log rather than swallowed. Human-owned columns are never
touched (the orchestrator writes system columns only).

Run nightly on Render, alongside the existing Airtable syncs.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from api.models import AirtableSyncLog
from api.school_programme import (
    build_grid_health,
    refresh_school_programme_grid,
    rollup_to_published_stats,
)
from api.zazi_client import fetch_school_programme_export


class Command(BaseCommand):
    help = "Refresh the School Programme Grid system-owned columns for a year."

    def add_arguments(self, parser):
        parser.add_argument(
            "--year",
            type=int,
            default=None,
            help="Year to refresh (default: current year).",
        )
        parser.add_argument(
            "--skip-zazi",
            action="store_true",
            help="Explicitly skip the Zazi export (within-Masi only). Use during a "
                 "Zazi maintenance window; otherwise the refresh fails closed if "
                 "Zazi is unreachable rather than silently undercounting.",
        )

    def handle(self, *args, **options):
        year = options["year"] or timezone.now().year
        sync_log = AirtableSyncLog.objects.create(sync_type="school_programme_grid")
        try:
            # Fetch Zazi BEFORE opening the write transaction: a network failure
            # then aborts with zero DB changes (fail-closed, prior grid intact).
            zazi_export = None
            if not options["skip_zazi"]:
                zazi_export = fetch_school_programme_export(year)
            with transaction.atomic():
                result = refresh_school_programme_grid(year, zazi_export=zazi_export)
                rollup = rollup_to_published_stats(year)
            sync_log.records_processed = result["schools_processed"]
            sync_log.records_created = result["rows_created"]
            sync_log.records_updated = result["rows_updated"]
            sync_log.details = build_grid_health(result, rollup, timezone.now())
            sync_log.mark_complete(success=True)
        except Exception as exc:
            sync_log.mark_complete(success=False, error_message=str(exc))
            raise
        self._report(result)
        self.stdout.write(
            self.style.SUCCESS(
                f"Rollups (Zazi-inclusive, unpublished): "
                f"{rollup['children']:,} children, "
                f"{rollup['sites_total']} sites "
                f"({rollup['schools_primary']} primary / {rollup['schools_ecd']} ECD)."
            )
        )

    def _report(self, result):
        self.stdout.write(
            self.style.SUCCESS(
                f"Grid refreshed for {result['year']}: "
                f"{result['schools_processed']} schools, "
                f"{result['rows_created']} created, {result['rows_updated']} updated."
            )
        )
        integ = result["integrity"]
        # Integrity checks are surfaced loudly as warnings -- never swallowed.
        warnings = [
            ("Unmapped job titles", integ["unmapped_titles"]),
            ("Schools with no school_uid", integ["unmatched_schools"]),
            ("Unknown site_type tokens", integ["unknown_site_type_tokens"]),
            ("Reach without identities", len(integ["reach_without_identities"]) or None),
            ("Site-assigned youth with no school", integ["site_assigned_no_school"]),
            ("Unmapped Zazi schools", integ.get("unmapped_zazi_schools")),
            ("Unresolved Zazi participants", integ.get("unresolved_zazi_participants")),
        ]
        for label, value in warnings:
            if value:
                self.stdout.write(self.style.WARNING(f"{label}: {value}"))
        if result["roster"]:
            self.stdout.write(f"Site-unassigned roster (off-grid): {result['roster']}")
