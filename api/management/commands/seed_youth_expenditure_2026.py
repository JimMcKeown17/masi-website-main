import calendar
import csv
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from api.models import MonthlyYouthExpenditure


MONTHS = {
    name.lower(): number
    for number, name in enumerate(calendar.month_name)
    if name
}


def parse_amount(raw):
    """Parse a finance-ledger Rand amount into Decimal."""
    cleaned = (
        str(raw or "")
        .strip()
        .replace("R", "")
        .replace(",", "")
        .replace(" ", "")
    )
    if not cleaned or cleaned == "-":
        return Decimal("0")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        raise ValueError(f"Invalid Amount value: {raw!r}")


def bucket_for(row):
    """Classify one ledger payment using the agreed priority order."""
    category_2 = (row.get("Category 2") or "").lower()
    category_3 = (row.get("Category 3") or "").lower()
    if "mentor" in category_3:
        return "mentor_amount"
    if "wind farm" in category_2 or "rural" in category_3:
        return "rural_amount"
    return "core_amount"


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
