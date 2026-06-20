"""Seed/refresh management's planned Zazi iZandi youth per school.

Source: static/data/zz_youth_school_allocations.csv -- a staff-maintained list of
planned Zazi iZandi youth per (primary) school: one `School name,Allocated` row
each. School names were fuzzy-matched to canonical School.school_uid and every
match reviewed by Jim (2026-06-20); the reviewed map is FROZEN below so the seed is
deterministic and auditable -- it never re-runs fuzzy matching against a moving
school table. "Re" is the staff's shorthand for Republic Primary (Jim-confirmed).

Scope (Jim, 2026-06-20): UPSERT ONLY. Writes youth_planned (zazi_izandi programme)
for the schools in the sheet and leaves every OTHER school's existing zazi_izandi
youth_planned untouched -- it never clears off-sheet allocations (the ~19 ECD ZZ
allocations and off-sheet primaries like Dumani/Isaac Booi/Seyisi stay as-is). The
sheet's explicit 0s (Imbasa, C W Hendrickse, Ilitha) are written as a planned 0.

youth_planned is human-owned, so the nightly grid cron never overwrites it. The
seed is idempotent and re-runnable; --dry-run prints the plan without writing.

Run on Render after deploy:  python manage.py seed_zazi_planned_youth
"""
import csv
import os
import re

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from api.school_programme import ZAZI_IZANDI, create_cell

# Jim-approved 2026-06-20. Keyed normalized-CSV-name -> School.school_uid.
# Frozen on purpose: a fuzzy re-match against a changing school table could
# silently pick a different school. Regenerate deliberately, never at runtime.
# (normalize = strip, lower, drop apostrophes, non-alphanumerics -> single space.)
ZAZI_YOUTH_NAME_TO_UID = {
    "abraham levy": "SCH-00144",
    "canzibe": "SCH-00090",
    "coega": "SCH-00190",
    "daniels": "SCH-00098",
    "emfundweni": "SCH-00210",
    "frank joubert": "SCH-00180",
    "emzomncane": "SCH-00099",
    "jarvis gqamlana": "SCH-00049",
    "enkululekweni": "SCH-00075",      # DB: Enkulekweni
    "lamani": "SCH-00067",
    "enqileni": "SCH-00097",
    "funimfundo": "SCH-00062",
    "samuel nongogo": "SCH-00085",
    "imbasa": "SCH-00066",             # sheet allocates 0
    "kayser ngxwana": "SCH-00065",
    "cebelihle": "SCH-00068",
    "melisizwe": "SCH-00060",
    "mnqophiso": "SCH-00168",
    "nkuthalo": "SCH-00074",
    "nxanelwimfundo": "SCH-00059",
    "ilitha": "SCH-00105",             # sheet allocates 0
    "j k zondi": "SCH-00169",
    "machiu": "SCH-00179",
    "malabar": "SCH-00181",
    "sipho hashe": "SCH-00147",
    "soweto on sea": "SCH-00151",
    "re": "SCH-00118",                 # Republic Primary (Jim-confirmed)
    "sanctor": "SCH-00154",
    "vukanibantu": "SCH-00080",
    "walmer": "SCH-00200",
    "alfonso arries": "SCH-00142",
    "boet jegels": "SCH-00159",
    "cedarberg": "SCH-00110",
    "emafini": "SCH-00073",
    "fernwood park": "SCH-00164",
    "dr a w habelgaan": "SCH-00191",   # DB: Dr A W Habelgaarn
    "spencer mabija": "SCH-00093",
    "kleinskool community": "SCH-00137",  # DB: Kleinskool
    "c w hendrickse": "SCH-00122",     # sheet allocates 0
    "st joseph": "SCH-00124",          # DB: St Joseph'S
    "amanzi": "SCH-00165",
    "ilinge": "SCH-00175",
    "james ntungwana": "SCH-00116",
    "magqabi": "SCH-00129",
    "mjuleni junior": "SCH-00177",     # DB: Mjuleni
    "mthonjeni senior": "SCH-00158",   # DB: Mthonjeni
    "nomathamsanqa": "SCH-00167",
    "nosipho": "SCH-00162",
    "phakamile": "SCH-00285",
    "sikhothina": "SCH-00125",
    "uitenhage": "SCH-00143",
    "kwanoxolo": "SCH-00082",
    "sapphire": "SCH-00051",
    "strelitzia": "SCH-00102",
    "bethvale": "SCH-00072",
    "garret": "SCH-00088",             # DB: Garrett
    "emsengeni": "SCH-00076",
    "esitiyeni": "SCH-00198",
    "w b tshume": "SCH-00150",         # DB: W B Tshume
    "diaz farm school": "SCH-00189",   # DB: Dias
    "phakama": "SCH-00104",
}

DEFAULT_CSV = os.path.join(
    settings.BASE_DIR, "static", "data", "zz_youth_school_allocations.csv"
)


def _norm(name):
    s = (name or "").strip().lower().replace("'", "")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _read_allocations(path):
    """Yield (raw_name, planned, valid) for each non-blank, non-header sheet row.

    The sheet is `School name,Allocated` with leading/trailing blank rows. A row
    whose Allocated is not an integer is returned valid=False so the caller can
    surface it rather than silently writing a wrong 0.
    """
    out = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.reader(f):
            if not row or len(row) < 2:
                continue
            name = (row[0] or "").strip()
            alloc = (row[1] or "").strip()
            if not name or name.lower() == "school name":
                continue
            if alloc.isdigit():
                out.append((name, int(alloc), True))
            else:
                out.append((name, alloc, False))
    return out


class Command(BaseCommand):
    help = ("Seed/refresh planned Zazi iZandi youth from "
            "zz_youth_school_allocations.csv into youth_planned (upsert only).")

    def add_arguments(self, parser):
        parser.add_argument("--year", type=int, default=2026,
                            help="Grid year to seed (default: 2026).")
        parser.add_argument("--csv", default=DEFAULT_CSV,
                            help="Path to the Zazi planned-youth CSV.")
        parser.add_argument("--dry-run", action="store_true",
                            help="Print the plan without writing.")

    def handle(self, *args, **options):
        year = options["year"]
        allocations = _read_allocations(options["csv"])

        plan = []      # (uid, planned, raw_name)
        unmapped = []  # (raw_name, planned)
        invalid = []   # (raw_name, raw_alloc)
        for raw_name, planned, valid in allocations:
            if not valid:
                invalid.append((raw_name, planned))
                continue
            uid = ZAZI_YOUTH_NAME_TO_UID.get(_norm(raw_name))
            if uid is None:
                unmapped.append((raw_name, planned))
            else:
                plan.append((uid, planned, raw_name))

        self.stdout.write(
            f"Zazi planned-youth seed for {year}: {len(plan)} schools "
            f"from {len(allocations)} sheet rows (upsert only -- off-sheet "
            f"zazi_izandi allocations left untouched)."
        )
        if invalid:
            self.stdout.write(self.style.WARNING(
                f"{len(invalid)} row(s) with a non-integer Allocated (skipped):"
            ))
            for raw_name, raw_alloc in invalid:
                self.stdout.write(f"  - {raw_name!r} -> {raw_alloc!r}")
        if unmapped:
            self.stdout.write(self.style.WARNING(
                f"{len(unmapped)} sheet row(s) with NO school mapping (skipped):"
            ))
            for raw_name, planned in unmapped:
                self.stdout.write(f"  - {raw_name!r} (planned={planned})")

        if options["dry_run"]:
            for uid, planned, raw_name in plan:
                self.stdout.write(
                    f"  {uid}  zazi_izandi  planned={planned:<3} ({raw_name})"
                )
            self.stdout.write(self.style.NOTICE("Dry run -- nothing written."))
            return

        updated = unchanged = 0
        with transaction.atomic():
            for uid, planned, raw_name in plan:
                row = create_cell(uid, ZAZI_IZANDI, year, user=None)
                if row.youth_planned == planned:
                    unchanged += 1
                    continue
                row.youth_planned = planned
                row.save(update_fields=["youth_planned", "updated_at"])
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Done. {updated} youth_planned values written, {unchanged} already correct."
        ))
