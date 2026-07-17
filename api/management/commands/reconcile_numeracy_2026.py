import os

import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from dotenv import load_dotenv

from api.management.commands.export_numeracy_2026_parquet import DEFAULT_OUT, REQUIRED_COLUMNS
from api.management.commands.sync_airtable_numeracy_assessments_2026 import Command as AssessmentSync
from api.management.commands.sync_airtable_numeracy_on_programme_2026 import Command as RosterSync
from api.models import CanonicalChild, NumeracyAssessment2026, NumeracyOnTheProgramme2026
from api.numeracy_2026 import COMPONENTS, evaluate_quality, parse_numeric, uid_value


EXPECTED_ASSESSMENT_MIN = 2000
EXPECTED_ROSTER_MIN = 600
EXPECTED_JAN_MIN = 600
EXPECTED_JUNE_MIN = 450


def _raw_assessment(record):
    fields = record.get("fields", {})
    year = parse_numeric(fields.get("Year"))
    row = {
        "source_airtable_id": record.get("id"),
        "child_uid": uid_value(fields.get("Child UID")),
        "year": int(year) if year is not None else None,
        "term": uid_value(fields.get("Term")),
        "total_raw": parse_numeric(fields.get("Total (162)")),
    }
    for component in COMPONENTS:
        row[component.model_field] = parse_numeric(fields.get(component.airtable_field))
    return row


def aggregate_rows(assessment_rows, roster_uids, canonical_uids):
    in_h1 = [
        row for row in assessment_rows if row.get("year") == 2026 and row.get("term") in ("Jan", "Jun")
    ]
    winners, _issues = evaluate_quality(in_h1)
    accepted = {
        key: row
        for key, row in winners.items()
        if row.get("child_uid") in roster_uids
        and row.get("child_uid") in canonical_uids
    }
    component_stats = {}
    for term, prefix in (("Jan", "Jan"), ("Jun", "June")):
        for component in COMPONENTS:
            values = [
                row.get(component.model_field)
                for (uid, year, candidate_term), row in accepted.items()
                if year == 2026
                and candidate_term == term
                and row.get(component.model_field) is not None
            ]
            component_stats[f"{prefix} - {component.display_name}"] = {
                "count": len(values),
                "mean": (sum(values) / len(values)) if values else None,
            }
    matched_complete = 0
    for uid in roster_uids:
        jan = accepted.get((uid, 2026, "Jan"))
        june = accepted.get((uid, 2026, "Jun"))
        if jan and june and all(
            jan.get(component.model_field) is not None
            and june.get(component.model_field) is not None
            for component in COMPONENTS
        ):
            matched_complete += 1
    return {
        "assessment_rows": len(assessment_rows),
        "jan_rows": sum(row.get("year") == 2026 and row.get("term") == "Jan" for row in assessment_rows),
        "june_rows": sum(row.get("year") == 2026 and row.get("term") == "Jun" for row in assessment_rows),
        "roster_count": len(roster_uids),
        "roster_uids": set(roster_uids),
        "jan_unique_uids": len(
            {row.get("child_uid") for row in in_h1 if row.get("term") == "Jan" and row.get("child_uid")}
        ),
        "june_unique_uids": len(
            {row.get("child_uid") for row in in_h1 if row.get("term") == "Jun" and row.get("child_uid")}
        ),
        "matched_complete": matched_complete,
        "canonical_resolved": len(set(roster_uids) & set(canonical_uids)),
        "component_stats": component_stats,
    }


def compare_reconciliation(
    source,
    postgres,
    parquet,
    tolerance=1e-9,
    min_assessments=1,
    min_jan=1,
    min_june=1,
    min_roster=EXPECTED_ROSTER_MIN,
):
    checks = []

    def add(name, got, want, ok):
        checks.append({"check": name, "got": got, "want": want, "ok": bool(ok)})

    missing = [column for column in REQUIRED_COLUMNS if column not in parquet.columns]
    add("required_columns", missing, [], not missing)
    add("source_assessment_floor", source["assessment_rows"], f">={min_assessments}", source["assessment_rows"] >= min_assessments)
    add("source_january_floor", source["jan_rows"], f">={min_jan}", source["jan_rows"] >= min_jan)
    add("source_june_floor", source["june_rows"], f">={min_june}", source["june_rows"] >= min_june)
    add("source_roster_floor", source["roster_count"], f">={min_roster}", source["roster_count"] >= min_roster)
    for key in (
        "assessment_rows",
        "jan_rows",
        "june_rows",
        "roster_count",
        "jan_unique_uids",
        "june_unique_uids",
        "matched_complete",
        "canonical_resolved",
    ):
        add(f"postgres_{key}", postgres[key], source[key], postgres[key] == source[key])
    add("postgres_roster_uid_set", postgres["roster_uids"], source["roster_uids"], postgres["roster_uids"] == source["roster_uids"])
    if not missing:
        parquet_uids = set(parquet["child_uid"].dropna())
        add("parquet_row_count", len(parquet), source["roster_count"], len(parquet) == source["roster_count"])
        add("parquet_uid_set", parquet_uids, source["roster_uids"], parquet_uids == source["roster_uids"])
        add("parquet_uid_unique", parquet["child_uid"].is_unique, True, parquet["child_uid"].is_unique)
        parquet_matched = int(
            (parquet["Jan - Assessment Complete"].fillna(False)
             & parquet["June - Assessment Complete"].fillna(False)).sum()
        )
        add("parquet_matched_complete", parquet_matched, source["matched_complete"], parquet_matched == source["matched_complete"])
        for column, expected in source["component_stats"].items():
            if column not in parquet:
                continue
            values = pd.to_numeric(parquet[column], errors="coerce").dropna()
            add(f"{column}_count", len(values), expected["count"], len(values) == expected["count"])
            got_mean = float(values.mean()) if len(values) else None
            want_mean = expected["mean"]
            means_match = got_mean is None and want_mean is None
            if got_mean is not None and want_mean is not None:
                means_match = abs(got_mean - want_mean) <= tolerance
            add(f"{column}_mean", got_mean, want_mean, means_match)
    for column, expected in source["component_stats"].items():
        actual = postgres["component_stats"].get(column)
        add(f"postgres_{column}_stats", actual, expected, actual == expected)
    return {"ok": all(check["ok"] for check in checks), "checks": checks}


def golden_trace(uid, source_rows, postgres_rows, parquet):
    source_winners, _ = evaluate_quality(
        [row for row in source_rows if row.get("child_uid") == uid and row.get("year") == 2026]
    )
    postgres_winners, _ = evaluate_quality(
        [row for row in postgres_rows if row.get("child_uid") == uid and row.get("year") == 2026]
    )
    parquet_rows = parquet.loc[parquet["child_uid"] == uid]
    mismatches = []
    if len(parquet_rows) != 1:
        return {"ok": False, "mismatches": ["parquet_row_count"]}
    output = parquet_rows.iloc[0]

    def equal(left, right):
        if pd.isna(left) and pd.isna(right):
            return True
        return left == right

    for term, prefix in (("Jan", "Jan"), ("Jun", "June")):
        source = source_winners.get((uid, 2026, term))
        postgres = postgres_winners.get((uid, 2026, term))
        for component in COMPONENTS:
            source_value = source.get(component.model_field) if source else None
            postgres_value = postgres.get(component.model_field) if postgres else None
            parquet_value = output[f"{prefix} - {component.display_name}"]
            if not (equal(source_value, postgres_value) and equal(source_value, parquet_value)):
                mismatches.append(f"{prefix}:{component.display_name}")
        source_total = source.get("total_raw") if source else None
        postgres_total = postgres.get("total_raw") if postgres else None
        if not (
            equal(source_total, postgres_total)
            and equal(source_total, output[f"{prefix} - Total"])
        ):
            mismatches.append(f"{prefix}:Total")
    return {"ok": not mismatches, "mismatches": mismatches}


class Command(BaseCommand):
    help = "Independently reconcile Airtable, local Postgres, and the numeracy parquet"

    def add_arguments(self, parser):
        parser.add_argument("--parquet", default=str(DEFAULT_OUT))
        parser.add_argument("--golden-uid", action="append", default=[])

    def handle(self, *args, **options):
        if len(options["golden_uid"]) != 3:
            raise CommandError("Provide exactly three operator-selected --golden-uid values")
        if not os.path.exists(options["parquet"]):
            raise CommandError(f"Parquet not found: {options['parquet']}")
        load_dotenv()
        token = os.getenv("AIRTABLE_TOKEN") or os.getenv("AIRTABLE_API_KEY")
        assessment_base = os.getenv("AIRTABLE_NUMERACY_2026_ASSESSMENTS_BASE_ID")
        assessment_table = os.getenv("AIRTABLE_NUMERACY_2026_ASSESSMENTS_TABLE_ID")
        roster_base = os.getenv("AIRTABLE_NUMERACY_ON_THE_PROGRAMME_2026_BASE_ID")
        roster_table = os.getenv("AIRTABLE_NUMERACY_ON_THE_PROGRAMME_2026_TABLE_ID")
        if not all((token, assessment_base, assessment_table, roster_base, roster_table)):
            raise CommandError("Missing Airtable configuration for numeracy reconciliation")
        raw_assessments = AssessmentSync().fetch_from_airtable(
            assessment_base.strip(), assessment_table.strip(), token.strip()
        )
        raw_roster = RosterSync().fetch_from_airtable(
            roster_base.strip(), roster_table.strip(), token.strip()
        )
        source_rows = [_raw_assessment(record) for record in raw_assessments]
        source_roster_uids = {
            uid_value(record.get("fields", {}).get("Child UID")) for record in raw_roster
        } - {None}
        canonical_uids = set(CanonicalChild.objects.values_list("child_uid", flat=True))
        source = aggregate_rows(source_rows, source_roster_uids, canonical_uids)

        fields = [
            "source_airtable_id",
            "child_uid",
            "year",
            "term",
            "total_raw",
            *(component.model_field for component in COMPONENTS),
        ]
        postgres_rows = list(
            NumeracyAssessment2026.objects.filter(is_active=True).values(*fields)
        )
        postgres_roster_uids = set(
            NumeracyOnTheProgramme2026.objects.filter(is_active=True).values_list("child_uid", flat=True)
        )
        postgres = aggregate_rows(postgres_rows, postgres_roster_uids, canonical_uids)
        parquet = pd.read_parquet(options["parquet"])
        result = compare_reconciliation(
            source,
            postgres,
            parquet,
            min_assessments=EXPECTED_ASSESSMENT_MIN,
            min_jan=EXPECTED_JAN_MIN,
            min_june=EXPECTED_JUNE_MIN,
        )
        for check in result["checks"]:
            style = self.style.SUCCESS if check["ok"] else self.style.ERROR
            self.stdout.write(style(f"{check['check']}: got={check['got']} want={check['want']}"))

        golden_ok = True
        for uid in options["golden_uid"]:
            trace = golden_trace(uid, source_rows, postgres_rows, parquet)
            golden_ok = golden_ok and trace["ok"]
            style = self.style.SUCCESS if trace["ok"] else self.style.ERROR
            self.stdout.write(
                style(
                    f"GOLDEN {uid}: exact_component_and_total_match={trace['ok']} "
                    f"mismatches={trace['mismatches']}"
                )
            )
        if not result["ok"] or not golden_ok:
            raise CommandError("Numeracy reconciliation failed")
        self.stdout.write(self.style.SUCCESS("Numeracy reconciliation passed"))
