from __future__ import annotations

import calendar
import os
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from api.models import MonthlyYouthExpenditure
from api.youth_expenditure_import import (
    YouthExpenditureImportError,
    read_youth_expenditure_workbook,
    resolve_latest_management_workbook,
)


def default_workbook_directory() -> Path:
    configured = os.getenv("MASI_MANAGEMENT_SHEETS_DIR")
    if configured:
        return Path(configured).expanduser()
    return Path(settings.BASE_DIR).resolve().parents[2] / "masi-finance" / "management_sheets"


class Command(BaseCommand):
    help = (
        "Preview or publish monthly Youth Jobs actuals from the latest "
        "management workbook"
    )

    def add_arguments(self, parser):
        source = parser.add_mutually_exclusive_group()
        source.add_argument(
            "--workbook-dir",
            default=str(default_workbook_directory()),
            help=(
                "Directory containing YYYYMMDD management workbooks; defaults "
                "to MASI_MANAGEMENT_SHEETS_DIR or the local masi-finance checkout"
            ),
        )
        source.add_argument(
            "--path",
            help="Use one explicit management workbook instead of resolving the latest",
        )
        parser.add_argument("--year", type=int, default=date.today().year)
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Write the previewed full-year snapshot to the database",
        )
        parser.add_argument(
            "--allow-category-errors",
            action="store_true",
            help=(
                "Acknowledge selected-year rows whose Category 1/2/3 cells are "
                "Excel errors and remain excluded from Youth Jobs totals"
            ),
        )

    def handle(self, *args, **options):
        try:
            path = (
                Path(options["path"])
                if options.get("path")
                else resolve_latest_management_workbook(options["workbook_dir"])
            )
            snapshot = read_youth_expenditure_workbook(
                path,
                year=options["year"],
            )
        except YouthExpenditureImportError as exc:
            raise CommandError(str(exc)) from exc

        existing = {
            row.month: row
            for row in MonthlyYouthExpenditure.objects.filter(
                year=snapshot.year
            ).order_by("month")
        }
        self._write_preview(snapshot, existing)

        if not options["apply"]:
            self.stdout.write(
                self.style.WARNING(
                    "DRY RUN: no database rows changed. Re-run with --apply to publish."
                )
            )
            return

        if snapshot.category_errors and not options["allow_category_errors"]:
            raise CommandError(
                f"Workbook has {len(snapshot.category_errors)} category errors for "
                f"{snapshot.year}; review them and re-run with "
                "--allow-category-errors to acknowledge their exclusion"
            )

        newest_source_month = max(snapshot.months)
        later_existing = sorted(
            month for month in existing if month > newest_source_month
        )
        if later_existing:
            names = ", ".join(calendar.month_name[month] for month in later_existing)
            raise CommandError(
                "Database contains actual months later than the selected workbook: "
                f"{names}. Refusing to move published actuals backwards."
            )

        with transaction.atomic():
            for month, amounts in snapshot.months.items():
                MonthlyYouthExpenditure.objects.update_or_create(
                    year=snapshot.year,
                    month=month,
                    defaults={
                        "core_amount": amounts.core_amount,
                        "mentor_amount": amounts.mentor_amount,
                        "rural_amount": amounts.rural_amount,
                        "note": (
                            f"Imported from {snapshot.path.name} | "
                            f"sha256={snapshot.sha256} | rows={amounts.row_count}"
                        ),
                    },
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"APPLIED: {len(snapshot.months)} months restated for "
                f"{snapshot.year} from {snapshot.path.name}"
            )
        )

    def _write_preview(self, snapshot, existing):
        self.stdout.write(f"Source: {snapshot.path}")
        self.stdout.write(f"SHA-256: {snapshot.sha256}")
        self.stdout.write(
            "Source modified: "
            f"{snapshot.source_modified_at.astimezone().isoformat(timespec='seconds')}"
        )
        self.stdout.write(
            f"Classified Youth Jobs rows: {snapshot.classified_row_count}"
        )
        self.stdout.write(f"Category errors: {len(snapshot.category_errors)}")
        for issue in snapshot.category_errors:
            month_name = (
                calendar.month_name[issue.month]
                if issue.month is not None
                else "invalid month"
            )
            self.stdout.write(
                self.style.WARNING(
                    f"  row {issue.row}: {month_name}, R {issue.amount:.2f}, "
                    f"categories={issue.values!r}"
                )
            )
        if snapshot.date_period_mismatch_rows:
            self.stdout.write(
                self.style.WARNING(
                    "Date differs from accounting Month/Year on rows: "
                    + ", ".join(
                        str(row) for row in snapshot.date_period_mismatch_rows
                    )
                )
            )

        self.stdout.write(
            "Month      Rows          Core        Mentor         Rural         Total"
            "         Delta"
        )
        for month, amounts in snapshot.months.items():
            previous = existing.get(month)
            previous_total = (
                previous.core_amount
                + previous.mentor_amount
                + previous.rural_amount
                if previous is not None
                else Decimal("0")
            )
            self.stdout.write(
                f"{calendar.month_abbr[month]:<10}"
                f"{amounts.row_count:>5}"
                f"{amounts.core_amount:>14.2f}"
                f"{amounts.mentor_amount:>14.2f}"
                f"{amounts.rural_amount:>14.2f}"
                f"{amounts.total:>14.2f}"
                f"{amounts.total - previous_total:>14.2f}"
            )
