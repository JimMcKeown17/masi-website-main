import csv
import json
import os
import tempfile
from pathlib import Path

import pandas as pd
from django.core.management.base import BaseCommand, CommandError

from api.models import (
    AirtableSyncLog,
    CanonicalChild,
    NumeracyAssessment2026,
    NumeracyOnTheProgramme2026,
)
from api.numeracy_2026 import COMPONENTS, evaluate_quality, issue_counts


TERM_PREFIX = {"Jan": "Jan", "Jun": "June"}
STREAMLIT_ROOT = Path(__file__).resolve().parents[6] / "Masi_Data_Site" / "masi_data_streamlit"
DEFAULT_OUT = STREAMLIT_ROOT / "data" / "parquet" / "raw" / "2026_numeracy_midline.parquet"
EXCEPTION_FIELDS = (
    "source_airtable_id",
    "child_uid",
    "year",
    "term",
    "issue_code",
    "component",
    "value",
    "maximum",
)
REQUIRED_COLUMNS = [
    "child_uid",
    "Full Name",
    "Mcode",
    "Name",
    "Surname",
    "Gender",
    "School",
    "Mentor",
    "Numeracy Coach",
    "Grade",
    "On the Programme",
    "Programme Belonging",
    "Identity Resolved",
    *[
        f"{prefix} - {component.display_name}"
        for prefix in ("Jan", "June")
        for component in COMPONENTS
    ],
    "Jan - Total",
    "June - Total",
    "Jan - Assessment Complete",
    "June - Assessment Complete",
    "Jan - Assessment Excluded",
    "June - Assessment Excluded",
    "Jan - Exclusion Reasons",
    "June - Exclusion Reasons",
]

NON_BLOCKING_ISSUE_CODES = {"REDUNDANT_IDENTICAL_DUPLICATE"}


def build_wide_frame(assessments, roster_by_uid, child_by_uid):
    in_2026 = [
        row for row in assessments if row.get("year") == 2026 and row.get("term") in TERM_PREFIX
    ]
    winners, issues = evaluate_quality(in_2026)
    source_groups = {
        (row.get("child_uid"), row.get("year"), row.get("term"))
        for row in in_2026
        if row.get("child_uid")
    }
    exclusion_reasons = {}
    for issue in issues:
        if issue["issue_code"] in NON_BLOCKING_ISSUE_CODES or not issue.get("child_uid"):
            continue
        key = (issue["child_uid"], issue.get("year"), issue.get("term"))
        exclusion_reasons.setdefault(key, set()).add(issue["issue_code"])
    off_roster = sum(
        bool(row.get("child_uid")) and row.get("child_uid") not in roster_by_uid for row in in_2026
    )
    rows = []
    unresolved_uids = []
    for uid in sorted(roster_by_uid):
        roster = roster_by_uid[uid]
        child = child_by_uid.get(uid, {})
        identity_resolved = bool(child.get("full_name"))
        if not identity_resolved:
            unresolved_uids.append(uid)
        output = {
            "child_uid": uid,
            "Full Name": child.get("full_name"),
            "Mcode": child.get("mcode"),
            "Name": child.get("first_name"),
            "Surname": child.get("surname"),
            "Gender": child.get("gender"),
            "School": roster.get("school"),
            "Mentor": roster.get("mentor"),
            "Numeracy Coach": roster.get("numeracy_coach"),
            "Grade": roster.get("grade"),
            "On the Programme": roster.get("programme_status"),
            "Programme Belonging": roster.get("programme_belonging") or [],
            "Identity Resolved": identity_resolved,
        }
        for term, prefix in TERM_PREFIX.items():
            key = (uid, 2026, term)
            reasons = set(exclusion_reasons.get(key, set()))
            if not identity_resolved and key in source_groups:
                reasons.add("UNRESOLVED_ROSTER_UID")
            accepted = winners.get(key) if not reasons else None
            present = []
            for component in COMPONENTS:
                value = accepted.get(component.model_field) if accepted else None
                output[f"{prefix} - {component.display_name}"] = value
                present.append(value is not None)
            output[f"{prefix} - Total"] = accepted.get("total_raw") if accepted else None
            output[f"{prefix} - Assessment Complete"] = bool(accepted and all(present))
            output[f"{prefix} - Assessment Excluded"] = bool(reasons)
            output[f"{prefix} - Exclusion Reasons"] = " | ".join(sorted(reasons))
        rows.append(output)
    frame = pd.DataFrame(rows, columns=REQUIRED_COLUMNS)
    blocking = [
        issue for issue in issues if issue["issue_code"] not in NON_BLOCKING_ISSUE_CODES
    ]
    return frame, {
        "issues": issues,
        "issue_counts": issue_counts(issues),
        "blocking_issue_count": len(blocking),
        "off_roster_assessments": off_roster,
        "unresolved_roster_uids": unresolved_uids,
        "identical_duplicate_count": sum(
            issue["issue_code"] == "REDUNDANT_IDENTICAL_DUPLICATE" for issue in issues
        ),
    }


def build_quality_summary(frame, meta):
    issues = meta.get("issues", [])
    blocking = [
        issue for issue in issues if issue.get("issue_code") not in NON_BLOCKING_ISSUE_CODES
    ]
    quarantined_assessments = [
        issue
        for issue in blocking
        if issue.get("issue_code") != "UNRESOLVED_ROSTER_UID"
    ]

    def unique_source_ids(rows):
        return {
            str(issue["source_airtable_id"])
            for issue in rows
            if issue.get("source_airtable_id")
        }

    def unique_groups(code):
        return {
            (issue.get("child_uid"), issue.get("year"), issue.get("term"))
            for issue in issues
            if issue.get("issue_code") == code
        }

    excluded_columns = [
        column for column in ("Jan - Assessment Excluded", "June - Assessment Excluded")
        if column in frame.columns
    ]
    excluded_children = (
        int(frame[excluded_columns].fillna(False).any(axis=1).sum())
        if excluded_columns
        else 0
    )
    unresolved_assessment_uids = {
        issue.get("child_uid")
        for issue in issues
        if issue.get("issue_code") == "UNRESOLVED_ASSESSMENT_UID"
        and issue.get("child_uid")
    }
    unresolved_roster_uids = {
        issue.get("child_uid")
        for issue in issues
        if issue.get("issue_code") == "UNRESOLVED_ROSTER_UID"
        and issue.get("child_uid")
    }
    missing_uid_records = unique_source_ids(
        [issue for issue in issues if issue.get("issue_code") == "MISSING_CHILD_UID"]
    )
    return {
        "roster_rows": int(len(frame)),
        "source_records_with_issues": len(unique_source_ids(issues)),
        "assessment_records_quarantined": len(unique_source_ids(quarantined_assessments)),
        "children_with_excluded_assessments": excluded_children,
        "missing_child_uid_records": len(missing_uid_records),
        "conflicting_duplicate_groups": len(unique_groups("CONFLICTING_DUPLICATE")),
        "out_of_range_cells": sum(
            issue.get("issue_code") == "OUT_OF_RANGE" for issue in issues
        ),
        "unresolved_assessment_uids": len(unresolved_assessment_uids),
        "unresolved_roster_uids": len(unresolved_roster_uids),
        "january_assessments_excluded": int(
            frame.get("Jan - Assessment Excluded", pd.Series(dtype=bool)).fillna(False).sum()
        ),
        "june_assessments_excluded": int(
            frame.get("June - Assessment Excluded", pd.Series(dtype=bool)).fillna(False).sum()
        ),
        "january_assessments_complete": int(
            frame.get("Jan - Assessment Complete", pd.Series(dtype=bool)).fillna(False).sum()
        ),
        "june_assessments_complete": int(
            frame.get("June - Assessment Complete", pd.Series(dtype=bool)).fillna(False).sum()
        ),
        "matched_complete_children": int(
            (
                frame.get("Jan - Assessment Complete", pd.Series(False, index=frame.index))
                & frame.get("June - Assessment Complete", pd.Series(False, index=frame.index))
            ).sum()
        ),
        "issue_counts": meta.get("issue_counts", issue_counts(issues)),
    }


class Command(BaseCommand):
    help = "Export the roster-shaped 2026 numeracy parquet"
    required_syncs = (
        "numeracy_assessments_2026",
        "numeracy_on_the_programme_2026",
    )

    def add_arguments(self, parser):
        parser.add_argument("--out", default=str(DEFAULT_OUT))
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Skip freshness checks for local dry-run diagnosis only",
        )

    def assert_clean_syncs(self):
        blocking_detail_keys = {
            "numeracy_assessments_2026": (
                "retire_skipped",
            ),
            "numeracy_on_the_programme_2026": (
                "retire_skipped",
                "duplicate_child_uids",
            ),
        }
        for sync_type in self.required_syncs:
            latest = AirtableSyncLog.objects.filter(sync_type=sync_type).order_by("-started_at").first()
            if latest is None or not latest.success or latest.completed_at is None:
                raise CommandError(f"Latest {sync_type} sync is missing, incomplete, or failed")
            details = latest.details or {}
            flagged = {
                key: details.get(key)
                for key in blocking_detail_keys[sync_type]
                if details.get(key)
            }
            if flagged:
                raise CommandError(f"Latest {sync_type} sync has publish blockers: {flagged}")

    def handle(self, *args, **options):
        if options["force"] and not options["dry_run"]:
            raise CommandError("--force is restricted to --dry-run local diagnosis")
        if not options["force"]:
            self.assert_clean_syncs()

        roster_rows = list(NumeracyOnTheProgramme2026.objects.filter(is_active=True))
        roster_by_uid = {
            row.child_uid: {
                "school": row.school,
                "mentor": row.mentor,
                "numeracy_coach": row.numeracy_coach,
                "grade": row.grade,
                "programme_status": row.programme_status,
                "programme_belonging": row.programme_belonging,
            }
            for row in roster_rows
        }
        child_by_uid = {
            row["child_uid"]: {
                "full_name": row["full_name"],
                "mcode": row["mcode"],
                "first_name": row["first_name"],
                "surname": row["surname"],
                "gender": row["gender"],
            }
            for row in CanonicalChild.objects.values(
                "child_uid", "full_name", "mcode", "first_name", "surname", "gender"
            )
        }
        assessment_fields = [
            "source_airtable_id",
            "child_uid",
            "year",
            "term",
            "total_raw",
            "child_id",
            *(component.model_field for component in COMPONENTS),
        ]
        assessments = list(
            NumeracyAssessment2026.objects.filter(
                is_active=True, year=2026, term__in=TERM_PREFIX
            ).values(*assessment_fields)
        )
        frame, meta = build_wide_frame(assessments, roster_by_uid, child_by_uid)
        identity_issues = [
            {
                "source_airtable_id": row.source_airtable_id,
                "child_uid": row.child_uid,
                "year": 2026,
                "term": "roster",
                "issue_code": "UNRESOLVED_ROSTER_UID",
                "component": "",
                "value": "",
                "maximum": "",
            }
            for row in roster_rows
            if row.child_id is None
        ]
        identity_issues.extend(
            {
                "source_airtable_id": row["source_airtable_id"],
                "child_uid": row["child_uid"],
                "year": row["year"],
                "term": row["term"],
                "issue_code": "UNRESOLVED_ASSESSMENT_UID",
                "component": "",
                "value": "",
                "maximum": "",
            }
            for row in assessments
            if row.get("child_uid") and row.get("child_id") is None
        )
        if identity_issues:
            meta["issues"].extend(identity_issues)
            meta["issues"].sort(
                key=lambda issue: (
                    str(issue.get("issue_code")),
                    str(issue.get("source_airtable_id")),
                )
            )
            meta["issue_counts"] = issue_counts(meta["issues"])
            meta["blocking_issue_count"] += len(identity_issues)
        summary = build_quality_summary(frame, meta)
        self.stdout.write(
            f"rows={len(frame)} issues={meta['issue_counts']} "
            f"off_roster={meta['off_roster_assessments']} "
            f"unresolved_roster={len(meta['unresolved_roster_uids'])}"
        )

        out = Path(options["out"]).expanduser().resolve()
        exception_path = out.with_name("2026_numeracy_quality_exceptions.csv")
        summary_path = out.with_name("2026_numeracy_quality_summary.json")
        if meta["issues"]:
            exception_path.parent.mkdir(parents=True, exist_ok=True)
            with exception_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=EXCEPTION_FIELDS)
                writer.writeheader()
                writer.writerows(
                    {key: issue.get(key, "") for key in EXCEPTION_FIELDS}
                    for issue in meta["issues"]
                )
            self.stdout.write(f"Exception report: {exception_path}")

        if options["dry_run"]:
            self.stdout.write("DRY RUN: parquet not written")
            return
        if frame.empty:
            raise CommandError("Cannot publish an empty numeracy parquet")
        missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
        if missing:
            raise CommandError(f"Missing required columns: {missing}")
        if not frame["child_uid"].is_unique:
            raise CommandError("Parquet child_uid rows are not unique")
        if len(frame) != len(roster_by_uid):
            raise CommandError("Roster and parquet row counts differ")
        if out.parent != (STREAMLIT_ROOT / "data" / "parquet" / "raw").resolve():
            raise CommandError(f"Output must be the Streamlit raw parquet directory: {out.parent}")

        out.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temp_name = tempfile.mkstemp(
            prefix=f".{out.stem}.", suffix=".parquet.tmp", dir=out.parent
        )
        os.close(descriptor)
        try:
            frame.to_parquet(temp_name, index=False)
            os.replace(temp_name, out)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        descriptor, temp_name = tempfile.mkstemp(
            prefix=f".{summary_path.stem}.", suffix=".json.tmp", dir=out.parent
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(summary, handle, indent=2, sort_keys=True)
                handle.write("\n")
            os.replace(temp_name, summary_path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        self.stdout.write(self.style.SUCCESS(f"Wrote {out}"))
        self.stdout.write(self.style.SUCCESS(f"Wrote {summary_path}"))
