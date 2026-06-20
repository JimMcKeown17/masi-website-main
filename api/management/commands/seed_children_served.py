"""One-time seed of the 1000 Stories + EduTech children counts into the grid.

Source: static/data/children-per-school-1000-stories-edutech.csv -- a staff matrix
of children served per site for two MANUAL programmes (1000 Stories, EduTech).
School names were fuzzy-matched to canonical School.school_uid (bucket-constrained
ECD vs Primary) and the matches reviewed by Jim (2026-06-20); the reviewed map is
FROZEN below so the seed is deterministic and auditable -- it never re-runs fuzzy
matching against a moving school table.

children_count is human-owned for these programmes, so the nightly grid cron never
overwrites it (column-ownership rule). The seed creates the cell when it doesn't
yet exist (the same create_cell path the "click to add" button uses), which makes
the programme PRESENT at the school -- so it also appears on the youth tab as a
0/-- cell. It creates no youth job and changes no denominator. Idempotent and
re-runnable; --dry-run prints the plan without writing.

Three ECD sites in the CSV (Aaron Gqadu / Charles Duna / Seyisi) are co-located
with a same-named primary and had no ECD record. Jim added them in Airtable on
2026-06-20 (Educare/ECD suffix; the Charles Duna ECD is "Sume Centre"), with uids
SCH-00332 / SCH-00333 / SCH-00334. They are in the frozen map below, so they seed
once sync_airtable_schools has pulled them into Postgres.

Run on Render after deploy, AFTER syncing the new schools:
    python manage.py sync_airtable_schools
    python manage.py seed_children_served --dry-run   # review
    python manage.py seed_children_served
"""
import csv
import os

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from api.school_programme import create_cell, parse_children_served

# Jim-approved 2026-06-20. Keyed (csv_name_lower, bucket) -> School.school_uid.
# Frozen on purpose: a fuzzy re-match against a changing school table could
# silently pick a different school. Regenerate deliberately, never at runtime.
CHILDREN_SEED_NAME_TO_UID = {
    # --- ECDs (1000 Stories, whole-school basis) ---
    ('adcoc brighton kids', 'ECD'): 'SCH-00245',
    ('arise and shine', 'ECD'): 'SCH-00256',
    ('bambino', 'ECD'): 'SCH-00298',
    ('bavumeleni', 'ECD'): 'SCH-00053',
    ('bomi obutsha', 'ECD'): 'SCH-00257',
    ('bright angels', 'ECD'): 'SCH-00299',
    ('busy bee', 'ECD'): 'SCH-00262',
    ('cuttee babies nursery', 'ECD'): 'SCH-00232',
    ('dorcas educare centre', 'ECD'): 'SCH-00239',
    ('dorothy', 'ECD'): 'SCH-00318',
    ('early rose', 'ECD'): 'SCH-00230',
    ('ekhaya', 'ECD'): 'SCH-00282',
    ('entokozweni educare', 'ECD'): 'SCH-00247',
    ('ezibeleni', 'ECD'): 'SCH-00231',
    ('future angels', 'ECD'): 'SCH-00052',
    ('future kids educare', 'ECD'): 'SCH-00225',
    ('future stars', 'ECD'): 'SCH-00255',
    ('good hope', 'ECD'): 'SCH-00287',
    ('govan mbeki', 'ECD'): 'SCH-00223',
    ('green apple', 'ECD'): 'SCH-00301',
    ('hlumelo', 'ECD'): 'SCH-00258',
    ('holy name community', 'ECD'): 'SCH-00261',
    ('ikamvalethu', 'ECD'): 'SCH-00250',
    ('ilithalethu', 'ECD'): 'SCH-00094',
    ('isizwe sethu', 'ECD'): 'SCH-00265',
    ('jesus dominion', 'ECD'): 'SCH-00310',
    ('jongilanga', 'ECD'): 'SCH-00290',
    ('khazimla', 'ECD'): 'SCH-00248',
    ('kids college', 'ECD'): 'SCH-00056',
    ('kings and quuens', 'ECD'): 'SCH-00237',
    ('kokkewiet', 'ECD'): 'SCH-00292',
    ('kwakhanya', 'ECD'): 'SCH-00240',
    ('libhongo lwethu', 'ECD'): 'SCH-00061',
    ('linge tots', 'ECD'): 'SCH-00244',
    ('lithemba', 'ECD'): 'SCH-00309',
    ('little angels unite', 'ECD'): 'SCH-00254',
    ('little ships', 'ECD'): 'SCH-00226',
    ('living ubuntu', 'ECD'): 'SCH-00316',
    ('lukhanyiselo', 'ECD'): 'SCH-00241',
    ('lukhanyiso', 'ECD'): 'SCH-00229',
    ('luv birds day care', 'ECD'): 'SCH-00253',
    ('malikhanye day care', 'ECD'): 'SCH-00228',
    ('minnie day care', 'ECD'): 'SCH-00048',
    ('msobomvu pre-school', 'ECD'): 'SCH-00297',
    ('mzamomhle edu-care', 'ECD'): 'SCH-00294',
    ('nelisa', 'ECD'): 'SCH-00243',
    ('new brighton future kids', 'ECD'): 'SCH-00233',
    ('njongozabantu', 'ECD'): 'SCH-00081',
    ('nobandla', 'ECD'): 'SCH-00320',
    ('nolundi', 'ECD'): 'SCH-00224',
    ('noluthando', 'ECD'): 'SCH-00321',
    ('nomonde', 'ECD'): 'SCH-00238',
    ('nonkqubela', 'ECD'): 'SCH-00315',
    ('nontsapho', 'ECD'): 'SCH-00252',
    ('nosandla educare', 'ECD'): 'SCH-00206',
    ('p.g mangqana pre-school', 'ECD'): 'SCH-00260',
    ('paulos oyigcwele', 'ECD'): 'SCH-00296',
    ('qaqawuli godolozi', 'ECD'): 'SCH-00302',
    ('rock of ages', 'ECD'): 'SCH-00227',
    ('sakha abantwana', 'ECD'): 'SCH-00100',
    ('sakhuxolo educare', 'ECD'): 'SCH-00263',
    ('sekunjalo educentre', 'ECD'): 'SCH-00272',
    ('sifunimfundo', 'ECD'): 'SCH-00314',
    ('sikhulise pre-school', 'ECD'): 'SCH-00205',
    ('simanye', 'ECD'): 'SCH-00234',
    ('sinethemba', 'ECD'): 'SCH-00291',
    ('sisonke', 'ECD'): 'SCH-00313',
    ('siyazama', 'ECD'): 'SCH-00295',
    ('st magdalene', 'ECD'): 'SCH-00264',
    ('sunnyside', 'ECD'): 'SCH-00251',
    ('thanda abantwana', 'ECD'): 'SCH-00242',
    ("thandi's educare & aftercare", 'ECD'): 'SCH-00259',
    ('tinky winky day care', 'ECD'): 'SCH-00235',
    ('twinkle toes educare', 'ECD'): 'SCH-00266',
    ("umzam'omhle educare", 'ECD'): 'SCH-00273',
    ('vukani daycare', 'ECD'): 'SCH-00311',
    ('vulithemba', 'ECD'): 'SCH-00246',
    ('yomelela educare', 'ECD'): 'SCH-00236',
    ('zizamele', 'ECD'): 'SCH-00304',
    ('zukhanye', 'ECD'): 'SCH-00249',
    # --- Primaries (1000 Stories percent-of-school + EduTech whole-school) ---
    ('aaron gqadu', 'Primary'): 'SCH-00276',
    ('astra', 'Primary'): 'SCH-00278',
    ('ben sinuka', 'Primary'): 'SCH-00289',
    ('bethelsdorp', 'Primary'): 'SCH-00087',
    ('bj mnyanda', 'Primary'): 'SCH-00057',
    ('canzibe', 'Primary'): 'SCH-00090',
    ('cebelihle', 'Primary'): 'SCH-00068',
    ('charles duna', 'Primary'): 'SCH-00281',
    ('clarkson', 'Primary'): 'SCH-00319',
    ('daniels public', 'Primary'): 'SCH-00098',
    ('david vuku', 'Primary'): 'SCH-00064',
    ('dumani', 'Primary'): 'SCH-00280',
    ('ebongweni', 'Primary'): 'SCH-00288',
    ('elufefeni', 'Primary'): 'SCH-00274',
    ('emafini primary', 'Primary'): 'SCH-00073',
    ('emfundweni', 'Primary'): 'SCH-00210',
    ('empumalanga', 'Primary'): 'SCH-00305',
    ('emsengeni', 'Primary'): 'SCH-00076',
    ('emzomncane', 'Primary'): 'SCH-00099',
    ('fumisukoma', 'Primary'): 'SCH-00283',
    ('gertrude shope', 'Primary'): 'SCH-00275',
    ('isaac booi', 'Primary'): 'SCH-00277',
    ('jarvis gqamlana', 'Primary'): 'SCH-00049',
    ('kama', 'Primary'): 'SCH-00071',
    ('khanyisa', 'Primary'): 'SCH-00317',
    ('kk ncwana', 'Primary'): 'SCH-00089',
    ('kroneberg', 'Primary'): 'SCH-00077',
    ('kwanoxolo', 'Primary'): 'SCH-00082',
    ('lamani primary school', 'Primary'): 'SCH-00067',
    ('mboniselo', 'Primary'): 'SCH-00101',
    ('melisizwe', 'Primary'): 'SCH-00060',
    ('molefe', 'Primary'): 'SCH-00284',
    ('mzimhlophe', 'Primary'): 'SCH-00096',
    ('mzingisi', 'Primary'): 'SCH-00312',
    ('ntyatyambo', 'Primary'): 'SCH-00083',
    ('phakamile', 'Primary'): 'SCH-00285',
    ('sandwater', 'Primary'): 'SCH-00306',
    ('seyisi', 'Primary'): 'SCH-00279',
    ('sivuyiseni', 'Primary'): 'SCH-00204',
    ('spencer mabija', 'Primary'): 'SCH-00093',
    ('st augustines', 'Primary'): 'SCH-00303',
    ('stephen mazungula', 'Primary'): 'SCH-00050',
    ('zukisa', 'Primary'): 'SCH-00307',
    # --- ECDs co-located with a same-named primary (added in Airtable 2026-06-20
    #     by Jim, Educare/ECD suffix). The CSV's ECD-block "Charles Duna" is the
    #     Sume Centre educare. Seeds counts 33 / 62 / 37. Requires
    #     sync_airtable_schools to have pulled these uids into Postgres first. ---
    ('aaron gqadu', 'ECD'): 'SCH-00332',   # Aaron Gqadu ECD
    ('charles duna', 'ECD'): 'SCH-00333',  # Sume Centre (Charles Duna ECD)
    ('seyisi', 'ECD'): 'SCH-00334',        # Seyisi ECD
}

DEFAULT_CSV = os.path.join(
    settings.BASE_DIR, "static", "data",
    "children-per-school-1000-stories-edutech.csv",
)


class Command(BaseCommand):
    help = "Seed manual 1000 Stories + EduTech children_count values into the grid."

    def add_arguments(self, parser):
        parser.add_argument("--year", type=int, default=2026,
                            help="Grid year to seed (default: 2026).")
        parser.add_argument("--csv", default=DEFAULT_CSV,
                            help="Path to the children-per-school CSV.")
        parser.add_argument("--dry-run", action="store_true",
                            help="Print the plan without writing.")

    def handle(self, *args, **options):
        year = options["year"]
        with open(options["csv"], newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)  # discard the header row
            aggregated = parse_children_served(list(reader))

        plan = []      # (school_uid, programme, count, csv_name, bucket)
        unmapped = []  # (csv_name, bucket, {programme: count})
        for (name, bucket), counts in sorted(aggregated.items()):
            uid = CHILDREN_SEED_NAME_TO_UID.get((name, bucket))
            if uid is None:
                unmapped.append((name, bucket, counts))
                continue
            for programme, count in sorted(counts.items()):
                plan.append((uid, programme, count, name, bucket))

        schools = len({uid for uid, *_ in plan})
        self.stdout.write(
            f"Children seed for {year}: {len(plan)} cells across {schools} schools."
        )
        if unmapped:
            self.stdout.write(self.style.WARNING(
                f"{len(unmapped)} CSV site(s) with values have NO mapping (skipped):"
            ))
            for name, bucket, counts in unmapped:
                self.stdout.write(f"  - {name} [{bucket}] {dict(counts)}")

        if options["dry_run"]:
            for uid, programme, count, name, bucket in plan:
                self.stdout.write(
                    f"  {uid}  {programme:<16} count={count:<5} ({name} [{bucket}])"
                )
            self.stdout.write(self.style.NOTICE("Dry run -- nothing written."))
            return

        updated = unchanged = 0
        with transaction.atomic():
            for uid, programme, count, name, bucket in plan:
                row = create_cell(uid, programme, year, user=None)
                if row.children_count == count:
                    unchanged += 1
                    continue
                row.children_count = count
                row.save(update_fields=["children_count", "updated_at"])
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Done. {updated} children_count values written, {unchanged} already correct."
        ))
