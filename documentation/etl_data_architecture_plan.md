# Airtable → Postgres ETL & Data Architecture Plan

Last updated: 2026-03-09

---

# Part 1: Architecture Plan

## Purpose

This document is a practical implementation plan for cleaning up Masinyusane's current Airtable → Django/Postgres data architecture, auditing what currently exists, and moving toward a stable reporting-oriented backend that can power a Next.js dashboard layer.

The goal is not to redesign everything at once. The goal is to:

1. Audit current reality.
2. Identify what is live vs stale.
3. Define a canonical data model.
4. Standardize ETL pipelines from Airtable into Postgres.
5. Make Next.js read from clean canonical tables and reporting views.

---

## Executive Summary

### Current situation

The current system contains a mix of:

- **Canonical relational models** intended to represent real entities: School, Youth, Child, Mentor, Session
- **Imported / denormalized / source-shaped models**: LiteracySession, NumeracySessionChild, WELA_assessments
- **Nightly sync scripts** that populate some tables but not all

This makes it difficult to know which Airtable tables are active, which Django/Postgres tables are still being updated, what data is stale, and how entities are linked across years.

### Target direction

Three conceptual layers:

1. **Raw ingestion layer** — mirrors Airtable closely, used for debugging and traceability
2. **Canonical relational layer** — normalized Postgres tables with stable keys and foreign keys
3. **Reporting / snapshot / frozen layer** — dashboard-friendly views and snapshot tables

### Key design decisions

- `mcode` is the stable canonical child identifier across years and Airtable tables.
- A child moving schools is still the same child — update their record, do not create a duplicate.
- Literacy, numeracy, and 1000 Stories sessions are different business objects — use separate fact tables per program.
- The Next.js site is mostly read-only / reporting-oriented.
- Airtable record IDs are not always trustworthy — staff sometimes recreate rows.

---

## Guiding Principles

1. Audit before redesign. Do not create more sync jobs until current reality is mapped.
2. Use canonical keys. Avoid matching on names where possible.
3. Treat Airtable as operational source input, not final analytics truth.
4. Preserve source lineage. Every canonical row should be traceable to one or more source Airtable records.
5. Separate program fact tables. Do not force literacy, numeracy, and 1000 Stories into one generic session table.
6. Freeze by batch/version, not by chaos. Historical assessment datasets should be preserved intentionally.
7. Build for reporting. Since Next.js is mainly reading dashboards, optimize the Postgres model for clean querying.

---

## Recommended Architecture

### 1. Raw ingestion layer

Captures Airtable records as they arrive, for debugging and reprocessing.

Target tables: raw_airtable_schools, raw_airtable_children, raw_airtable_youth, raw_airtable_literacy_sessions, raw_airtable_numeracy_sessions, raw_airtable_thousand_stories_sessions, raw_airtable_assessments_2024/2025/2026

Each raw table should contain: source Airtable record ID, source table/base name, last modified time, raw payload JSON, extracted key fields, imported timestamp, sync batch ID, optional content hash.

### 2. Canonical relational layer

The real backend for dashboards and APIs.

Master entities: schools, children, youth, mentors

Program fact tables: literacy_sessions, numeracy_sessions, thousand_stories_sessions, mentor_visits, numeracy_visits, yebo_visits, thousand_stories_visits

Assessment families (one table per family, initially):
- wela_assessments
- egra_assessments
- numeracy_assessments

### 3. Reporting / snapshot layer

For dashboard queries and year-end freezes.

Examples: vw_child_latest_school, vw_literacy_sessions_monthly, vw_numeracy_sessions_monthly, vw_assessment_growth_by_child, frozen_2024_wela_export.

When a yearly assessment dataset is finalized, mark and freeze it intentionally — create a batch record, record the source table and import timestamp, flag the batch as final.

---

## Canonical Key Strategy

### Children

Use `mcode` as the canonical business key.
- `mcode` is stable across years
- `mcode` appears across multiple Airtable tables
- Children move schools but remain the same canonical child
- Keep the database PK `id`, add uniqueness constraint to `mcode`
- Use `mcode` for all ETL child matching

### Youth

Use `employee_id` as the canonical business key.

### Schools

Use the most stable school-level business identifier: `school_id`, Airtable record ID if the school row is stable, or a government school code if one exists.

### Sessions

Use source Airtable record ID as the source uniqueness key. Store canonical FKs to child, youth, school, mentor.

---

## Mapping Tables

Mapping tables bridge canonical Postgres records to one or more source-system records. They are valuable when Airtable rows are recreated, IDs change, staff use different source tables, or you need lineage and traceability.

### Recommended mapping tables

`child_source_map`:
- id
- child_id FK
- source_system (e.g. 'airtable')
- source_base
- source_table
- source_record_id
- source_business_key (mcode)
- is_active
- first_seen_at
- last_seen_at
- last_sync_batch_id

Also: `school_source_map`, `youth_source_map`

### ETL pattern using mapping tables

1. Read Airtable row
2. Extract `mcode`
3. Find or create canonical `Child`
4. Upsert `ChildSourceMap` using Airtable record ID + source table
5. Upsert canonical assessment/session record using canonical child FK

---

## Program Fact Tables

Each program fact table should include: id, source_airtable_id, optional source_session_id, child_id FK, youth_id FK, school_id FK, mentor_id FK, session_date, week, month, month_year, program-specific fields, ETL metadata (created_at, updated_at, last_synced_at).

---

## ETL Standard Pattern

Every Airtable sync job should follow this blueprint:

1. Start sync batch — create AirtableSyncLog record
2. Pull source records via Airtable API with pagination
3. Validate required keys (mcode for children, employee_id for youth, etc.)
4. Resolve canonical entities
5. Upsert canonical fact table keyed on source Airtable record ID
6. Update mapping table
7. Log stats: processed, created, updated, skipped, unmatched, errored, completed_at, success/failure
8. Optional alerting if failures exceed threshold

---

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Staff create new Airtable tables without telling us | Full Airtable audit before writing new ETL |
| Airtable rows get recreated, breaking record ID continuity | Use mapping tables + stable business keys (mcode, employee_id) |
| Existing Postgres tables are stale but still queried | Document every consumer before deprecating |
| Assessments vary too much for a single schema | Use assessment-family tables first, generalize later |
| ETL jobs silently fail | AirtableSyncLog on all commands, alerting on failure |

---

## Implementation Roadmap

### Phase 0: Immediate fixes (current focus)

See Part 3 of this document.

### Phase 1: Define canonical model and ETL standard

Finalize canonical keys, design mapping tables, define target canonical fact tables per program, decide which existing models are temporary imports vs long-term canonical, define sync job standard pattern.

### Phase 2: Standardize core entity sync

Build/refactor sync jobs for Schools, Children, Youth. These are the dimensions all program fact tables depend on.

### Phase 3: Refactor program session pipelines

Refactor/build ETL for Literacy Sessions, Numeracy Sessions, 1000 Stories Sessions. Each follows: ingest → resolve canonical entities → upsert canonical fact table → update sync log → capture rejects.

### Phase 4: Assessment architecture cleanup

After sessions/master data are stable: inventory assessment variations by year/program, decide assessment family boundaries, add canonical child linkage to existing assessment tables, add batch/freeze handling.

### Phase 5: Reporting views and Next.js integration

Create reporting-friendly views/materialized views, standardize API queries, document which tables Next.js is allowed to read, remove dependence on stale/legacy tables.

---

# Part 2: Audit Findings (March 2026)

## Models in `api/models.py`

| Model | Type | Status | Key Issues |
|---|---|---|---|
| `School` | Canonical | Good | Has `airtable_id` (unique), `school_id`. May be stale — sync job exists but not scheduled as cron. |
| `Youth` | Canonical | Good | Has `airtable_id`, `employee_id` (unique). May be stale — `import_airtable_youth.py` is a one-off import, not a cron. |
| `Child` | Canonical | Needs work | `mcode` is NOT unique. No dedicated sync job from master Airtable children table. |
| `Mentor` | Canonical | Minor issue | Class Meta verbose_name says "Mentor Visit" — misleading. |
| `MentorVisit` | Operational | Issue | References `User` FK, not `Mentor` FK. |
| `YeboVisit` | Operational | Issue | References `User` FK, not `Mentor` FK. |
| `ThousandStoriesVisit` | Operational | Issue | References `User` FK, not `Mentor` FK. |
| `NumeracyVisit` | Operational | Issue | References `User` FK, not `Mentor` FK. |
| `Session` | Canonical | Good | Has proper FKs (Youth, Child, School, Mentor). |
| `AirtableSyncLog` | Utility | Good | Exists, but only used by the schools sync command. Should be used by all commands. |
| `LiteracySession` | Denormalized | Import-style | All text fields — school/lc/mentor stored as strings, no FKs. Uses `session_id` as upsert key. |
| `NumeracySessionChild` | Denormalized | **CRITICAL** | All text. Sync deletes entire table and rebuilds every run — if sync fails mid-run, table is empty. No AirtableSyncLog. |
| `WELA_assessments` | Denormalized | Legacy-ish | school/mentor as text, mcode not FK. Multi-year via assessment_year field. |
| `Assessment2025` | Semi-canonical | OK for now | Has `airtable_id` and indexed `mcode`. School still as text. |

## Sync Commands

| Command | Destination | Upsert Key | Sync Log | Cron | Risk |
|---|---|---|---|---|---|
| `sync_airtable_schools.py` | `School` | `airtable_id` | Yes | No | Low — but Postgres may be stale |
| `sync_airtable_literacy_sessions.py` | `LiteracySession` | `session_id` | No | Yes (nightly) | Medium |
| `sync_airtable_numeracy_sessions.py` | `NumeracySessionChild` | None (full delete) | No | Yes (nightly) | CRITICAL |
| `sync_airtable_2025_assessments.py` | `Assessment2025` | `airtable_id` | Unknown | No | Low |
| `import_airtable_youth.py` | `Youth` | `employee_id` | Unknown | No (one-off) | Medium |
| `import_airtable_sessions.py` | `Session` | Unknown | Unknown | No (one-off) | Medium |

Legacy/inspection commands in `dashboards/management/commands/`:
- `inspect_sessions_airtable.py` — inspection only, not a sync
- `inspect_youth_airtable.py` — inspection only
- `import_schools_old.py` — legacy, not in use
- `import_visits_old.py` — legacy, not in use

## Confirmed Airtable context

- There is a **separate master Airtable children table** (distinct from the 2025 assessments table) with unique MCodes spanning all years. This has never been synced to Postgres.
- Airtable schools and youth tables are accurate. Postgres equivalents may be stale.
- Only two active cron jobs: literacy sessions and numeracy sessions.
- `AirtableSyncLog` already exists and is well-designed — use it on all commands going forward.

---

# Part 3: Phase 0 Implementation — Four Immediate Tasks

## Task 1: Fix numeracy sync — replace delete+recreate with upsert (CRITICAL)

**File:** `api/management/commands/sync_airtable_numeracy_sessions.py`

**Problem:** Line 114 does `NumeracySessionChild.objects.all().delete()` before bulk_create. If sync fails mid-run, table is empty. Row PKs change nightly. No history. No sync log.

**Changes:**
1. Add `source_airtable_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)` to `NumeracySessionChild` in `api/models.py`
2. Run `makemigrations` and `migrate`
3. Rewrite sync to use `update_or_create(source_airtable_id=record['id'], defaults={...})`
4. Wrap with `AirtableSyncLog` (create at start, `mark_complete()` at end)
5. Track and log created vs updated vs skipped counts

## Task 2: Add AirtableSyncLog to literacy sync

**File:** `api/management/commands/sync_airtable_literacy_sessions.py`

**Problem:** Runs blind — no log of success, failure, or record counts.

**Changes:**
- Add `AirtableSyncLog.objects.create(sync_type='literacy_sessions')` at start
- Add `sync_log.mark_complete(success=True/False)` at end with error capture
- Track created vs updated counts (the command already uses `update_or_create`)

## Task 3: Create `sync_airtable_children.py` — sync from master children table

**File:** `api/management/commands/sync_airtable_children.py` (new)

**Context:** There is a separate Airtable master children table with unique MCodes spanning all years. The `Child` model exists in Postgres but has never had a dedicated sync job.

**Changes:**
1. First, verify no duplicate mcodes in Postgres:
   ```sql
   SELECT mcode, COUNT(*) FROM api_child GROUP BY mcode HAVING COUNT(*) > 1;
   ```
2. If clean, add `unique=True` to `Child.mcode` in `api/models.py` + migration
3. Create new management command following the schools sync pattern:
   - Match on `mcode` (primary) and fall back to `airtable_id` — mcode is more stable
   - Store `airtable_id` for traceability
   - Use `AirtableSyncLog`
   - Support `--dry-run`, `--verbose`, `--limit` flags
   - Never delete children — update or create only
4. Add env vars: `AIRTABLE_CHILDREN_BASE_ID`, `AIRTABLE_CHILDREN_TABLE_ID`

## Task 4: Run existing school sync to refresh Postgres

**File:** `api/management/commands/sync_airtable_schools.py` (already exists, already good)

**Action:**
1. Run `--dry-run` first to preview changes
2. Run live to refresh Postgres schools from Airtable
3. Add to cron schedule alongside literacy/numeracy

---

## Files to Modify/Create

| File | Action |
|---|---|
| `api/models.py` | Add `source_airtable_id` to `NumeracySessionChild`; add `unique=True` to `Child.mcode` after duplicate check |
| `api/management/commands/sync_airtable_numeracy_sessions.py` | Replace delete+recreate with upsert; add AirtableSyncLog |
| `api/management/commands/sync_airtable_literacy_sessions.py` | Add AirtableSyncLog wrapper |
| `api/management/commands/sync_airtable_children.py` | New file — sync from master Airtable children table |

## Verification

1. Check Child mcode duplicates before constraining: `SELECT mcode, COUNT(*) FROM api_child GROUP BY mcode HAVING COUNT(*) > 1`
2. Run numeracy sync twice — row counts should be stable, no delete in logs
3. Check Django admin AirtableSyncLog — entries should appear for literacy and numeracy after each run
4. Run children sync with `--dry-run` first, review before going live
5. Run school sync with `--dry-run` first, review planned changes before applying

---

## Out of Scope for Phase 0

- Mapping tables (ChildSourceMap, SchoolSourceMap, YouthSourceMap) — Phase 1
- Raw ingestion layer — Phase 1
- Normalizing visit models to use Mentor FK instead of User — Phase 2
- Assessment architecture cleanup — Phase 4
- Reporting views and materialized views — Phase 5
- Youth sync rebuild — Phase 2
- 1000 Stories sessions sync — Phase 3
