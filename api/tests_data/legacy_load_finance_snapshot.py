# api/management/commands/load_finance_snapshot.py
"""Preview or publish a finance snapshot produced by masi-finance.

    manage.py load_finance_snapshot outputs/publish/finance-snapshot-<run>.json
    manage.py load_finance_snapshot <path> --apply
    manage.py load_finance_snapshot <path> --apply --force

Same ritual as sync_youth_expenditure: read-only preview unless --apply;
the preview prints provenance and the per-contract differences from what
is published; applies restate the year's single row in one transaction.
Two guards (spec section 7, after the complexity check): the schema
version must be one this code knows, and an artifact must not move the
published figures backwards. The only ordering signal is the workbook's
YYYYMMDD date: an older date is refused; the same date with the same
hash restates idempotently; the same date with a DIFFERENT hash is
refused too, because neither published_at (artifact generation time)
nor the file's mtime (a plain copy gets a fresh one) says which content
is newer, and guessing wrong would replace corrected figures with a
stale backup. --force is the operator's explicit statement. The guard
is decided under a row lock inside the same transaction as the write,
so a preview that looked fine cannot be overtaken between the check and
the write.
Every run's file stays in masi-finance/outputs/publish/; that is the
publication history, so the database keeps one row per year.
"""

from __future__ import annotations

from datetime import timezone
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from api.finance_snapshot import (
    FinanceSnapshotError,
    load_snapshot_file,
    parse_date,
    parse_timestamp,
)
from api.models import FinanceSnapshot


class Command(BaseCommand):
    help = "Preview or publish a finance snapshot (funder contracts, allocation coverage, findings)"

    def add_arguments(self, parser):
        parser.add_argument("path", help="Path to a finance-snapshot-<run id>.json written by masi-finance")
        parser.add_argument("--apply", action="store_true", help="Write the snapshot to the database")
        parser.add_argument(
            "--force", action="store_true",
            help="Publish even if the workbook is older than the currently published one",
        )

    def handle(self, *args, **options):
        try:
            payload = load_snapshot_file(options["path"])
        except FinanceSnapshotError as exc:
            raise CommandError(str(exc)) from exc

        year = payload["accounting_year"]
        source = payload["source"]
        workbook_date = parse_date(source["workbook_date"])
        modified_at = parse_timestamp(source["modified_at"])
        published_at = parse_timestamp(payload["published_at"])
        existing = FinanceSnapshot.objects.filter(accounting_year=year).first()

        self._write_preview(payload, Path(options["path"]), existing,
                            _refusal(existing, workbook_date, source["sha256"], payload["payload_sha256"]))

        if not options["apply"]:
            self.stdout.write(self.style.WARNING("DRY RUN: no database rows changed. Re-run with --apply to publish."))
            return

        with transaction.atomic():
            locked = FinanceSnapshot.objects.select_for_update().filter(accounting_year=year).first()
            refusal = _refusal(locked, workbook_date, source["sha256"], payload["payload_sha256"])
            if refusal and not options["force"]:
                raise CommandError(f"{refusal} for {year}. Re-run with --force to override.")
            FinanceSnapshot.objects.update_or_create(
                accounting_year=year,
                defaults={
                    "schema_version": payload["schema_version"],
                    "run_id": payload["run_id"],
                    "workbook_name": source["workbook_name"],
                    "workbook_date": workbook_date,
                    "workbook_modified_at": modified_at,
                    "workbook_sha256": source["sha256"],
                    "payload_sha256": payload["payload_sha256"],
                    "published_at": published_at,
                    "payload": payload,
                },
            )
        verb = "FORCED" if refusal else "APPLIED"
        self.stdout.write(self.style.SUCCESS(
            f"{verb}: finance snapshot for {year} restated from {source['workbook_name']} ({payload['run_id']})"
        ))

    def _write_preview(self, payload: dict, path: Path, existing, refusal: str | None) -> None:
        source = payload["source"]
        contracts = payload["funder_contracts"]
        self.stdout.write(f"Source: {path.resolve()}")
        self.stdout.write(f"Run: {payload['run_id']}  accounting year {payload['accounting_year']}  schema {payload['schema_version']}")
        self.stdout.write(f"Workbook: {source['workbook_name']}  date {source['workbook_date']}  sha256 {source['sha256']}")
        self.stdout.write(f"Published: {payload['published_at']}")
        self.stdout.write(
            f"{len(contracts)} contracts, {sum(len(c['lines']) for c in contracts)} lines, "
            f"{len(payload['allocation_coverage'])} coverage groups, {len(payload['findings'])} findings"
        )
        if existing is None:
            self.stdout.write(f"Database: no published snapshot for {payload['accounting_year']} yet.")
        else:
            self.stdout.write(
                f"Database: {existing.workbook_name} ({existing.run_id}) loaded {existing.loaded_at.isoformat(timespec='seconds')}; "
                f"workbook date {existing.workbook_date.isoformat()} -> {source['workbook_date']}"
            )
            if refusal:
                self.stdout.write(self.style.WARNING(f"{refusal}; --apply would be refused without --force."))
        self._write_contract_deltas(contracts, existing.payload.get("funder_contracts", []) if existing else [])
        self._write_finding_counts(payload["findings"])

    def _write_contract_deltas(self, new: list[dict], old: list[dict]) -> None:
        previous = {contract["id"]: contract for contract in old}
        self.stdout.write(
            f"{'contract':<34}{'period':<28}{'budget':>14}{'lifetime':>14}{'in-year':>12}{'remaining':>14}{'delta':>12}"
        )
        for contract in new:
            before = previous.pop(contract["id"], None)
            delta = ""
            if before is not None:
                change = Decimal(contract["allocated_total_lifetime"]) - Decimal(before["allocated_total_lifetime"])
                delta = f"{change:+.2f}" if change else "0.00"
            else:
                delta = "new"
            self.stdout.write(
                f"{(contract['contract_code'] or contract['block_label'])[:33]:<34}{(contract['period_label'] or '')[:27]:<28}"
                f"{_money(contract['budget_total']):>14}{_money(contract['allocated_total_lifetime']):>14}"
                f"{_money(contract['allocated_total_in_year']):>12}{_money(contract['remaining']):>14}{delta:>12}"
            )
        for contract in previous.values():
            self.stdout.write(self.style.WARNING(
                f"{(contract['contract_code'] or contract['block_label'])[:33]:<34}{(contract['period_label'] or '')[:27]:<28}{'removed':>78}"
            ))

    def _write_finding_counts(self, findings: list[dict]) -> None:
        counts: dict[tuple[str, str, bool], int] = {}
        for finding in findings:
            key = (finding["code"], finding["severity"], finding["in_scope_year"])
            counts[key] = counts.get(key, 0) + 1
        for (code, severity, in_scope), count in sorted(counts.items(), key=lambda item: (not item[0][2], item[0][1], item[0][0])):
            self.stdout.write(f"  {code:<26}{severity:<8}{'in-year' if in_scope else 'out-of-year':<13}{count:>5}")


def _refusal(existing, workbook_date, sha256: str, payload_sha256: str) -> str | None:
    """Why --apply would be refused, or None. Overview sections 3.15 and 3.24."""
    if existing is None:
        return None
    if workbook_date < existing.workbook_date:
        return (
            f"Workbook {workbook_date.isoformat()} is older than the published snapshot's "
            f"{existing.workbook_date.isoformat()}. Refusing to move published figures backwards"
        )
    if workbook_date == existing.workbook_date and sha256 != existing.workbook_sha256:
        return (
            f"Artifact has the same workbook date {workbook_date.isoformat()} as the published snapshot but a "
            f"different sha256 ({sha256[:12]} vs {existing.workbook_sha256[:12]}); which content is newer cannot "
            "be inferred from the file"
        )
    if workbook_date == existing.workbook_date and payload_sha256 != existing.payload_sha256:
        return (
            f"Artifact comes from the same workbook ({sha256[:12]}) as the published snapshot but its figures differ "
            f"(payload {payload_sha256[:12]} vs {existing.payload_sha256[:12]}); a different publisher version or an "
            "edited artifact. See the deltas above"
        )
    return None


def _stamp(value) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _money(value: str | None) -> str:
    return "not set" if value is None else f"{Decimal(value):,.2f}"
