"""One-off recovery: restore School.school_uid wiped by a mis-targeted sync.

Incident (2026-06-20): a sync_airtable_schools run on Render fetched from the
WRONG Airtable base (AIRTABLE_SCHOOLS_BASE_ID was a stale base, appHSK..., whose
records have no "School UID" field). extract_row() returned school_uid=None for
every record and bulk_update() wrote those NULLs (Postgres allows many NULLs in a
unique column, so nothing blocked it). ~343 active schools lost school_uid -- the
join key for the 2026 session tables, the programme grid, and the youth roster.

The rows, names, and the grid's SchoolProgrammeYear data (keyed by school FK, not
uid) all survived. This command restores each row to the uid it held immediately
before the wipe, from PRE_WIPE_NAME_TO_UID (captured read-only from prod at the
start of the incident session).

Why not just re-run the sync? The bad run also stamped every row with appHSK
record-ids, so a fresh sync would match nothing (wrong airtable_id, null uid) and
bulk-create ~329 duplicate schools. Restore uids first; a later (hardened) sync
then matches by uid and refreshes airtable_id without duplicating.

Duplicate rows (the sync's known dup-regrowth) are resolved deterministically: a
contested uid goes to the row the grid actually references (SchoolProgrammeYear),
then the active row, then the lowest id; the losing duplicate stays null. A uid
already present on a surviving row is never reassigned. Idempotent (only fills
NULLs); --dry-run prints the plan.

Run on Render:  python manage.py restore_school_uids --dry-run   # review
                python manage.py restore_school_uids
"""
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

# Prod's own school_uid state captured read-only at the start of the incident,
# keyed by lower-cased School.name. Names are unique in this snapshot.
PRE_WIPE_NAME_TO_UID = {
    'aaron gqadu': 'SCH-00276', 'abraham levy': 'SCH-00144',
    'adcoc brighton kids': 'SCH-00245', 'adolph schauder': 'SCH-00123',
    'alex jayiya': 'SCH-00109', 'alexander': 'SCH-00324',
    'alfonso arries': 'SCH-00142', 'alpha': 'SCH-00115', 'amanzi': 'SCH-00165',
    'arcadia': 'SCH-00146', 'arise and shine': 'SCH-00256',
    'ashton gontshi': 'SCH-00127', 'astra': 'SCH-00278', 'baby daycare': 'SCH-00218',
    'bambino': 'SCH-00298', 'bavumeleni': 'SCH-00053', 'bayview': 'SCH-00173',
    'ben nyati': 'SCH-00203', 'ben sinuka': 'SCH-00289', 'bethelsdorp': 'SCH-00087',
    'bethvale': 'SCH-00072', 'bj mnyanda': 'SCH-00057', 'boet jegels': 'SCH-00159',
    'bomi obutsha': 'SCH-00257', 'bright angels': 'SCH-00299', 'bright suns': 'SCH-00330',
    'busy bee': 'SCH-00262', 'c w hendrickse': 'SCH-00122', 'canzibe': 'SCH-00090',
    'caritas': 'SCH-00182', 'cebelihle': 'SCH-00068', 'cedarberg': 'SCH-00110',
    'charles duna': 'SCH-00281', 'charlotte educare': 'SCH-00329', 'chubekile': 'SCH-00036',
    'cillie': 'SCH-00325', 'cingani': 'SCH-00026', 'clarkson': 'SCH-00319',
    'coega': 'SCH-00190', 'colchester': 'SCH-00113', 'colleen glen': 'SCH-00111',
    'coselelani': 'SCH-00001', 'cowan': 'SCH-00037', 'cuttee babies nursery': 'SCH-00232',
    'dalrose': 'SCH-00196', 'dalubuhle': 'SCH-00010', 'daniels': 'SCH-00098',
    'david vuku': 'SCH-00064', 'de vos malan': 'SCH-00114', 'despatch': 'SCH-00132',
    'dias': 'SCH-00189', 'die heuwel': 'SCH-00153', 'dietrich': 'SCH-00121',
    'dorcas educare centre': 'SCH-00239', 'dorothy': 'SCH-00318', 'douglas mbopa': 'SCH-00002',
    'dr a w habelgaarn': 'SCH-00191', 'dumani': 'SCH-00280', 'early rose': 'SCH-00230',
    'ebongweni': 'SCH-00288', 'ekhaya': 'SCH-00282', 'elufefeni': 'SCH-00274',
    'elukholweni': 'SCH-00108', 'elundini': 'SCH-00054', 'emafini': 'SCH-00073',
    'emfundweni': 'SCH-00210', 'emfundweni pre-r educare': 'SCH-00213',
    'emmanuel day care': 'SCH-00091', 'empumalanga': 'SCH-00305', 'emsengeni': 'SCH-00076',
    'emzomncane': 'SCH-00099', 'enkulekweni': 'SCH-00075', 'enkwenkwezini': 'SCH-00070',
    'enqileni': 'SCH-00097', 'entokozweni educare': 'SCH-00247', 'esitiyeni': 'SCH-00198',
    'ez kabane': 'SCH-00046', 'ezibeleni': 'SCH-00231', 'fernwood park': 'SCH-00164',
    'fontein': 'SCH-00161', 'frank joubert': 'SCH-00180', 'fumisukoma': 'SCH-00283',
    'funimfundo': 'SCH-00062', 'future angels': 'SCH-00052', 'future kids educare': 'SCH-00225',
    'future stars': 'SCH-00255', 'g j louw': 'SCH-00155', 'garrett': 'SCH-00088',
    'gelvan park': 'SCH-00170', 'gelvandale': 'SCH-00130', 'gertrude shope': 'SCH-00275',
    'good hope': 'SCH-00287', 'govan mbeki': 'SCH-00223', 'green apple': 'SCH-00301',
    'greenville': 'SCH-00112', 'helenvale': 'SCH-00145', 'hillcrest': 'SCH-00166',
    'hlokoma': 'SCH-00044', 'hlumelo': 'SCH-00258', 'holy name community': 'SCH-00261',
    'hombakazi': 'SCH-00184', 'ikamvalethu': 'SCH-00250', 'ikhwezelihle': 'SCH-00095',
    'ilinge': 'SCH-00175', 'ilitha': 'SCH-00105', 'ilithalethu': 'SCH-00094',
    'imbasa': 'SCH-00066', 'inkqubela': 'SCH-00055', 'isaac booi': 'SCH-00277',
    'isilimela': 'SCH-00008', 'isizwe sethu': 'SCH-00265', 'ithembalethu': 'SCH-00268',
    'ithembelihle': 'SCH-00013', 'j k zondi': 'SCH-00169', 'j n tulwana': 'SCH-00194',
    'james jolobe': 'SCH-00024', 'james ndulula': 'SCH-00163', 'james ntungwana': 'SCH-00116',
    'jarvis gqamlana': 'SCH-00049', "jeffrey's bay": 'SCH-00015', 'jesus dominion': 'SCH-00310',
    'joe slovo': 'SCH-00131', 'john masiza': 'SCH-00192', 'jongilanga': 'SCH-00290',
    'jongingomso ecd': 'SCH-00267', 'jubilee park': 'SCH-00171', 'kama': 'SCH-00071',
    'kamvalethu daycare': 'SCH-00214', 'kayser ngxwana': 'SCH-00065', 'khanyisa': 'SCH-00317',
    'khanyisa hs': 'SCH-00047', 'khazimla pre-school': 'SCH-00208',
    # 'khazimla' (was SCH-00248) intentionally dropped: consolidated onto
    # "Khazimla Pre-School" SCH-00208; its row is retired, not restored.
    'khulile': 'SCH-00086', 'khumbulani': 'SCH-00005', 'khwezi lomso': 'SCH-00004',
    'kideo learning centre': 'SCH-00222', 'kids college': 'SCH-00056',
    'kings and quuens': 'SCH-00237', 'kk ncwana': 'SCH-00089', 'kleinskool': 'SCH-00137',
    'koester': 'SCH-00106', 'kokkewiet': 'SCH-00292', 'kroneberg': 'SCH-00077',
    'kruisrivier': 'SCH-00186', 'kuyga': 'SCH-00183', 'kwakhanya': 'SCH-00240',
    'kwakhanya daycare': 'SCH-00209', 'kwamagxaki': 'SCH-00023', 'kwanoxolo': 'SCH-00082',
    'kwazakhele': 'SCH-00028', 'lamani': 'SCH-00067', 'lavela pre-school': 'SCH-00215',
    'libhongo lwethu': 'SCH-00061', 'lihlombe educare': 'SCH-00207', 'likhaya daycare': 'SCH-00216',
    'linge tots': 'SCH-00244', 'lingelethu': 'SCH-00322', 'lithemba': 'SCH-00309',
    'little angels unite': 'SCH-00254', 'little flower': 'SCH-00187', 'little flowers': 'SCH-00328',
    'little ships': 'SCH-00226', 'living ubuntu': 'SCH-00316', 'livuse': 'SCH-00079',
    'lovemore park': 'SCH-00176', 'loyiso': 'SCH-00042', 'lukhanyiselo': 'SCH-00241',
    'lukhanyiso': 'SCH-00229', 'lukhanyiso educare': 'SCH-00271', 'lukhanyiso pre school': 'SCH-00220',
    'lukhanyo': 'SCH-00063', 'lungisa': 'SCH-00022', 'lungiso': 'SCH-00045',
    'luv birds day care': 'SCH-00253', 'machiu': 'SCH-00179', 'magqabi': 'SCH-00129',
    'malabar': 'SCH-00181', 'malikhanye day care': 'SCH-00228', 'masakhane': 'SCH-00138',
    'masibambane': 'SCH-00043', 'masiphathisane': 'SCH-00018', 'mboniselo': 'SCH-00101',
    'mdengentonga': 'SCH-00119', 'melisizwe': 'SCH-00060', 'melumzi': 'SCH-00148',
    'mfesane': 'SCH-00017', 'minnie day care': 'SCH-00048', 'missionvale': 'SCH-00117',
    'mjuleni': 'SCH-00177', 'mngcunube': 'SCH-00152', 'mnqophiso': 'SCH-00168',
    'molefe': 'SCH-00284', 'moses mabhida': 'SCH-00041', 'motherwell': 'SCH-00025',
    'mqhayi': 'SCH-00140', 'msobomvu full service': 'SCH-00323', 'msobomvu preschool': 'SCH-00297',
    'mthonjeni': 'SCH-00158', 'mzamomhle edu-care': 'SCH-00294', 'mzimhlophe': 'SCH-00096',
    'mzingisi': 'SCH-00312', 'mzomtsha': 'SCH-00157', 'mzontsundu': 'SCH-00029',
    'ncedo': 'SCH-00039', 'nceduluntu edu-care': 'SCH-00293', 'ndyebo': 'SCH-00027',
    'ndzondelelo': 'SCH-00031', 'nelisa': 'SCH-00243', 'new brighton future kids': 'SCH-00233',
    'newell': 'SCH-00016', 'njongozabantu': 'SCH-00081', 'nkuthalo': 'SCH-00074',
    'nobandla': 'SCH-00320', 'nokwezi': 'SCH-00195', 'nolundi': 'SCH-00224',
    'noluthando': 'SCH-00321', 'nomathamsanqa': 'SCH-00167', 'nomonde': 'SCH-00238',
    'nomtha': 'SCH-00308', 'noninzi luzipho': 'SCH-00193', 'nonkqubela': 'SCH-00315',
    'nontsapho': 'SCH-00252', 'nontsikelelo': 'SCH-00300', 'nosandla educare': 'SCH-00206',
    'nosipho': 'SCH-00162', 'ntlemeza': 'SCH-00172', 'ntyatyambo': 'SCH-00083',
    'nxanelwimfundo': 'SCH-00059', 'p.g mangqana pre-school': 'SCH-00260', 'p.g manqana': 'SCH-00270',
    'papenkuil': 'SCH-00185', 'paulos oyigcwele': 'SCH-00296', 'pendla': 'SCH-00078',
    'phakama': 'SCH-00104', 'phakamile': 'SCH-00285', 'phakamisa': 'SCH-00032',
    'phindubuye': 'SCH-00201', 'qaphelani': 'SCH-00003', 'qaqawuli godolozi': 'SCH-00302',
    'qhamani pre-school': 'SCH-00212', 'qhayiyalethu': 'SCH-00020', 'r h godlo senior': 'SCH-00202',
    'republic': 'SCH-00118', 'rock of ages': 'SCH-00227', 'rocklands': 'SCH-00006',
    'rufane donkin': 'SCH-00197', 'sakha abantwana': 'SCH-00100', 'sakhisizwe': 'SCH-00014',
    'sakhuxolo educare': 'SCH-00263', 'samkelewe': 'SCH-00033', 'samuel nongogo': 'SCH-00085',
    'sanctor': 'SCH-00154', 'sandwater': 'SCH-00306', 'sapphire': 'SCH-00051',
    'seagull': 'SCH-00133', 'sekunjalo preschool': 'SCH-00272', 'seyisi': 'SCH-00279',
    'sifunimfundo': 'SCH-00314', 'sikhothina': 'SCH-00125', 'sikhulise pre-school': 'SCH-00205',
    'simanye': 'SCH-00234', 'sinethemba': 'SCH-00291', 'sipho hashe': 'SCH-00147',
    'sisonke': 'SCH-00313', 'sithembile': 'SCH-00139', 'sivuyiseni': 'SCH-00204',
    'siyabulela': 'SCH-00092', 'siyaphambili': 'SCH-00069', 'siyazama': 'SCH-00295',
    'sizamokuhle daycare': 'SCH-00221', 'smarties': 'SCH-00269', 'sophakama pre-school': 'SCH-00219',
    'soqhayisa': 'SCH-00034', 'soutpan': 'SCH-00199', 'soweto-on-sea': 'SCH-00151',
    'spencer mabija': 'SCH-00093', 'st augustines': 'SCH-00303', 'st james': 'SCH-00035',
    "st joseph's": 'SCH-00124', 'st magdalene': 'SCH-00264', 'st mary magdalene': 'SCH-00103',
    "st teresa's (rc)": 'SCH-00160', 'st thomas': 'SCH-00038', 'stephen mazungula': 'SCH-00050',
    'stephen nkomo': 'SCH-00135', 'strelitzia': 'SCH-00102', 'sume centre': 'SCH-00286',
    'sunnyside': 'SCH-00251', 'swartkops': 'SCH-00126', 'takalani daycare': 'SCH-00211',
    'thanda abantwana': 'SCH-00242', 'thandabantwana daycare': 'SCH-00217',
    "thandi's educare & aftercare": 'SCH-00259', 'thembalethu': 'SCH-00107', 'tinara': 'SCH-00030',
    'tinky winky day care': 'SCH-00235', 'triomf': 'SCH-00188', 'twinkle toes educare': 'SCH-00266',
    'tyhilulwazi': 'SCH-00040', 'uitenhage': 'SCH-00143', "umzam'omhle educare": 'SCH-00273',
    'van der kemp': 'SCH-00149', 'van stadens': 'SCH-00174', 'verite': 'SCH-00134',
    'vezubuhle': 'SCH-00084', 'vm kwinana': 'SCH-00021', 'vuba': 'SCH-00128',
    'vukani daycare': 'SCH-00311', 'vukanibantu': 'SCH-00080', 'vulamazibuko': 'SCH-00007',
    'vulithemba': 'SCH-00246', 'vulumzi': 'SCH-00019', 'w b tshume': 'SCH-00150',
    'walmer': 'SCH-00200', 'walmer hs': 'SCH-00012', 'west end': 'SCH-00136',
    'winterberg': 'SCH-00120', 'wongalethu': 'SCH-00009', 'yellowwoods': 'SCH-00178',
    'yomelela educare': 'SCH-00236', 'zamukukhanya': 'SCH-00156', 'zanolwazi': 'SCH-00011',
    'zanoxolo': 'SCH-00058', 'zizamele': 'SCH-00304', 'zukhanye': 'SCH-00249',
    'zukisa': 'SCH-00307',
}


class Command(BaseCommand):
    help = "Restore School.school_uid values wiped by the wrong-base sync (2026-06-20)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true",
                            help="Print the plan without writing.")

    def handle(self, *args, **options):
        from api.models import School, SchoolProgrammeYear

        null_rows = list(School.objects.filter(school_uid__isnull=True))
        existing_uids = set(
            School.objects.exclude(school_uid__isnull=True).values_list("school_uid", flat=True)
        )
        spy_ids = set(SchoolProgrammeYear.objects.values_list("school_id", flat=True))

        groups = defaultdict(list)
        unresolved = []
        for s in null_rows:
            uid = PRE_WIPE_NAME_TO_UID.get((s.name or "").strip().lower())
            if uid:
                groups[uid].append(s)
            else:
                unresolved.append(s)

        plan = []        # (school_id, uid, name)
        skipped_dups = []  # (name, uid, reason)
        for uid, rows in groups.items():
            if uid in existing_uids:
                skipped_dups += [(r.name, uid, "uid already on a surviving row") for r in rows]
                continue
            if len(rows) == 1:
                plan.append((rows[0].id, uid, rows[0].name))
                continue
            # Contested: prefer the grid-referenced row, then active, then lowest id.
            winner = max(rows, key=lambda r: (r.id in spy_ids, r.is_active, -r.id))
            plan.append((winner.id, uid, winner.name))
            skipped_dups += [
                (r.name, uid, f"duplicate of winning row {winner.id}")
                for r in rows if r.id != winner.id
            ]

        self.stdout.write(
            f"Restore plan: {len(plan)} rows to set, {len(skipped_dups)} duplicate rows skipped, "
            f"{len(unresolved)} rows with no pre-wipe match."
        )
        if skipped_dups:
            self.stdout.write(self.style.WARNING("Skipped duplicate rows (left null):"))
            for name, uid, reason in skipped_dups:
                self.stdout.write(f"  - {name} -> {uid}: {reason}")
        if unresolved:
            self.stdout.write(self.style.WARNING("No pre-wipe match (left null):"))
            for s in unresolved:
                self.stdout.write(f"  - {s.name} (id {s.id}, active={s.is_active})")

        if options["dry_run"]:
            for sid, uid, name in sorted(plan, key=lambda x: x[1]):
                self.stdout.write(f"  id={sid:<5} {uid}  {name}")
            self.stdout.write(self.style.NOTICE("Dry run -- nothing written."))
            return

        written = 0
        with transaction.atomic():
            for sid, uid, name in plan:
                # idempotent + race-safe: only fill a still-null row
                written += School.objects.filter(id=sid, school_uid__isnull=True).update(school_uid=uid)

        self.stdout.write(self.style.SUCCESS(
            f"Done. Restored {written} school_uid values."
        ))
