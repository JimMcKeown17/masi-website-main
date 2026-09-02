# Masi Data Map: entities, events, and how it is all wired

Status: reference snapshot, verified July 2026 by a full sweep of both backend repos and the Next.js frontend.

This is the system-wide map of Masinyusane's data operations: every capture tool, both canonical Postgres stores, the sync and compute layer, the serving channels, and the dashboards they feed. It is the written companion to the leadership page at `/operations/data-map` on the website (which renders from `frontend/masi-website/src/lib/data-map/config.ts`). When the wiring changes, update this file, that config, and the sibling docs below together.

Sibling docs (this file is the map; those are the manuals):
- `etl_data_architecture_plan.md`: strategic roadmap (raw / canonical / reporting layers, canonical-key strategy, phased plan).
- `airtable_pipeline_sync.md`: operational sync convention, verified Airtable base/table IDs, join keys, data-quality traps.
- Frontend counterpart: `frontend/masi-website/documentation/data-architecture.md` (three-backend topology, WIG integration decisions).

---

## 1. The mental model

Three kinds of data, one rule.

- **Canonical entities (the nouns):** children, youth, schools, staff. Each exists exactly once, with a permanent ID. Small, precious, hand-maintained registries.
- **Events (the verbs):** sessions, assessments, visits, closures. High-volume, append-only, each row carrying the IDs of the entities it happened to.
- **Derived data (the answers):** summaries, caches, published stats. Rebuilt by machines on a schedule, never hand-edited. If a derived number is wrong, the fix is upstream.

**The rule: every event must name its entities.** An event that cannot resolve its child/school/youth key is an orphan: the work happened, but no child gets credit, no school total moves, no WIG ring fills. Orphan prevention is a management job (clean IDs at capture), which is why every domain has a steward (section 9).

This is the classic warehouse distinction between dimension tables and fact tables, applied org-wide.

## 2. Capture layer (where staff type things in)

| Tool | Status | Feeds | Notes |
|---|---|---|---|
| Airtable | live | Masi backend | Staff-facing entry for all Masi programmes: child/school/youth/staff registries, literacy and numeracy sessions, assessments |
| Teampact | live | Zazi backend | The app Zazi iZandi EAs use in the field; source of all Zazi sessions, EGRA assessments, mentor visits |
| Website forms | live | Masi backend | Mentor visit forms, closure calendar, grid planning cells; written directly, no sync lag |
| Masi Field App | field test | Masi backend (future sync) | React Native app on its own Supabase Postgres (`MASI_SUPABASE_URL`); read live today by `/operations/field-app` |
| ZZ Mobile App | arriving | Zazi backend (future sync) | Also Supabase-backed; push notifications already wired through the Zazi backend (`/api/mobile-notifications/...`, Expo + `ZZ_SUPABASE_*`) |

Legacy/occasional: CSV backfills (both backends), SurveyCTO (Zazi, superseded by Teampact).

## 3. Masi backend (`masi_database`, Django + Postgres on Render)

The organisation's centre of gravity. Owns the canonical registries, receives every Masi-programme event, and is the only API the website calls. All models in `api/models.py`.

### Canonical entities

| Entity | Table | Keys | Scale (Jul 2026) | Source and cadence |
|---|---|---|---|---|
| Children | `canonical_children` (CanonicalChild) | `child_uid` CH-XXXXX (unique), `mcode` (unique int, cross-year), `participant_id` (Teampact bridge), upsert on `source_airtable_id` | 10,700+ | Airtable Child Registry (base `app6ayjg1NwvYdZQf`), nightly `sync_airtable_children` |
| Schools | `api_school` | `school_uid` SCH-XXXXX (unique), `airtable_id`, `school_number` | 341 | Airtable schools base, nightly `sync_airtable_schools` |
| Youth | `api_youth` | `youth_uid` YTH-XXXX (unique), `employee_id` (unique int), canonical Airtable ID from Youth Basic Data | hundreds | Airtable Youth Basic Data, enriched through its one-to-one Combined Youth Data link for four subsidy fields; nightly `sync_airtable_youth` (hard-deletes orphans transactionally) |
| Staff | `staff` | `employee_number` (unique int), upsert on `source_airtable_id` | | Airtable staff base, on demand `sync_airtable_staff` |
| Mentor | `api_mentor` | optional OneToOne to User | | Seeded/manual, not Airtable-synced; visit models FK to `User`, not this |

### Event streams

| Stream | Table | Grain | Links to | Source and cadence |
|---|---|---|---|---|
| Literacy sessions | `literacy_sessions_2026` | one session, exactly 2 children | CH x2, SCH, YTH (resolved FKs), business key `session_uid` | Airtable, twice-daily `sync_airtable_literacy_sessions_2026` |
| Numeracy sessions | `numeracy_sessions_2026` | one group session, 3 to 10 children | `child_uids` JSON of CH, SCH, YTH | Airtable, twice-daily `sync_airtable_numeracy_sessions_2026` |
| Literacy assessments | `literacy_assessments_2026` | one child per term (long format), 11 sub-scores | CH (FK); soft-retire via `is_active`/`last_seen_at` | Airtable Assessments DB (base `appEcfbzkyFQZbwzH`), per window `sync_airtable_literacy_assessments_2026`; ~13,800 rows |
| Mentor visits | `api_mentorvisit`, `api_yebovisit`, `api_thousandstoriesvisit`, `api_numeracyvisit` | one school visit | School FK, mentor = User FK | Website DRF forms, written live |
| Programme grid | SchoolProgrammeYear | school x programme x year cell | SCH | nightly `refresh_school_programme_grid` (system cols) + manual planning edits; SchoolYearStats per school x year |
| On the programme | `on_the_programme_2026` | one child on roster | `child_uid` unique | Airtable, on demand; ~1,388 rows. Caveat: its `All Sessions Count v2` is NOT a reliable session total |
| Closures & absences | SchoolClosure / StaffAbsence | one non-working day | SCH scope keys / `youth_uid` (SET_NULL, survives re-sync) | Closure calendar UI, written live; `load_public_holidays` |

### Derived and serving

- `PublishedStat`: hand-approved donor-facing numbers; the only figures the public impact pages show. Editorial via admin, seeded by `seed_published_stats`.
- `ZaziOverviewSnapshot`: cached Zazi programme-overview payload, refreshed by `refresh_zazi_overview` via `api/zazi_client.py`.
- `api_airtablesynclog` (AirtableSyncLog): one row per sync run (counts, errors, JSON `details` incl. `retire_skipped`/`dup_uid_skipped` that the parquet export's freshness gates fail closed on).
- Canonical Youth subsidy enrichment receipts use
  `details.subsidy_enrichment.contract_version = youth_subsidy_enrichment_v1`.
  Budget source counts are unavailable until a complete versioned receipt exists; an
  incomplete enrichment preserves the last complete subsidy values.
- Parquet export: `export_literacy_2026_parquet` writes analysis-ready files to the Masi Data Site (Streamlit) repo; `reconcile_literacy_2026` cross-checks against Airtable aggregates.
- Internal identity feed: `/api/identity/export/` (shared secret) serves school/youth identity to the Zazi backend.

### History shelf (kept for comparisons, no longer synced)

`wela_assessments` (2022-2024, keyed on `mcode`), `assessment_2025`, legacy `api_literacysession` / `api_numeracysessionchild` / `api_session`, legacy `api_child` (superseded by CanonicalChild).

## 4. Zazi iZandi backend (`zazi_izandi_db`, Django + Postgres on Render)

Separate repo: `/Users/jimmckeown/Development/Zazi_iZandi_Website_2025`. Teampact-fed, fully instrumented for the Zazi programme, serves aggregates to the Masi backend over a shared-secret API. The website never calls it directly. All 2026 models in its `api/models.py`; syncs run as Render cron jobs (in-app scheduler deliberately disabled).

### Sources

- **Teampact Analytics API** (Bearer `TEAMPACT_API_TOKEN`): `sync_teampact_sessions_2026`, `sync_assessments_2026` (EGRA; baseline surveys 815/816/817/805, midline 880/881/882/891), `sync_mentor_visits_2026` (survey 824), `sync_teampact_participants`, `sync_teampact_users`. Nightly around 02:00, computes after.
- **Masi backend over HTTP** (`MASI_API_BASE_URL` + `X-Internal-Auth`): `sync_masi_identity` and `sync_masi_calendar` pull the identity feed and closures/absences into local caches.
- CSV backfills (grades, rosters) and legacy SurveyCTO.

### Canonical entities

| Entity | Table | Keys | Source |
|---|---|---|---|
| Education assistants | `api_educationassistant` | `user_id` (Teampact, unique), email, employment status | Teampact roster + sessions |
| Participants (children) | `teampact_participants` | `participant_id` (PK), class enrolments JSON | Teampact nightly |
| Identity maps | SchoolIdentity2026 / YouthIdentity2026 | `school_uid` / `youth_uid` mapped to Teampact names (youth matched on email) | Pulled from the Masi identity feed |

### Event streams

| Stream | Table | Grain | Keys | Scale (Jul 2026) |
|---|---|---|---|---|
| Sessions | `sessions_2026` | one child's attendance at one session (letters taught, blending, flags) | `attendance_id` PK, `participant_id`, `user_id` | 134,000+ |
| EGRA assessments | `assessments_2026` (+ `assessment_cells_2026` letter-level detail) | one child per phase (baseline/midline/endline) | `response_id` PK, `participant_id` | 13,600+ (cells ~2.3M) |
| Mentor visits | `mentor_visits_2026` | one quality-observation visit | `response_id` PK | ~100 |

### Derived

Nightly compute commands rebuild: `school_summaries_2026`, `group_summaries_2026`, `child_letter_alignment_2026` (joins sessions to assessments per child: are EAs teaching the right letters), `group_alignment_snapshots_2026`, assessment/mentor-visit JSON caches. `programme_targets` holds the 2026 targets (dosage 2.5/day, on-track 80%, coverage 95%, etc.) in the database, not in code. Parquet backups (`backup_*_to_parquet`) go to the sibling ZZ Data Site repo (`ZZ_DATA_SITE_PATH`); backup/analytics only, never the serving path.

### WIG outcomes computation (for reference)

`/api/wig-outcomes/` (`api/wig_outcomes_2026.py`) computes from the live `assessments_2026` table, not parquet. Latest row per participant per phase, grade backfilled from baseline, nulls count as not-passing. Pass thresholds on `letters_total_correct`: Gr R 20, Gr 1 40, Gr 2 55, ECD 20; targets 0.67/0.67/0.40/0.75. Cohorts classified by `api/cohorts_2026.py` (treatment / SEF / 53 control schools; unknown schools are "other", never control).

## 5. The bridge (data flows BOTH ways)

- **Masi to Zazi:** identity feed (SCH/YTH UIDs) + the closures/absences calendar.
- **Zazi to Masi:** WIG aggregates and outcomes (`/wig/zazi/`, `/wig/outcomes/` Zazi slices), per-school reach for the programme grid (`school-programme-export`).
- **Transport:** server-to-server HTTPS with shared-secret `X-Internal-Auth` headers (`ZAZI_INTERNAL_API_SECRET` / `MASI_INTERNAL_API_SECRET`). No CORS, nothing browser-exposed. The frontend only ever talks to the Masi backend.
- The canonical child record also stores its Teampact `participant_id`, so a child is one child across Airtable, Teampact and (soon) the mobile apps.

## 6. Serving layer

| Channel | Auth | Purpose |
|---|---|---|
| Masi REST API | Clerk JWT | The only API the website calls; role checks (ADMIN / PROJECT MANAGER) happen here |
| Zazi internal API | shared secret | Pre-computed Zazi metrics, consumed only by the Masi backend |
| Published snapshots | public | `/api/impact/published-stats/` for the public impact pages; hourly cache, human sign-off on every number |
| Parquet exports | file drop | Nightly extracts feeding the two Streamlit data portals (Masi Data Site, ZZ Data Site) |
| Supabase direct | server-side key | Field App live view reads the mobile app's tables directly during field test |

## 7. The ID spine

| Key | Identifies | Minted by | Used by |
|---|---|---|---|
| `CH-XXXXX` | a child, across programmes and years | Airtable Child Registry | Masi sessions, assessments, rosters |
| `SCH-XXXXX` | a school | Airtable schools base | everything, both backends |
| `YTH-XXXX` | a youth (coach/EA) | Airtable youth base | sessions, absences, grid, Zazi identity map |
| `mcode` | a child in the 2022-2025 history tables | legacy Airtable | WELA and 2025 assessments, year-on-year growth |
| `employee_number` | a staff member in HR | Airtable staff base | staff table, HR reporting |
| `participant_id` | a child inside Teampact | Teampact | all Zazi sessions/assessments; stored on CanonicalChild as the bridge |
| `user_id` | an EA inside Teampact | Teampact | Zazi sessions, EA roster and performance |
| `response_id` | one submitted Teampact survey | Teampact | Zazi assessments and mentor visits (dedup) |

## 8. Dashboards and their feeds

| Dashboard | Route | Freshness | Reads |
|---|---|---|---|
| WIG Scoreboard | `/operations/wig` | live | Masi sessions + visits (lead measures), Masi assessments (outcomes), Zazi aggregates via the bridge, data-quality checks. The one board spanning both backends |
| Youth Sessions | `/operations/youth-sessions` | live | `literacy/numeracy_sessions_2026`, Youth registry, closures/absences |
| Mentor Visits | `/operations/mentors` | live (also writes) | the four visit tables, schools, mentors |
| School Programme Grid | `/operations/school-programme-grid` | nightly + manual | SchoolProgrammeYear, SchoolYearStats, Zazi reach via bridge |
| Closure Calendar | `/operations/closures` | live (writes) | closures/absences; feeds every "per working day" metric in both backends |
| ETL Preview | `/operations/preview` | live | sync log, per-table counts, orphan-key resolution checks |
| Field App Live View | `/operations/field-app` | live | Masi Supabase tables directly |
| Public Impact pages | `/impact` | snapshot | PublishedStat only |
| Data portals | data.masinyusane.org (+ ZZ Data Site) | external | nightly parquet exports |
| Data Map | `/operations/data-map` | static config | this document, rendered |

## 9. Stewardship register (owners named 2026-07-05)

One steward per domain: the person leadership holds accountable for the data being complete, current and correctly keyed at the source.

| Domain | Entered by | Pipeline | Steward |
|---|---|---|---|
| Child registry | programme admins, Airtable | nightly sync | Tumelo |
| School registry | ops team, Airtable | nightly sync | Tumelo |
| Youth roster | HR, Airtable | nightly sync | Noxolo |
| Staff roster | HR, Airtable | on-demand sync | Zola |
| Literacy & numeracy sessions | coaches, Airtable forms | twice-daily sync | Tumelo |
| Masi assessments | assessors, Airtable Assessments DB | per window | Tumelo |
| Zazi sessions & assessments | EAs, Teampact | nightly sync + recompute | Noxolo |
| Mentor visits | mentors, website forms | written live | Chombe |
| Closures & absences | ops, closure calendar | written live, cached to Zazi | Chombe |
| Published stats | data team, hand-approved | editorial sign-off | Jim |

The register also renders on `/operations/data-map`; keep names in sync with `frontend/masi-website/src/lib/data-map/config.ts`.

## 10. Known gaps and caveats

1. **Airtable audit gap:** most Airtable data reaches Postgres via crons, but not all (e.g. some 2026 baseline assessments lived only in Airtable). A definitive still-only-in-Airtable list is owed.
2. **Canonical fragmentation in Airtable:** the same entity exists in at least two bases (the canonical registry base and the 2026 assessments base's own Child/School/Youth copies).
3. **Key-naming drift:** the ETL plan names `mcode`/`employee_id` as canonical keys; the implemented 2026 models standardised on UID strings (`child_uid`/`youth_uid`/`school_uid`). Reconciling this is the plan's foundational open item.
4. **`On The Programme.All Sessions Count v2`** is a static number, not a live rollup; never treat it as an authoritative session total.
5. **Render runs UTC**, not SAST: "today" queries are off by two hours after 22:00 SAST.

## 11. What changes next

- **Mobile apps replace forms:** the Masi Field App and ZZ Mobile App each run on their own Supabase Postgres. As they go live, nightly syncs will carry their data into the two canonical backends, same pattern as Airtable and Teampact today. Capture tools change; the canonical stores do not.
- **One identity spine:** every new system, including the mobile apps, must carry the UID keys so a child's story stays whole across tools and years.

## Key file paths

- Masi models/syncs: `api/models.py`, `api/management/commands/`, `api/urls.py`, `api/zazi_client.py`
- Zazi (sibling repo): `api/models.py`, `api/management/commands/`, `api/wig_outcomes_2026.py`, `api/cohorts_2026.py`, `api/middleware.py`
- Website page + config: `frontend/masi-website/src/app/operations/data-map/`, `frontend/masi-website/src/lib/data-map/config.ts`, `frontend/masi-website/src/lib/operations/nav.ts`
