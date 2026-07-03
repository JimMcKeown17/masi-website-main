import csv
import os
from pathlib import Path
import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from api.models import LiteracyAssessment2026, OnTheProgramme2026, CanonicalChild, AirtableSyncLog
from api.literacy_2026_grades import SKILLS, normalize_grade, grade_is_fallback
from api.literacy_2026_dedupe import SKILL_MODEL_FIELDS, assessment_row, dedupe, pick_winner

TERM_TO_PREFIX = {"Jan": "Jan", "Jun": "June"}
IDENTITY_COVERAGE_MIN = 0.95
DUP_REJECT_MAX = 0
REQUIRED_SYNCS = ("literacy_assessments_2026", "on_the_programme_2026")

# R2-1: resolve to the SIBLING Streamlit repo. From this file:
# parents[0]=commands [1]=management [2]=api [3]=Masi Web Main [4]=backend
# [5]=Masi_Website_2026 [6]=/Users/jimmckeown/Development
STREAMLIT_ROOT = Path(__file__).resolve().parents[6] / "Masi_Data_Site" / "masi_data_streamlit"
DEFAULT_OUT = STREAMLIT_ROOT / "data" / "parquet" / "raw" / "2026_literacy_midline.parquet"



def build_wide_frame(assessments, roster_by_uid, child_by_uid):
    """Pivot the on-programme cohort's 2026 Jan/Jun assessments long->wide. Returns (DataFrame, meta).

    Rows are the ENTIRE active on-programme roster (R3-1) — one per roster child, whether or not they
    were assessed. Unassessed children carry null Jan/June scores. Identity coverage is therefore
    computed over the full roster cohort (the denominator the reconcile's roster_count check expects).
    """
    in_scope = [a for a in assessments
                if a["year"] == 2026 and a["term"] in TERM_TO_PREFIX and a["child_uid"] in roster_by_uid]
    winners, dup_exceptions = dedupe(in_scope)
    hard_exceptions = [e for e in dup_exceptions if e["reason"] == "unresolved_tie"]
    reject_exceptions = [e for e in dup_exceptions if e["reason"] == "duplicate_more_complete_rejected"]

    uids = sorted(roster_by_uid.keys())   # the roster cohort, not just assessed children
    rows, grade_fallbacks, identified = [], 0, 0
    for uid in uids:
        child = child_by_uid.get(uid, {})
        roster = roster_by_uid.get(uid, {})
        jun = winners.get((uid, "Jun"))
        jan = winners.get((uid, "Jan"))
        raw_grade = roster.get("grade") or (jun or jan or {}).get("grade")
        if grade_is_fallback(raw_grade):
            grade_fallbacks += 1
        full_name = child.get("full_name")
        if full_name:
            identified += 1
        row = {
            "child_uid": uid,
            "Full Name": full_name,
            "Mcode": child.get("mcode"),
            "Surname": child.get("surname"),
            "Name": child.get("first_name"),
            "Gender": child.get("gender"),
            "School": roster.get("school"),
            "Mentor": roster.get("mentor"),
            "On the Programme": "Yes" if roster.get("on_programme") else "No",
            "Grade": normalize_grade(raw_grade),
            "Language": (jun or jan or {}).get("language"),
        }
        for term, prefix in TERM_TO_PREFIX.items():
            a = winners.get((uid, term))
            for skill in SKILLS:
                row[f"{prefix} - {skill}"] = a["scores"].get(skill) if a else None
            row[f"{prefix} - Total"] = a.get("total") if a else None
        rows.append(row)
    coverage = (identified / len(rows)) if rows else 1.0
    meta = {"identity_coverage": coverage, "dup_exceptions": dup_exceptions,
            "hard_exceptions": hard_exceptions, "reject_exceptions": reject_exceptions,
            "grade_fallbacks": grade_fallbacks,
            "unresolved_uids": [uid for uid in uids if not child_by_uid.get(uid, {}).get("full_name")]}
    return pd.DataFrame(rows), meta


class Command(BaseCommand):
    help = "Export the 2026 midline literacy wide parquet for the Streamlit portal"

    def add_arguments(self, parser):
        parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output parquet path")
        parser.add_argument("--dry-run", action="store_true", help="Build frame, print QA, do not write")
        parser.add_argument("--force", action="store_true", help="Skip the sync-freshness gate (local only)")
        parser.add_argument("--allow-dup-exceptions", action="store_true",
                            help="Write parquet even if unresolved duplicate ties exist")

    def _assert_synced(self):
        for sync_type in REQUIRED_SYNCS:
            last = (AirtableSyncLog.objects.filter(sync_type=sync_type)
                    .order_by("-started_at").first())     # R4: the LATEST attempt, success or not
            if last is None or not last.success or last.completed_at is None:
                raise CommandError(
                    f"Latest '{sync_type}' sync is missing, incomplete, or failed — re-run it before "
                    f"exporting (or --force). A newer failed sync is NOT masked by an older success.")
            details = last.details or {}
            if details.get("retire_skipped") or details.get("dup_uid_skipped"):   # R3-4 / R4
                raise CommandError(
                    f"Latest '{sync_type}' sync flagged retire_skipped={details.get('retire_skipped', 0)} / "
                    f"dup_uid_skipped={details.get('dup_uid_skipped', 0)} — resolve (verify a full pull / fix "
                    f"duplicate roster child_uids in Airtable) and re-run before exporting (or --force).")

    def handle(self, *args, **options):
        if not options["force"]:
            self._assert_synced()
        roster_by_uid = {
            r.child_uid: dict(mentor=r.mentor, school=r.school, grade=r.grade, on_programme=r.on_the_programme)
            for r in OnTheProgramme2026.objects.filter(is_active=True)
        }
        child_by_uid = {
            c["child_uid"]: dict(full_name=c["full_name"], mcode=c["mcode"],
                                 first_name=c["first_name"], surname=c["surname"], gender=c["gender"])
            for c in CanonicalChild.objects.values("child_uid", "full_name", "mcode",
                                                    "first_name", "surname", "gender")
        }
        qs = LiteracyAssessment2026.objects.filter(year=2026, term__in=["Jan", "Jun"], is_active=True)
        assessments = [assessment_row(a) for a in qs]
        df, meta = build_wide_frame(assessments, roster_by_uid, child_by_uid)
        matched = df[df["Jan - Letter Sounds"].notna() & df["June - Letter Sounds"].notna()] if not df.empty else df
        self.stdout.write(self.style.SUCCESS(
            f"Rows: {len(df)} | Jan+Jun matched (Letter Sounds): {len(matched)} | "
            f"identity_coverage: {meta['identity_coverage']:.3f} | "
            f"dup_exceptions: {len(meta['dup_exceptions'])} "
            f"(hard ties: {len(meta['hard_exceptions'])}, dup-rejected: {len(meta['reject_exceptions'])}) | "
            f"grade_fallbacks: {meta['grade_fallbacks']}"))

        out = options["out"]
        exceptions_csv = os.path.join(os.path.dirname(out), "2026_literacy_dedupe_exceptions.csv")
        if meta["dup_exceptions"]:
            # Only write into a directory that already exists, or into the real Streamlit repo
            # (R2-1) — never create a phantom directory tree at a default path that doesn't
            # resolve on this machine, including during --dry-run.
            if os.path.isdir(os.path.dirname(exceptions_csv)) or os.path.isdir(STREAMLIT_ROOT):
                os.makedirs(os.path.dirname(exceptions_csv), exist_ok=True)
                with open(exceptions_csv, "w", newline="") as fh:
                    w = csv.DictWriter(fh, fieldnames=["child_uid", "term", "reason", "winner", "n"])
                    w.writeheader()
                    for e in meta["dup_exceptions"]:
                        w.writerow({"child_uid": e["key"][0], "term": e["key"][1],
                                    "reason": e["reason"], "winner": e["winner"], "n": e["n"]})
                self.stdout.write(self.style.WARNING(f"  wrote dedupe exceptions -> {exceptions_csv}"))
            else:
                self.stdout.write(self.style.WARNING(
                    f"  {len(meta['dup_exceptions'])} dedupe exceptions NOT written — target dir "
                    f"{os.path.dirname(exceptions_csv)} does not exist (pass --out or create the "
                    f"Streamlit repo at {STREAMLIT_ROOT})."))

        # --- Gates (skipped only in dry-run) ---
        if not options["dry_run"]:
            if meta["identity_coverage"] < IDENTITY_COVERAGE_MIN:
                raise CommandError(
                    f"Identity coverage {meta['identity_coverage']:.3f} < {IDENTITY_COVERAGE_MIN}. "
                    f"{len(meta['unresolved_uids'])} child_uids unresolved in CanonicalChild "
                    f"(first 10: {meta['unresolved_uids'][:10]}). Reconcile canonical children or build "
                    f"the base-local Child DB fallback (Appendix A).")
            if meta["hard_exceptions"] and not options["allow_dup_exceptions"]:
                raise CommandError(
                    f"{len(meta['hard_exceptions'])} unresolved duplicate ties — review "
                    f"{exceptions_csv} then re-run with --allow-dup-exceptions if intended.")
            if len(meta["reject_exceptions"]) > DUP_REJECT_MAX and not options["allow_dup_exceptions"]:
                raise CommandError(
                    f"{len(meta['reject_exceptions'])} groups where a Duplicate-flagged row was more "
                    f"complete than the winner — review {exceptions_csv} (a corrected row may still be "
                    f"flagged Duplicate) then re-run with --allow-dup-exceptions if intended.")
            if not os.path.isdir(STREAMLIT_ROOT):
                raise CommandError(
                    f"Streamlit repo not found at {STREAMLIT_ROOT} — pass --out explicitly to the real "
                    f"data/parquet/raw path.")

        if options["dry_run"]:
            self.stdout.write("DRY RUN — not writing.")
            return
        os.makedirs(os.path.dirname(out), exist_ok=True)
        df.to_parquet(out, index=False)
        self.stdout.write(self.style.SUCCESS(f"Wrote {out}"))
