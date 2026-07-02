import os
import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from dotenv import load_dotenv
from api.literacy_2026_grades import SKILLS
# Reuse the export's winner POLICY (pick_winner) + the sync's generic value coercers (_dt/_clean_status),
# but NOT the sync's field mapping — the Airtable->fields mapping is re-derived here independently (R3-2/R4).
from api.management.commands.export_literacy_2026_parquet import DEFAULT_OUT, pick_winner
from api.management.commands.sync_airtable_literacy_assessments_2026 import (
    Command as AssessSync, _dt, _clean_status,
)
from api.management.commands.sync_airtable_on_the_programme_2026 import Command as RosterSync

REQUIRED_COLUMNS = (
    ["child_uid", "Full Name", "Mcode", "Surname", "Name", "Gender",
     "School", "Grade", "Language", "Mentor", "On the Programme"]
    + [f"{p} - {s}" for p in ("Jan", "June") for s in SKILLS]
    + ["Jan - Total", "June - Total"]
)
# Expected lower bounds for the verified 2026 cohort (~1,388 roster, ~1,161 Jun-assessed). These are
# sanity FLOORS well below the real counts but far above any truncated/first-page/wrong-table pull
# (Airtable pages at 100), so a 1-row or single-page source fails acceptance (R5). Revisit if the
# cohort size changes materially.
EXPECTED_ROSTER_MIN = 1000
EXPECTED_JUN_MIN = 800


def _raw_uid(v):
    if isinstance(v, list):
        return v[0] if v else None
    return v or None


def _raw_num(v):
    if isinstance(v, dict) or v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _raw_assessment(rec):
    """Parse a raw Airtable assessment record into the export's assessment shape — independently of
    the sync's extract_row, but suitable for the export's pick_winner policy (R4)."""
    f = rec.get("fields", {})
    return dict(
        child_uid=_raw_uid(f.get("Child UID")),
        term=f.get("Term"),
        year=_raw_num(f.get("Year")),
        scores={s: _raw_num(f.get(s)) for s in SKILLS},
        duplicate_status=_clean_status(f.get("Duplicate?") or f.get("Duplicate Status")),
        source_created_time=_dt(rec.get("createdTime")),
        source_modified_time=_dt(f.get("Last Modified Time") or f.get("Last Modified")),
        source_airtable_id=rec.get("id"),
    )


def airtable_aggregates(assessment_records, roster_records):
    """Independent aggregates from RAW Airtable fields, roster-scoped, using the SAME winner policy
    as the export (pick_winner) so the Jan mean matches the export's chosen rows exactly (R4). Pure."""
    roster_uids = set()
    for r in roster_records:
        uid = _raw_uid(r.get("fields", {}).get("Child UID"))
        if uid:
            roster_uids.add(uid)
    jan_winner, jun_winner = {}, {}
    for rec in assessment_records:
        a = _raw_assessment(rec)
        if not a["child_uid"] or a["year"] != 2026 or a["child_uid"] not in roster_uids:
            continue
        bucket = jan_winner if a["term"] == "Jan" else (jun_winner if a["term"] == "Jun" else None)
        if bucket is None:
            continue
        cur = bucket.get(a["child_uid"])
        bucket[a["child_uid"]] = a if cur is None else pick_winner([cur, a])
    jan_vals = [w["scores"]["Letter Sounds"] for w in jan_winner.values()
                if w["scores"]["Letter Sounds"] is not None]
    # Count June WINNERS with a non-null Letter Sounds, so this matches the parquet's
    # `June - Letter Sounds` notna count exactly (R6 uses exact equality on this integer).
    jun_ls_count = sum(1 for w in jun_winner.values() if w["scores"]["Letter Sounds"] is not None)
    return {"roster_count": len(roster_uids),
            "jun_assessed_on_roster": jun_ls_count,
            "mean_jan_letter_sounds": (sum(jan_vals) / len(jan_vals)) if jan_vals else 0.0}


def compare(airtable_stats, parquet_df, tol=0.02, min_roster=1, min_jun=0):
    """Assert the parquet matches INDEPENDENT Airtable aggregates AND satisfies the column contract
    and lower bounds. A schema-wrong/empty parquet, empty source, or a source below the expected
    floor (a 1-row/first-page/wrong-table pull) FAILS (R4-crit / R5). Pure + unit-tested.
    Callers pass the production floors (EXPECTED_ROSTER_MIN/EXPECTED_JUN_MIN); the tiny defaults
    keep unit fixtures usable."""
    checks = []

    def flag(name, got, want, ok):
        checks.append({"check": name, "got": got, "want": want, "ok": ok})

    def approx(name, got, want, rel=tol):
        flag(name, got, want, want != 0 and abs(got - want) / abs(want) <= rel)  # 0 expected => FAIL

    missing = [c for c in REQUIRED_COLUMNS if c not in parquet_df.columns]
    flag("required_columns", f"{len(missing)} missing {missing[:3]}", 0, not missing)
    flag("roster_source_floor", airtable_stats["roster_count"], f">={min_roster}",
         airtable_stats["roster_count"] >= min_roster)
    flag("jun_assessed_floor", airtable_stats["jun_assessed_on_roster"], f">={min_jun}",
         airtable_stats["jun_assessed_on_roster"] >= min_jun)
    flag("nonempty_parquet", len(parquet_df), ">0", len(parquet_df) > 0)
    if not missing and len(parquet_df) > 0:
        # Integer structural counts must match EXACTLY — the parquet is one row per active roster
        # child and both sides derive from Airtable, so a 2% band could hide truncation/over-
        # inclusion (R6). Tolerance is reserved for the float mean only.
        flag("roster_row_count", len(parquet_df), airtable_stats["roster_count"],
             len(parquet_df) == airtable_stats["roster_count"])
        jun_got = int(parquet_df["June - Letter Sounds"].notna().sum())
        flag("jun_assessed_exact", jun_got, airtable_stats["jun_assessed_on_roster"],
             jun_got == airtable_stats["jun_assessed_on_roster"])
        got_mean = float(parquet_df["Jan - Letter Sounds"].dropna().mean())
        approx("mean_jan_letter_sounds", got_mean, airtable_stats["mean_jan_letter_sounds"], rel=0.05)
        off = int((parquet_df["On the Programme"] != "Yes").sum())
        flag("all_on_programme", off, 0, off == 0)
    return {"ok": all(c["ok"] for c in checks), "checks": checks}


class Command(BaseCommand):
    help = "Reconcile the exported 2026 parquet against INDEPENDENT Airtable aggregates."

    def add_arguments(self, parser):
        parser.add_argument("--parquet", default=str(DEFAULT_OUT))

    def handle(self, *args, **options):
        path = options["parquet"]
        if not os.path.exists(path):
            raise CommandError(f"Parquet not found: {path} — run export_literacy_2026_parquet first.")
        df = pd.read_parquet(path)
        load_dotenv()
        token = os.getenv("AIRTABLE_TOKEN")
        a_base = os.getenv("AIRTABLE_LITERACY_ASSESSMENTS_2026_BASE_ID")
        a_table = os.getenv("AIRTABLE_LITERACY_ASSESSMENTS_2026_TABLE_ID")
        r_base = os.getenv("AIRTABLE_ON_THE_PROGRAMME_2026_BASE_ID")
        r_table = os.getenv("AIRTABLE_ON_THE_PROGRAMME_2026_TABLE_ID")
        if not all([token, a_base, a_table, r_base, r_table]):
            raise CommandError("Missing Airtable env vars for reconciliation.")
        a_records = AssessSync().fetch_from_airtable(a_base, a_table, token)
        r_records = RosterSync().fetch_from_airtable(r_base, r_table, token)
        stats = airtable_aggregates(a_records, r_records)
        result = compare(stats, df, min_roster=EXPECTED_ROSTER_MIN, min_jun=EXPECTED_JUN_MIN)
        for c in result["checks"]:
            style = self.style.SUCCESS if c["ok"] else self.style.ERROR
            self.stdout.write(style(f"  [{'OK' if c['ok'] else 'FAIL'}] {c['check']}: got={c['got']} want={c['want']}"))
        if not result["ok"]:
            raise CommandError("Reconciliation FAILED (parquet vs INDEPENDENT Airtable aggregates).")
        self.stdout.write(self.style.SUCCESS("Reconciliation passed."))
