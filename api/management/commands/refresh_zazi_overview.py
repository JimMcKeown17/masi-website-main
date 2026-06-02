"""Refresh the cached Zazi programme-overview snapshots for the WIG dashboard.

The Zazi /api/programme-overview/ endpoint takes ~10s to compute, so the WIG
Zazi tiles read cached snapshots instead of calling it live. There is one row
per cohort (Primary + ECD). Run this on a schedule (e.g. hourly) so the
snapshots stay fresh out-of-band.
"""
from django.core.management.base import BaseCommand

from api import zazi_client
from api.zazi_client import ZAZI_SEGMENTS


class Command(BaseCommand):
    help = "Fetch the Zazi programme overview per cohort and cache it as the WIG Zazi snapshots."

    def handle(self, *args, **options):
        for _prog_key, cohort, _prefix in ZAZI_SEGMENTS:
            snap = zazi_client.refresh_zazi_snapshot(cohort)
            if snap.ok:
                self.stdout.write(self.style.SUCCESS(f"Zazi [{cohort}] snapshot refreshed at {snap.fetched_at}"))
            else:
                self.stderr.write(f"Zazi [{cohort}] refresh failed (kept last-good): {snap.error_message}")
