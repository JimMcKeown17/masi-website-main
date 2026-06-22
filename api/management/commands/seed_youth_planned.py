"""One-time seed of management's planned-youth allocations into the grid.

Source: static/data/2026_feb_youth_numbers.csv -- a staff-maintained matrix of
planned youth per school x programme. School names were fuzzy-matched to canonical
School.school_uid and the matches reviewed by Jim (2026-06-20); the reviewed map
is FROZEN below so the seed is deterministic and auditable -- it never re-runs
fuzzy matching against a moving school table. "Wittekleibosch" had no canonical
match and is intentionally absent (it is reported, not silently dropped).

youth_planned is human-owned, so the nightly grid cron never overwrites it. The
seed is idempotent and re-runnable; --dry-run prints the plan without writing.
Cells that don't yet exist are created with the same system config the cron /
"click to add" path uses (via create_cell), so a planned-but-unstaffed programme
surfaces as a vacancy (youth_active 0 against a positive youth_planned).

Run once on Render after deploy:  python manage.py seed_youth_planned
"""
import csv
import os

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from api.school_programme import create_cell, parse_planned_youth

# Jim-approved 2026-06-20. Keyed (csv_name_lower, bucket) -> School.school_uid.
# Frozen on purpose: a fuzzy re-match against a changing school table could
# silently pick a different school. Regenerate deliberately, never at runtime.
YOUTH_SEED_NAME_TO_UID = {
    ('arise and shine', 'ECD'): 'SCH-00256',
    ('baby day care', 'ECD'): 'SCH-00218',
    ('bambino', 'ECD'): 'SCH-00298',
    ('bavumeleni preschool', 'ECD'): 'SCH-00053',
    ('bright angels', 'ECD'): 'SCH-00299',
    ('dorothy', 'ECD'): 'SCH-00318',
    ('ekhaya preschool', 'ECD'): 'SCH-00282',
    ('emanuel day care', 'ECD'): 'SCH-00091',
    ('emfundweni', 'ECD'): 'SCH-00213',
    ('ezibeleni', 'ECD'): 'SCH-00231',
    ('future angels', 'ECD'): 'SCH-00052',
    ('green apple', 'ECD'): 'SCH-00301',
    ('ilitha lethu day care', 'ECD'): 'SCH-00094',
    ('jongi ingomso', 'ECD'): 'SCH-00267',
    ('jongilanga', 'ECD'): 'SCH-00290',
    ('kamvalethu', 'ECD'): 'SCH-00214',
    ('khazimla', 'ECD'): 'SCH-00208',  # consolidated onto "Khazimla Pre-School" (was SCH-00248, retired)
    ('kids college', 'ECD'): 'SCH-00056',
    ('koester day care', 'ECD'): 'SCH-00106',
    ('kokkewiet', 'ECD'): 'SCH-00292',
    ('lavela', 'ECD'): 'SCH-00215',
    ('libhongolethu', 'ECD'): 'SCH-00061',
    ('lihlombe', 'ECD'): 'SCH-00207',
    ('likhaya', 'ECD'): 'SCH-00216',
    ('lithemba', 'ECD'): 'SCH-00309',
    ('living ubuntu', 'ECD'): 'SCH-00316',
    ('livuse preschool', 'ECD'): 'SCH-00079',
    ('lukhanyiso', 'ECD'): 'SCH-00229',
    ('lukhanyo creche', 'ECD'): 'SCH-00063',
    ('malukhanye', 'ECD'): 'SCH-00228',
    ('msobomvu', 'ECD'): 'SCH-00297',
    ('nceduluntu', 'ECD'): 'SCH-00293',
    ('njongozabantu', 'ECD'): 'SCH-00081',
    ('nobandla', 'ECD'): 'SCH-00320',
    ('noluthando', 'ECD'): 'SCH-00321',
    ('nomtha', 'ECD'): 'SCH-00308',
    ('nonqkubela', 'ECD'): 'SCH-00315',
    ('nosandla', 'ECD'): 'SCH-00206',
    ('paulos oyungcwele', 'ECD'): 'SCH-00296',
    ('qaqawuli godolozi', 'ECD'): 'SCH-00302',
    ('qhamani', 'ECD'): 'SCH-00212',
    ('sakha abantwana', 'ECD'): 'SCH-00100',
    ('sifunimfundo', 'ECD'): 'SCH-00314',
    ('sinethemba', 'ECD'): 'SCH-00291',
    ('sisonke', 'ECD'): 'SCH-00313',
    ('siyabulela preschool', 'ECD'): 'SCH-00092',
    ('sizamokuhle', 'ECD'): 'SCH-00221',
    ('sophakama', 'ECD'): 'SCH-00219',
    ('st mary magaldene', 'ECD'): 'SCH-00103',
    ('sume center', 'ECD'): 'SCH-00286',
    ('takalani', 'ECD'): 'SCH-00211',
    ('thembalethu preschool', 'ECD'): 'SCH-00107',
    ('twinkle toes', 'ECD'): 'SCH-00266',
    ('umzamomhle', 'ECD'): 'SCH-00273',
    ('vukani', 'ECD'): 'SCH-00311',
    ('zizamele', 'ECD'): 'SCH-00304',
    ('aaron gqadu', 'Primary'): 'SCH-00276',
    ('astra', 'Primary'): 'SCH-00278',
    ('ben nyathi', 'Primary'): 'SCH-00203',
    ('ben sinuka', 'Primary'): 'SCH-00289',
    ('bethelsdorp', 'Primary'): 'SCH-00087',
    ('bethvale', 'Primary'): 'SCH-00072',
    ('bj mnyanda', 'Primary'): 'SCH-00057',
    ('canzibe', 'Primary'): 'SCH-00090',
    ('cebelihle', 'Primary'): 'SCH-00068',
    ('charles duna', 'Primary'): 'SCH-00281',
    ('clarkson', 'Primary'): 'SCH-00319',
    ('daniels', 'Primary'): 'SCH-00098',
    ('dias farm school', 'Primary'): 'SCH-00189',
    ('dumani', 'Primary'): 'SCH-00280',
    ('ebhongweni', 'Primary'): 'SCH-00288',
    ('elufefeni', 'Primary'): 'SCH-00274',
    ('emafini', 'Primary'): 'SCH-00073',
    ('emfundweni', 'Primary'): 'SCH-00210',
    ('empumalanga', 'Primary'): 'SCH-00305',
    ('emsengeni', 'Primary'): 'SCH-00076',
    ('emzimhlophe', 'Primary'): 'SCH-00096',
    ('emzomncane', 'Primary'): 'SCH-00099',
    ('enkululekweni', 'Primary'): 'SCH-00075',
    ('esitiyeni', 'Primary'): 'SCH-00198',
    ('fumisukoma', 'Primary'): 'SCH-00283',
    ('garrett', 'Primary'): 'SCH-00088',
    ('gertrude', 'Primary'): 'SCH-00275',
    ('isaac booi', 'Primary'): 'SCH-00277',
    ('jarvis gqamlana', 'Primary'): 'SCH-00049',
    ('kama', 'Primary'): 'SCH-00071',
    ('kk ncwane', 'Primary'): 'SCH-00089',
    ('kwanoxolo', 'Primary'): 'SCH-00082',
    ('lingelethu', 'Primary'): 'SCH-00322',
    ('mboniselo', 'Primary'): 'SCH-00101',
    ('melisizwe', 'Primary'): 'SCH-00060',
    ('molefe', 'Primary'): 'SCH-00284',
    ('msobomvu', 'Primary'): 'SCH-00323',
    ('phakama', 'Primary'): 'SCH-00104',
    ('sandwater', 'Primary'): 'SCH-00306',
    ('sapphire', 'Primary'): 'SCH-00051',
    ('seyisi', 'Primary'): 'SCH-00279',
    ('sivuyiseni', 'Primary'): 'SCH-00204',
    ('spencer', 'Primary'): 'SCH-00093',
    ('steven mazungula', 'Primary'): 'SCH-00050',
    ('strelitzia', 'Primary'): 'SCH-00102',
    ('wb tshume', 'Primary'): 'SCH-00150',
}

DEFAULT_CSV = os.path.join(
    settings.BASE_DIR, "static", "data", "2026_feb_youth_numbers.csv"
)


class Command(BaseCommand):
    help = "Seed management's planned-youth allocations (Feb-2026 CSV) into youth_planned."

    def add_arguments(self, parser):
        parser.add_argument("--year", type=int, default=2026,
                            help="Grid year to seed (default: 2026).")
        parser.add_argument("--csv", default=DEFAULT_CSV,
                            help="Path to the planned-youth CSV.")
        parser.add_argument("--dry-run", action="store_true",
                            help="Print the plan without writing.")

    def handle(self, *args, **options):
        year = options["year"]
        with open(options["csv"], newline="", encoding="utf-8") as f:
            aggregated = parse_planned_youth(csv.DictReader(f))

        plan = []      # (school_uid, programme, planned, csv_name, bucket)
        unmapped = []  # (csv_name, bucket, {programme: planned})
        for (name, bucket), programmes in sorted(aggregated.items()):
            uid = YOUTH_SEED_NAME_TO_UID.get((name, bucket))
            if uid is None:
                unmapped.append((name, bucket, programmes))
                continue
            for programme, planned in sorted(programmes.items()):
                plan.append((uid, programme, planned, name, bucket))

        schools = len({uid for uid, *_ in plan})
        self.stdout.write(
            f"Planned-youth seed for {year}: {len(plan)} cells across {schools} schools."
        )
        if unmapped:
            self.stdout.write(self.style.WARNING(
                f"{len(unmapped)} CSV site(s) with planned youth have NO mapping (skipped):"
            ))
            for name, bucket, programmes in unmapped:
                self.stdout.write(f"  - {name} [{bucket}] {dict(programmes)}")

        if options["dry_run"]:
            for uid, programme, planned, name, bucket in plan:
                self.stdout.write(
                    f"  {uid}  {programme:<16} planned={planned:<3} ({name} [{bucket}])"
                )
            self.stdout.write(self.style.NOTICE("Dry run -- nothing written."))
            return

        updated = unchanged = 0
        with transaction.atomic():
            for uid, programme, planned, name, bucket in plan:
                row = create_cell(uid, programme, year, user=None)
                if row.youth_planned == planned:
                    unchanged += 1
                    continue
                row.youth_planned = planned
                row.save(update_fields=["youth_planned", "updated_at"])
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Done. {updated} youth_planned values written, {unchanged} already correct."
        ))
