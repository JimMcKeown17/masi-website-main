"""Refresh the cached Zazi programme-overview snapshot for the WIG dashboard.

The Zazi /api/programme-overview/ endpoint takes ~10s to compute, so the WIG
Zazi tile reads a cached snapshot instead of calling it live. Run this on a
schedule (e.g. hourly) so the snapshot stays fresh out-of-band.
"""
from django.core.management.base import BaseCommand

from api import zazi_client


class Command(BaseCommand):
    help = "Fetch the Zazi programme overview and cache it as the WIG Zazi snapshot."

    def handle(self, *args, **options):
        snap = zazi_client.refresh_zazi_snapshot()
        if snap.ok:
            self.stdout.write(self.style.SUCCESS(f"Zazi snapshot refreshed at {snap.fetched_at}"))
        else:
            self.stderr.write(f"Zazi snapshot refresh failed (kept last-good): {snap.error_message}")
