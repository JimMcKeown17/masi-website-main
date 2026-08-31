import csv
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from api.models import MonthlyYouthExpenditure
from api.youth_expenditure_import import MONTHS, bucket_for, parse_amount


class Command(BaseCommand):
    help = "Seed January to June 2026 youth expenditure from the finance ledger"

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default=str(
                Path(settings.BASE_DIR)
                / "staticfiles"
                / "data"
                / "youth-payments-jan-june-2026.csv"
            ),
        )

    @transaction.atomic
    def handle(self, *args, **options):
        path = Path(options["path"])
        if not path.exists():
            raise CommandError(f"Ledger CSV not found: {path}")

        grouped = defaultdict(
            lambda: {
                "core_amount": Decimal("0"),
                "mentor_amount": Decimal("0"),
                "rural_amount": Decimal("0"),
            }
        )
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            for source_row in reader:
                row = {
                    (key or "").strip(): value
                    for key, value in source_row.items()
                }
                month_name = (row.get("Month") or "").strip().lower()
                month = MONTHS.get(month_name)
                if month is None:
                    raise CommandError(
                        f"Unknown Month value: {row.get('Month')!r}"
                    )
                try:
                    amount = parse_amount(row.get("Amount"))
                except ValueError as exc:
                    raise CommandError(str(exc))
                grouped[month][bucket_for(row)] += amount

        for month, amounts in sorted(grouped.items()):
            MonthlyYouthExpenditure.objects.update_or_create(
                year=2026,
                month=month,
                defaults={
                    **amounts,
                    "note": "Seeded from youth payments ledger",
                },
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Youth expenditure ready for {len(grouped)} months"
            )
        )
