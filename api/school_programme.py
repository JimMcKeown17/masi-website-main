"""School Programme Grid logic (Increment 1, within-Masi).

Pure, DB-free policy functions live here so the nightly cron, the rollups, and
the grid API all import one source of truth. See _plans/site-programme-grid.md.

Import-time purity rule: this module imports only stdlib + its own constants at
module load. Every model access happens lazily inside a function body
(`from api.models import ...`) so models.py can import the vocabulary below
without a circular import.
"""
from collections import defaultdict

# --- Programme vocabulary (single source of truth) ---------------------------
# The 9 programmes that occupy grid columns (plan section 4a / 5).
ZAZI_IZANDI = "zazi_izandi"
MASI_LITERACY = "masi_literacy"
NUMERACY = "numeracy"
THOUSAND_STORIES = "thousand_stories"
EDUTECH = "edutech"
YEBO = "yebo"
SPORT_ARTS = "sport_arts"
HOMEWORK = "homework"
PRESCHOOL = "preschool"

PROGRAMME_CHOICES = [
    (ZAZI_IZANDI, "Zazi iZandi"),
    (MASI_LITERACY, "Masi Literacy"),
    (NUMERACY, "Numeracy"),
    (THOUSAND_STORIES, "1000 Stories"),
    (EDUTECH, "EduTech"),
    (YEBO, "Yebo"),
    (SPORT_ARTS, "Sport & Arts"),
    (HOMEWORK, "Homework"),
    (PRESCHOOL, "Preschool"),
]

# How children_count is interpreted (the sheet's "Include Which Beneficiaries").
COUNT_BASIS_CHILD_LEVEL = "child_level"
COUNT_BASIS_WHOLE_SCHOOL = "whole_school"
COUNT_BASIS_PERCENT = "percent_of_school"
COUNT_BASIS_CHOICES = [
    (COUNT_BASIS_CHILD_LEVEL, "Child-level"),
    (COUNT_BASIS_WHOLE_SCHOOL, "Whole school"),
    (COUNT_BASIS_PERCENT, "Percent of school"),
]

# Who owns children_count: the cron (computed) or a human (manual).
COUNT_SOURCE_COMPUTED = "computed"
COUNT_SOURCE_MANUAL = "manual"
COUNT_SOURCE_CHOICES = [
    (COUNT_SOURCE_COMPUTED, "Computed"),
    (COUNT_SOURCE_MANUAL, "Manual"),
]

# Canonical site-type buckets.
PRIMARY = "Primary"
ECD = "ECD"
SECONDARY = "Secondary"

# Raw School.type spellings -> canonical bucket (prod-verified 2026-06-18:
# Primary School, ECDC, Secondary School, plus the spelling variants ECD / Primary).
_SITE_TYPE_MAP = {
    "primary school": PRIMARY,
    "primary": PRIMARY,
    "ecdc": ECD,
    "ecd": ECD,
    "secondary school": SECONDARY,
    "secondary": SECONDARY,
}

# Site types that get programme rows on the grid. Secondary (Top Learners high
# schools) and unknown types are excluded (plan section 6.4).
GRID_SITE_TYPES = frozenset({PRIMARY, ECD})


def normalize_site_type(raw):
    """Map a raw School.type string to a canonical bucket, or None.

    None signals an unnormalizable type (blank / Other / unknown) that must be
    flagged for a manual fix rather than silently bucketed. Never coalesces
    School.site_type in -- that field is a programme-membership list, not a type.
    """
    if not raw:
        return None
    return _SITE_TYPE_MAP.get(raw.strip().lower())


def is_grid_eligible(raw):
    """True if a raw School.type belongs on the programme grid (Primary / ECD)."""
    return normalize_site_type(raw) in GRID_SITE_TYPES


# --- youth_active: the section 5 job-title -> programme lookup ----------------

# Sentinel for youth who count org-wide but occupy no grid cell (section 9 roster).
SITE_UNASSIGNED = "__site_unassigned__"

# Keys are lower-cased job titles. All 14 prod titles are covered (prod-verified
# 2026-06-18); "Literacy Coaches (ZZ)" is a cleaned-at-source mislabel kept here
# defensively. Both ZZ variants resolve to zazi_izandi, so site-type does not
# change the programme -- only the org's own labelling does.
_JOB_TITLE_TO_PROGRAMME = {
    "literacy coach": MASI_LITERACY,
    "numeracy coach": NUMERACY,
    "count coach": NUMERACY,
    "zazi izandi coach": ZAZI_IZANDI,
    "zz ecd coach": ZAZI_IZANDI,
    "literacy coaches (zz)": ZAZI_IZANDI,
    "1000 stories youth": THOUSAND_STORIES,
    "edutech coach": EDUTECH,
    "yeboneer": YEBO,
    "sport & arts coach": SPORT_ARTS,
    "homework coach": HOMEWORK,
    "practitioner": PRESCHOOL,
    "ecd practitioner": PRESCHOOL,
}

# Roam all programmes / no fixed school -- off the grid, on the roster (section 5).
_SITE_UNASSIGNED_TITLES = {"assessor", "yes intern"}


def programme_for_job_title(job_title):
    """Classify a Youth.job_title.

    Returns a programme key (site-assigned, gets a grid cell), the SITE_UNASSIGNED
    sentinel (Assessor / Yes Intern -- roster only), or None (unmapped -- the
    caller must flag it, never silently drop).
    """
    if not job_title:
        return None
    key = job_title.strip().lower()
    if key in _JOB_TITLE_TO_PROGRAMME:
        return _JOB_TITLE_TO_PROGRAMME[key]
    if key in _SITE_UNASSIGNED_TITLES:
        return SITE_UNASSIGNED
    return None


def compute_youth_active():
    """Snapshot of currently-active youth, classified per section 5.

    youth_active is a current-staffing snapshot (Youth.employment_status='Active'),
    not a year-scoped flow metric. Inactivity is read from employment_status, never
    inferred from end_date (section 12: an Inactive youth with a null end_date must
    not be counted).

    Returns:
      by_school_programme: {(school_id, programme): count} -- grid cells
      roster:              {job_title: count} -- site-unassigned active youth
      unmapped:            {job_title: count} -- active titles with no mapping (flag)
      site_assigned_no_school: {job_title: count} -- integrity gap (flag)
    """
    from api.models import Youth

    by_school_programme = defaultdict(int)
    roster = defaultdict(int)
    unmapped = defaultdict(int)
    site_assigned_no_school = defaultdict(int)

    active = Youth.objects.filter(employment_status="Active").values_list(
        "job_title", "school_id"
    )
    for job_title, school_id in active:
        programme = programme_for_job_title(job_title)
        if programme is None:
            unmapped[job_title or ""] += 1
        elif programme == SITE_UNASSIGNED:
            roster[job_title] += 1
        elif school_id is None:
            site_assigned_no_school[job_title] += 1
        else:
            by_school_programme[(school_id, programme)] += 1

    return {
        "by_school_programme": dict(by_school_programme),
        "roster": dict(roster),
        "unmapped": dict(unmapped),
        "site_assigned_no_school": dict(site_assigned_no_school),
    }


# --- children reach + identity-union dedup (section 7) ------------------------

def masi_child_identities(school_uid, year):
    """Distinct child identities (CanonicalChild child_uids) per within-Masi
    computed programme, for one school in one year.

    child_uid IS the CanonicalChild key, so deduping by child_uid already
    deduplicates by canonical child -- no join needed for the count (the join to
    CanonicalChild is only needed for gender, see compute_pct_female). Empty /
    None child slots are ignored.
    """
    from api.models import LiteracySession2026, NumeracySession2026

    literacy = set()
    lit_rows = LiteracySession2026.objects.filter(
        school_uid=school_uid, session_date__year=year
    ).values_list("child_uid_1", "child_uid_2")
    for child_uid_1, child_uid_2 in lit_rows:
        if child_uid_1:
            literacy.add(child_uid_1)
        if child_uid_2:
            literacy.add(child_uid_2)

    numeracy = set()
    num_rows = NumeracySession2026.objects.filter(
        school_uid=school_uid, session_date__year=year
    ).values_list("child_uids", flat=True)
    for child_uids in num_rows:
        for child_uid in child_uids or ():
            if child_uid:
                numeracy.add(child_uid)

    return {MASI_LITERACY: literacy, NUMERACY: numeracy}


def unique_beneficiaries_from_identities(identity_sets, has_whole_school, total_kids):
    """The section 7 dedup rule. Count DISTINCT child identities across the
    school's child-level programmes -- never the sum of aggregate counts.

    - A whole-school programme present (+ a known enrolment) means everyone is
      reached: return total_kids.
    - Otherwise return the size of the identity union, capped at total_kids when
      enrolment is known (you cannot serve more distinct children than exist).
    """
    if has_whole_school and total_kids is not None:
        return total_kids
    union = set()
    for identities in identity_sets:
        union |= identities
    count = len(union)
    if total_kids is not None:
        return min(count, total_kids)
    return count


# --- pct_female from CanonicalChild.gender (section 4b) -----------------------

# Prod CanonicalChild.gender is a raw string: 'F' / 'M', with most rows blank.
_FEMALE_TOKENS = {"F", "FEMALE"}
_MALE_TOKENS = {"M", "MALE"}


def compute_pct_female(child_uids):
    """Percent female among the given children that have a recorded gender.

    Children with no recorded gender are excluded from the denominator -- an
    honest percentage over known data, not a figure diluted by ~88% of rows that
    are simply blank. Returns a float rounded to 2 dp, or None when no child in
    the set has a recorded gender.
    """
    from api.models import CanonicalChild

    if not child_uids:
        return None
    genders = CanonicalChild.objects.filter(child_uid__in=child_uids).values_list(
        "gender", flat=True
    )
    female = male = 0
    for gender in genders:
        token = (gender or "").strip().upper()
        if token in _FEMALE_TOKENS:
            female += 1
        elif token in _MALE_TOKENS:
            male += 1
    gendered = female + male
    if gendered == 0:
        return None
    return round(100.0 * female / gendered, 2)


# --- per-programme config: source + basis (Jim, 2026-06-18) -------------------

# Increment 1 computes children only for these (Zazi deferred to Increment 2).
COMPUTED_PROGRAMMES = frozenset({MASI_LITERACY, NUMERACY})

# Programmes where every child at the site is reached (basis = whole_school) ->
# unique_beneficiaries = Total Kids in School. EduTech and Masi's own preschools.
# 1000 Stories is also whole-school but only at an ECD (handled below).
_FIXED_WHOLE_SCHOOL = frozenset({EDUTECH, PRESCHOOL})


def count_source_for(programme):
    """'computed' (cron-owned children_count) or 'manual' (human-owned)."""
    return COUNT_SOURCE_COMPUTED if programme in COMPUTED_PROGRAMMES else COUNT_SOURCE_MANUAL


def count_basis_for(programme, site_type):
    """The count_basis for a programme at a site of a given normalized site_type.

    1000 Stories is whole-school at an ECD but percent-of-school at a primary, so
    basis depends on the site, not the programme alone.
    """
    if programme == THOUSAND_STORIES:
        return COUNT_BASIS_WHOLE_SCHOOL if site_type == ECD else COUNT_BASIS_PERCENT
    if programme in _FIXED_WHOLE_SCHOOL:
        return COUNT_BASIS_WHOLE_SCHOOL
    return COUNT_BASIS_CHILD_LEVEL


def is_whole_school(programme, site_type):
    """True when a programme reaches the whole site (drives the section 7 dedup
    override: unique_beneficiaries = Total Kids in School)."""
    return count_basis_for(programme, site_type) == COUNT_BASIS_WHOLE_SCHOOL


# --- site_type cross-check: parse the programme-membership list ---------------

# site_type tokens -> programme (plan section 6: a seed/cross-check, NOT authoritative).
_SITE_TYPE_TOKEN_TO_PROGRAMME = {
    "literacy": MASI_LITERACY,
    "numeracy": NUMERACY,
    "zazi izandi": ZAZI_IZANDI,
    "1000 stories": THOUSAND_STORIES,
    "edutech": EDUTECH,
    "yearbeyond": YEBO,  # the WC youth-service programme Yeboneers staff
}

# Non-programme tokens that leak into site_type -- ignored, not flagged as unknown.
# Includes plural site-type forms ('ECDCs', 'Primary Schools') seen in prod data.
_SITE_TYPE_NOISE = {
    "", "primary", "primary school", "primary schools",
    "ecd", "ecds", "ecdc", "ecdcs",
    "secondary", "secondary school", "secondary schools",
    "top learners high school",
}


def programmes_from_site_type(site_type):
    """Parse School.site_type (a comma-joined programme list) into programme keys.

    Returns {'programmes': set, 'unknown_tokens': set}. Unknown tokens are
    surfaced for review (never silently dropped); recognised site-type/noise
    tokens are ignored. site_type only seeds/cross-checks which programme columns
    exist -- the authoritative presence comes from youth + computed children.
    """
    programmes = set()
    unknown_tokens = set()
    for raw in (site_type or "").split(","):
        token = raw.strip().lower()
        if token in _SITE_TYPE_TOKEN_TO_PROGRAMME:
            programmes.add(_SITE_TYPE_TOKEN_TO_PROGRAMME[token])
        elif token in _SITE_TYPE_NOISE:
            continue
        else:
            unknown_tokens.add(raw.strip())
    return {"programmes": programmes, "unknown_tokens": unknown_tokens}


# --- Zazi cross-backend dedup (Increment 2) ----------------------------------

def resolve_zazi_export(zazi_export):
    """Resolve a Zazi per-school export into Masi identities.

    Returns:
      by_uid: {school_uid: {'reach': int, 'child_uids': set, 'unresolved': int}}.
        reach = raw distinct Zazi children (complete, needs no canonical);
        child_uids = those resolved to CanonicalChild via participant_id (the
        deduppable subset); unresolved = participants not yet in canonical (the
        reconciliation gap).
      unmapped_schools: [program_name, ...] -- ZZ schools with no Masi school_uid.
    """
    from api.models import CanonicalChild

    schools = (zazi_export or {}).get("schools", [])
    all_pids = set()
    for school in schools:
        if not school.get("school_uid"):
            continue
        for child in school.get("children", []):
            pid = child.get("participant_id")
            if pid is not None:
                all_pids.add(str(pid))

    # One query resolves every participant_id -> canonical child_uid.
    pid_to_uid = dict(
        CanonicalChild.objects
        .filter(participant_id__in=all_pids)
        .exclude(child_uid__isnull=True)
        .values_list("participant_id", "child_uid")
    )

    by_uid = {}
    unmapped_schools = []
    for school in schools:
        uid = school.get("school_uid")
        if not uid:
            unmapped_schools.append(school.get("program_name"))
            continue
        child_uids = set()
        unresolved = 0
        for child in school.get("children", []):
            pid = child.get("participant_id")
            resolved = pid_to_uid.get(str(pid)) if pid is not None else None
            if resolved:
                child_uids.add(resolved)
            else:
                unresolved += 1
        by_uid[uid] = {
            "reach": school.get("child_count", 0),
            "child_uids": child_uids,
            "unresolved": unresolved,
        }
    return {"by_uid": by_uid, "unmapped_schools": unmapped_schools}


# --- the nightly refresh orchestrator (section 8) -----------------------------

def recompute_school_year_stats(school, year, now=None, identities=None,
                                programmes_present=None):
    """Recompute and write a school's derived year-stats (unique_beneficiaries,
    pct_female) from current DB state. Used by BOTH the nightly cron and the
    human-edit path, so a human edit to total_kids recomputes the rollup with the
    exact same logic, immediately (plan section 8 / 12). Writes system columns
    only, via .update().
    """
    from django.utils import timezone
    from api.models import SchoolProgrammeYear, SchoolYearStats

    now = now or timezone.now()
    site_type = normalize_site_type(school.type)
    if identities is None:
        identities = (
            masi_child_identities(school.school_uid, year)
            if school.school_uid
            else {MASI_LITERACY: set(), NUMERACY: set()}
        )
    if programmes_present is None:
        programmes_present = set(
            SchoolProgrammeYear.objects.filter(school=school, year=year)
            .values_list("programme", flat=True)
        )

    # Union over ALL identity sets the caller supplies -- within-Masi only on the
    # edit path, masi + zazi on the nightly cron path (see the module docstring).
    identity_sets = list(identities.values())
    identity_union = set().union(*identity_sets) if identity_sets else set()
    has_whole_school = any(
        is_whole_school(programme, site_type) for programme in programmes_present
    )

    stats, _ = SchoolYearStats.objects.get_or_create(school=school, year=year)
    unique = unique_beneficiaries_from_identities(
        identity_sets,
        has_whole_school,
        stats.total_kids_in_school,
    )
    SchoolYearStats.objects.filter(pk=stats.pk).update(
        unique_beneficiaries=unique,
        pct_female=compute_pct_female(identity_union),
        as_of=now,
    )
    return {
        "unique_beneficiaries": unique,
        "has_whole_school": has_whole_school,
        "identity_union": identity_union,
    }


def refresh_school_programme_grid(year, zazi_export=None):
    """Recompute and write the system-owned grid columns for `year`.

    Composes the computation functions above. Writes ONLY system-owned columns
    (youth_active, count_basis/source, computed children_count, as_of,
    unique_beneficiaries, pct_female) via column-scoped .update() so a concurrent
    human edit to a human-owned column is never lost (the column-ownership rule,
    plan section 4 / 8). Surfaces integrity checks rather than swallowing them.

    youth_active is a current-staffing snapshot, so this is meaningful for the
    current year; pass the current year in production.

    Returns a summary dict (counts + integrity flags + roster).
    """
    from django.utils import timezone

    from api.models import School, SchoolProgrammeYear, SchoolYearStats

    now = timezone.now()
    youth = compute_youth_active()
    zazi = resolve_zazi_export(zazi_export) if zazi_export else {"by_uid": {}, "unmapped_schools": []}
    zazi_by_uid = zazi["by_uid"]

    # Invert the youth snapshot to programmes-present-per-school.
    youth_by_school = defaultdict(dict)
    for (school_id, programme), count in youth["by_school_programme"].items():
        youth_by_school[school_id][programme] = count

    integrity = {
        "unmatched_schools": [],
        "unmapped_titles": dict(youth["unmapped"]),
        "site_assigned_no_school": dict(youth["site_assigned_no_school"]),
        "unknown_site_type_tokens": set(),
        "reach_without_identities": [],
        "unmapped_zazi_schools": list(zazi["unmapped_schools"]),
        "unresolved_zazi_participants": 0,
    }
    rows_created = 0
    rows_updated = 0
    schools_processed = 0

    grid_schools = [s for s in School.objects.filter(is_active=True) if is_grid_eligible(s.type)]
    for school in grid_schools:
        schools_processed += 1
        site_type = normalize_site_type(school.type)

        if not school.school_uid:
            # No SCH-XXXXX key: child sessions can't be joined for this school.
            integrity["unmatched_schools"].append(school.name)

        seeded = programmes_from_site_type(school.site_type)
        integrity["unknown_site_type_tokens"] |= seeded["unknown_tokens"]

        identities = (
            masi_child_identities(school.school_uid, year)
            if school.school_uid
            else {MASI_LITERACY: set(), NUMERACY: set()}
        )

        # Fold in Zazi (Increment 2): resolved identities join the dedup union;
        # the full reach is written as the zazi_izandi children_count below.
        zazi_here = zazi_by_uid.get(school.school_uid) if school.school_uid else None
        if zazi_here is not None:
            identities[ZAZI_IZANDI] = zazi_here["child_uids"]
            integrity["unresolved_zazi_participants"] += zazi_here["unresolved"]

        youth_here = youth_by_school.get(school.id, {})

        # Programmes present = seeded (site_type) + youth-derived + computed-children.
        programmes_present = set(seeded["programmes"]) | set(youth_here)
        for programme in COMPUTED_PROGRAMMES:
            if identities.get(programme):
                programmes_present.add(programme)
        if zazi_here is not None:
            programmes_present.add(ZAZI_IZANDI)

        existing = {
            row.programme: row
            for row in SchoolProgrammeYear.objects.filter(school=school, year=year)
        }

        for programme in programmes_present:
            source = count_source_for(programme)
            basis = count_basis_for(programme, site_type)
            youth_active = youth_here.get(programme, 0)
            system_fields = {
                "youth_active": youth_active,
                "count_basis": basis,
                "as_of": now,
            }
            # Cron owns children_count ONLY for computed programmes (reach =
            # distinct identities). Manual programmes' counts belong to humans.
            if programme == ZAZI_IZANDI and zazi_here is not None:
                # Zazi reach is the full distinct child_count from TeamPact (may
                # exceed the resolved identity set); it's computed only when we
                # actually have Zazi data (else zazi_izandi stays staffing-only).
                source = COUNT_SOURCE_COMPUTED
                system_fields["children_count"] = zazi_here["reach"]
            elif source == COUNT_SOURCE_COMPUTED:
                system_fields["children_count"] = len(identities.get(programme, set()))
            system_fields["count_source"] = source

            row = existing.get(programme)
            if row is None:
                SchoolProgrammeYear.objects.create(
                    school=school, programme=programme, year=year, **system_fields
                )
                rows_created += 1
            else:
                SchoolProgrammeYear.objects.filter(pk=row.pk).update(**system_fields)
                rows_updated += 1

        # School-level derived stats (shared with the human-edit path).
        recomputed = recompute_school_year_stats(
            school, year, now=now,
            identities=identities, programmes_present=programmes_present,
        )
        # A school with manual reach but no identities (and no whole-school
        # override) computes unique from an empty union -- surface it.
        if (not recomputed["identity_union"]
                and not recomputed["has_whole_school"] and programmes_present):
            integrity["reach_without_identities"].append(school.name)

    integrity["unknown_site_type_tokens"] = sorted(integrity["unknown_site_type_tokens"])
    return {
        "year": year,
        "schools_processed": schools_processed,
        "rows_created": rows_created,
        "rows_updated": rows_updated,
        "integrity": integrity,
        "roster": dict(youth["roster"]),
    }


# --- rollups -> PublishedStat (section 11.8) ----------------------------------

# Writes to NEW, unpublished keys (Jim, 2026-06-18). Zazi-inclusive as of
# Increment 2, but still gated on the child reconciliation gap, so they stay
# internal (NOT on the live hero_* donor stats) until that gap closes and Jim
# promotes them.
_ROLLUP_GROUP = "grid_internal"
_ROLLUP_SOURCE = "School Programme Grid (api.school_programme)"
_ROLLUP_NOTE = (
    "Zazi-inclusive: within-Masi programmes (Literacy/Numeracy, identity-deduped) "
    "plus Zazi iZandi (reach from TeamPact; cross-programme dedup for the Zazi "
    "children resolved to canonical, the rest pending the child reconciliation). "
    "Computed nightly from the School Programme Grid; unpublished -- not donor-facing "
    "until the reconciliation gap closes."
)


def _upsert_internal_stat(key, numeric, label, population, as_of):
    from api.models import PublishedStat

    PublishedStat.objects.update_or_create(
        key=key,
        defaults=dict(
            value=f"{int(numeric):,}",
            numeric_value=float(numeric),
            label=label,
            source_system=_ROLLUP_SOURCE,
            population=population,
            methodology_note=_ROLLUP_NOTE,
            as_of=as_of,
            is_published=False,
            group=_ROLLUP_GROUP,
        ),
    )


def rollup_to_published_stats(year):
    """Roll the grid up to PublishedStat: #1 children (Zazi-inclusive), #8 schools
    by type, #9 total sites. Writes unpublished internal keys only.

    A site is "active" if it has any child beneficiary this year: unique
    beneficiaries > 0, or a programme row carrying a positive children_count
    (manual reach without identities still marks the site active).
    """
    from django.utils import timezone

    from api.models import School, SchoolProgrammeYear, SchoolYearStats

    stats_by_school = {
        s.school_id: s for s in SchoolYearStats.objects.filter(year=year)
    }
    schools_with_child_counts = set(
        SchoolProgrammeYear.objects.filter(
            year=year, children_count__gt=0
        ).values_list("school_id", flat=True)
    )

    children_total = 0
    schools_primary = 0
    schools_ecd = 0
    for school in School.objects.filter(is_active=True):
        if not is_grid_eligible(school.type):
            continue
        stats = stats_by_school.get(school.id)
        unique = (stats.unique_beneficiaries if stats else None) or 0
        if unique <= 0 and school.id not in schools_with_child_counts:
            continue  # not an active site this year
        children_total += unique
        site_type = normalize_site_type(school.type)
        if site_type == PRIMARY:
            schools_primary += 1
        elif site_type == ECD:
            schools_ecd += 1

    sites_total = schools_primary + schools_ecd
    as_of = timezone.now().date()
    _upsert_internal_stat(
        "grid_children", children_total,
        "Children on a Masi programme", f"{year}", as_of,
    )
    _upsert_internal_stat(
        "grid_schools_primary", schools_primary,
        "Active primary schools", f"{year}", as_of,
    )
    _upsert_internal_stat(
        "grid_schools_ecd", schools_ecd,
        "Active ECD centres", f"{year}", as_of,
    )
    _upsert_internal_stat(
        "grid_sites_total", sites_total,
        "Total active sites", f"{year}", as_of,
    )
    return {
        "children": children_total,
        "schools_primary": schools_primary,
        "schools_ecd": schools_ecd,
        "sites_total": sites_total,
    }


# --- grid service: read, edit, rollover (section 9) ---------------------------

def _to_float(value):
    return float(value) if value is not None else None


def _iso(dt):
    return dt.isoformat() if dt else None


def serialize_cell(row):
    """The grid-read shape of one programme cell. Single source of truth so the
    read pivot and the create endpoint return identical JSON. Only a manual
    children_count is human-editable; computed cells are read-only.
    """
    return {
        "id": row.id,
        "children_count": row.children_count,
        "count_source": row.count_source,
        "count_basis": row.count_basis,
        "percent_of_school": _to_float(row.percent_of_school),
        "youth_planned": row.youth_planned,
        "youth_active": row.youth_active,
        "as_of": _iso(row.as_of),
        "updated_at": _iso(row.updated_at),
        "editable": row.count_source == COUNT_SOURCE_MANUAL,
    }


def serialize_year_stats(stats):
    if stats is None:
        return None
    return {
        "id": stats.id,
        "total_kids_in_school": stats.total_kids_in_school,
        "pct_african": _to_float(stats.pct_african),
        "pct_coloured": _to_float(stats.pct_coloured),
        "pct_white": _to_float(stats.pct_white),
        "pct_female": _to_float(stats.pct_female),
        "demographic_source": stats.demographic_source,
        "unique_beneficiaries": stats.unique_beneficiaries,
        "as_of": _iso(stats.as_of),
        "updated_at": _iso(stats.updated_at),
    }


def build_grid(year):
    """Pivot the grid for a year: schools (with any programme row) as rows,
    programmes as columns. Computed cells are flagged not-editable. Serializable.
    """
    from api.models import School, SchoolProgrammeYear, SchoolYearStats

    rows = SchoolProgrammeYear.objects.filter(year=year)
    by_school = defaultdict(dict)
    for row in rows:
        by_school[row.school_id][row.programme] = row

    school_ids = list(by_school.keys())
    schools = {s.id: s for s in School.objects.filter(id__in=school_ids)}
    stats_by_school = {
        s.school_id: s
        for s in SchoolYearStats.objects.filter(year=year, school_id__in=school_ids)
    }

    school_list = []
    for school_id in sorted(school_ids, key=lambda i: schools[i].name):
        school = schools[school_id]
        cells = {
            programme: serialize_cell(row)
            for programme, row in by_school[school_id].items()
        }
        school_list.append({
            "school_uid": school.school_uid,
            "name": school.name,
            "site_type": normalize_site_type(school.type),
            "stats": serialize_year_stats(stats_by_school.get(school_id)),
            "cells": cells,
        })

    return {
        "year": year,
        "programmes": [{"key": key, "label": label} for key, label in PROGRAMME_CHOICES],
        "schools": school_list,
        "roster": compute_youth_active()["roster"],
    }


# Human-editable fields by surface (everything else is system-owned).
_EDITABLE_CELL_FIELDS = ("percent_of_school", "youth_planned")
_EDITABLE_STATS_FIELDS = (
    "total_kids_in_school", "pct_african", "pct_coloured", "pct_white",
    "demographic_source",
)


def apply_cell_edit(cell_id, fields, user):
    """Apply a human edit to a programme cell. children_count is editable only for
    manual programmes (editing a computed cell raises ValueError). Writes only the
    edited human fields via save(update_fields=...) so system columns are untouched.
    """
    from api.models import SchoolProgrammeYear

    row = SchoolProgrammeYear.objects.get(pk=cell_id)
    changed = {f: fields[f] for f in _EDITABLE_CELL_FIELDS if f in fields}
    if "children_count" in fields:
        if row.count_source == COUNT_SOURCE_COMPUTED:
            raise ValueError(
                "children_count is computed for this programme and cannot be edited."
            )
        changed["children_count"] = fields["children_count"]

    if changed:
        for field, value in changed.items():
            setattr(row, field, value)
        row.updated_by = user
        row.save(update_fields=list(changed) + ["updated_by", "updated_at"])
    return row


# The grid's known programme keys (the SchoolProgrammeYear.programme choices).
_PROGRAMME_KEYS = frozenset(key for key, _label in PROGRAMME_CHOICES)


def create_cell(school_uid, programme, year, user):
    """Declare a programme at a school for a year (the "click to add" path).

    Seeds the SAME system-owned config the nightly cron would (count_source +
    count_basis from the per-programme policy), but never invents a children_count:
    the human/cron fills the count later. Idempotent -- an accidental double-click
    returns the existing row untouched rather than erroring or duplicating.
    """
    from api.models import School, SchoolProgrammeYear

    if programme not in _PROGRAMME_KEYS:
        raise ValueError("Unknown programme.")
    try:
        school = School.objects.get(school_uid=school_uid)
    except School.DoesNotExist:
        raise ValueError("School not found.")

    existing = SchoolProgrammeYear.objects.filter(
        school=school, programme=programme, year=year
    ).first()
    if existing is not None:
        return existing

    return SchoolProgrammeYear.objects.create(
        school=school,
        programme=programme,
        year=year,
        count_source=count_source_for(programme),
        count_basis=count_basis_for(programme, normalize_site_type(school.type)),
        youth_active=0,
        updated_by=user,
    )


def delete_cell(cell_id, user):
    """Remove an accidental empty add. Only a truly-empty cell may be deleted, so
    a real (data-bearing) cell is never destroyed by an errant click. A row counts
    as having data if any human/computed count is present (children_count or
    youth_planned set, or youth_active > 0).
    """
    from api.models import SchoolProgrammeYear

    row = SchoolProgrammeYear.objects.get(pk=cell_id)
    if (row.children_count is not None
            or row.youth_planned is not None
            or row.youth_active > 0):
        raise ValueError("Cell has data; clear it before removing.")
    row.delete()
    return None


def apply_stats_edit(stats_id, fields, user):
    """Apply a human edit to a school's year-stats (enrolment + race estimates).
    Editing total_kids_in_school recomputes the dependent rollup immediately
    (section 12), in the same transaction the caller provides.
    """
    from api.models import SchoolYearStats

    stats = SchoolYearStats.objects.get(pk=stats_id)
    changed = {f: fields[f] for f in _EDITABLE_STATS_FIELDS if f in fields}
    if changed:
        for field, value in changed.items():
            setattr(stats, field, value)
        stats.updated_by = user
        stats.save(update_fields=list(changed) + ["updated_by", "updated_at"])
    if "total_kids_in_school" in changed:
        recompute_school_year_stats(stats.school, stats.year)
    return SchoolYearStats.objects.get(pk=stats_id)


def rollover_grid(from_year, to_year):
    """Copy each school's programme + stats STRUCTURE forward to a new year, with
    all counts reset blank (Jim, section 9 -- staff confirm fresh). Idempotent:
    skips rows that already exist for to_year.
    """
    from api.models import SchoolProgrammeYear, SchoolYearStats

    existing_cells = set(
        SchoolProgrammeYear.objects.filter(year=to_year)
        .values_list("school_id", "programme")
    )
    new_cells = [
        SchoolProgrammeYear(
            school_id=row.school_id, programme=row.programme, year=to_year,
            count_basis=row.count_basis, count_source=row.count_source,
            children_count=None, percent_of_school=None,
            youth_planned=None, youth_active=0, as_of=None,
        )
        for row in SchoolProgrammeYear.objects.filter(year=from_year)
        if (row.school_id, row.programme) not in existing_cells
    ]
    SchoolProgrammeYear.objects.bulk_create(new_cells)

    existing_stats = set(
        SchoolYearStats.objects.filter(year=to_year).values_list("school_id", flat=True)
    )
    new_stats = [
        SchoolYearStats(school_id=school_id, year=to_year)
        for school_id in SchoolYearStats.objects.filter(year=from_year)
        .values_list("school_id", flat=True)
        if school_id not in existing_stats
    ]
    SchoolYearStats.objects.bulk_create(new_stats)

    return {"rows_created": len(new_cells), "stats_created": len(new_stats)}
