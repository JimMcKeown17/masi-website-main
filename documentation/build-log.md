# Backend Build Log

Last updated: 31 August 2026

This is the project-level implementation and release log for the Django repository. It starts with the current work rather than reconstructing older history. Domain history and source topology remain in `data_map.md` and `airtable_pipeline_sync.md`.

## 31 August 2026 - Youth Budget actuals publication from management accounts

Status: backend commit `ca97504` is on `main` and `origin/main`, and Render deployed it
successfully as live deployment `dep-dab0c50ae00c73dfdvh0`. Frontend commit `7076c04`
is on `main` and `origin/main`, and both linked Vercel projects deployed it successfully.
The production expenditure dry run succeeded against the selected management workbook,
then Jim explicitly authorized the production write. The guarded apply restated all eight
January-through-August rows, and an independent production readback tied every amount and
source hash to the reviewed snapshot. The authenticated production page now shows
January through August as actual and September through November as projected.

### Source contract

- Jim designated the newest dated workbook in the ignored local
  `/Users/jimmckeown/Development/masi-finance/management_sheets` directory as the complete
  source of truth. The importer does not merge a missing row from another workbook and
  does not preserve older database figures; every month in the selected year-to-date
  snapshot is restated.
- `sync_youth_expenditure` dynamically selects the newest
  `YYYYMMDD - *Management Accounts*.xlsx` file by date prefix, with modification time and
  filename as deterministic same-date tie-breakers. `MASI_MANAGEMENT_SHEETS_DIR`,
  `--workbook-dir`, and `--path` support deployment and explicit-source overrides.
- The importer reads the workbook without modifying it, hashes it before and after the
  read, and aborts if its bytes, size, or modification timestamp change. It requires an
  `Expenditure` sheet and the expected Date, Month, Year, Amount, and Category 1/2/3
  headers.
- Selected-year rows qualify when Category 3 contains `Youth Jobs:` and Category 1 is
  `Children & Youth`. Mentor in Category 3 wins classification priority; otherwise Wind
  Farm in Category 2 or Rural in Category 3 is rural; remaining Youth Jobs rows are core.
  The accounting Month/Year columns control publication, while Date disagreements are
  reported. Actual months must be contiguous from January.

### Publication safety

- The command is a read-only preview unless `--apply` is present. The preview prints the
  absolute source path, SHA-256, source timestamp, row count, data-quality warnings,
  category totals, and differences from the database.
- Rows with Excel category errors are reported and excluded because no Youth Jobs
  classification can be inferred from them. An apply with such rows refuses to run unless
  the operator explicitly passes `--allow-category-errors`.
- Applies run in one transaction and `update_or_create` every month in the full snapshot,
  including historical months. Each database row records source filename, source hash,
  and source row count. The command refuses to move the latest actual month backwards if
  the database contains a later month.
- `openpyxl==3.1.5` is now an explicit backend dependency. The original
  `seed_youth_expenditure_2026` CSV command remains available for legacy/bootstrap use and
  shares the canonical amount parsing and category classification helpers.

### Real-workbook evidence

- Default selection resolved
  `20260829 - Masinyusane Management Accounts.xlsx`, SHA-256
  `81ed709ff0506f574d00e3c9f9852a28b87b421383282135c382d32882262fe6`.
- The 2026 filter classified 2,020 Youth Jobs rows. July is R172,852.53, August is
  R882,963.85, and January through August totals R3,009,253.32.
- Three selected-year rows contain Excel errors in all category columns and remain
  excluded: July R700, August R700, and August R275. They were printed in the preview and
  explicitly acknowledged for the isolated test apply.
- A temporary SQLite database was migrated and received eight January-through-August
  rows from the real workbook. All rows retained the source hash and the aggregate tied to
  R3,009,253.32. Repeating the apply produced zero monthly deltas, demonstrating local
  idempotence without touching production.
- After backend deployment, the production command was run without `--apply` using that
  exact local workbook. It selected the same SHA-256, classified 2,020 Youth Jobs rows,
  reported the same three category errors, and reproduced every local month and category
  total. Its database deltas were January -R271.67, February R0, March -R6,005.80,
  April +R471.67, May R0, June +R11,860.30, July +R172,852.53, and August +R882,963.85.
  It ended with `DRY RUN: no database rows changed`.
- After Jim explicitly authorized the database write, the same command was re-run with
  `--apply --allow-category-errors`. The preflight reconfirmed that the workbook remained
  the newest dated file and its SHA-256 was unchanged. The transaction reported
  `APPLIED: 8 months restated for 2026`.
- A separate production readback returned exactly eight rows with months 1 through 8,
  aggregate R3,009,253.32, and `PROVENANCE_OK True`. Every row contained the selected
  workbook filename, matching SHA-256, and its classified source-row count.
- The authenticated production page then rendered January through August as actual,
  September through November as projected, and the expected core/mentor/rural values and
  accessible SVG descriptions. Desktop light-mode rendering passed. At the mobile
  breakpoint, chart overflow stayed inside its 360-pixel scroller with no body-level
  horizontal overflow, and both the early and later months remained reachable.
- The current application shell exposes no dark-theme control or dark class and reports
  the normal color scheme, so no dark-mode verification claim is made.

### Verification

- `env DATABASE_URL=sqlite:///:memory: PYTHONDONTWRITEBYTECODE=1 venv/bin/python manage.py test api.tests_youth_expenditure_import api.tests_youth_budget.ExpenditureSeedTests`
  - 10 tests passed.
- `env DATABASE_URL=sqlite:///:memory: PYTHONDONTWRITEBYTECODE=1 venv/bin/python manage.py test api.tests_youth_expenditure_import api.tests_youth_budget`
  - 62 tests passed.
- `env DATABASE_URL=sqlite:///:memory: PYTHONDONTWRITEBYTECODE=1 venv/bin/python manage.py test api`
  - all 554 tests passed in 9.101 seconds.
- `env DATABASE_URL=sqlite:///:memory: PYTHONDONTWRITEBYTECODE=1 venv/bin/python manage.py makemigrations --check --dry-run`
  - no migration changes detected.
- `env DATABASE_URL=sqlite:///:memory: PYTHONDONTWRITEBYTECODE=1 venv/bin/python manage.py check`
  - no system-check issues.
- `venv/bin/pip check` - no broken requirements.

### Operational follow-ups

- Correct the three Excel category-error rows in the management workbook when their
  intended categories are known; this publication intentionally excluded their R1,675.
- For future monthly updates, add the newest dated workbook to the ignored local
  `management_sheets` directory, run the production dry run, review its hash, warnings,
  and deltas, and require explicit authorization before `--apply`.
- If the application later introduces a dark theme, add and verify a dark-state treatment
  for this page; the current shell is light-only.

## 14 August 2026 — Backend deployed, bootstrapped, and scheduled in production

Status at 18:32 UTC: backend implementation commit `efbb946` and release-record commit `9e700b3` are on `main` and `origin/main`. Render deployed the web service and rebuilt the cron services from the current branch. The unrelated local `.gitignore` edit remains excluded and uncommitted.

### Migration and production bootstrap

- Migration `0046_airtable_sync_cursor` was applied automatically by the Render web deployment. A subsequent explicit `migrate --noinput` reported no work, and production inspection confirmed both the migration-recorder entry and the `api_airtablesynccursor` table.
- Full literacy bootstrap log 915 processed 25,068 Airtable records: 52 created, 25,016 updated, 0 skipped. The literacy cursor is `2026-08-14T17:19:28.820113+00:00`.
- Full numeracy bootstrap log 916 processed 6,606 Airtable records: 24 created, 6,582 updated, 0 skipped. The numeracy cursor is `2026-08-14T17:23:19.200999+00:00`.
- Production row counts after bootstrap are 25,128 literacy and 6,647 numeracy. Airtable returned 25,120 literacy and 6,630 numeracy records across the pre-existing full run plus bootstrap deltas. The extra 8 literacy and 17 numeracy rows are historical records no longer present in Airtable; guarded deletion or retirement remains explicitly out of scope.
- Direct production incremental smoke logs 917 and 918 both succeeded with zero records fetched, created, updated, or skipped. These runs exercised the real PostgreSQL advisory-lock, Airtable-filter, transaction, and cursor paths.
- The freshness route changed from pre-deploy `404` to unauthenticated `403`, proving that the endpoint is live and protected. Authenticated payload and staff-visible behavior remain frontend release checks.

### Render services and schedules

- Literacy incremental service `sync_youth_sessions_literacy_incremental` (`crn-d9vkvo3m8hqs73dn62p0`) runs `python manage.py sync_airtable_literacy_sessions_2026 --incremental-new` at `0,15,30,45 * * * *`.
- Numeracy incremental service `sync_youth_sessions_numeracy_incremental` (`crn-d9vl15vmal7c73fqkeug`) runs `python manage.py sync_airtable_numeracy_sessions_2026 --incremental-new` at `5,20,35,50 * * * *`.
- Both services use the Starter plan, backend commit `efbb946`, the shared `masi-shared-env` environment group, and workspace-default failure notifications.
- Managed literacy log 919 and numeracy log 920 both completed successfully with zero records fetched, created, updated, or skipped. This proves that both cron services can connect and execute with Render's effective environment.
- The enabled numeracy cadence then fired automatically at 18:20 UTC. Scheduled log 921 completed successfully with zero records fetched, created, updated, or skipped, proving the saved cron schedule itself is active rather than only the manual trigger path.
- The enabled literacy cadence fired automatically at 18:30 UTC. Scheduled log 922 completed successfully with zero records fetched, created, updated, or skipped. Both staggered schedules are therefore verified through their actual cron paths.
- The existing full reconciliation service `sync_airtable_sessions_daily` remains at `0 4,12 * * *` with the literacy and numeracy full commands. It continues to reconcile edits and FK repairs. Its saved command is `sync_exit_code=0; python manage.py sync_airtable_literacy_sessions_2026 || sync_exit_code=1; python manage.py sync_airtable_numeracy_sessions_2026 || sync_exit_code=1; exit $sync_exit_code`. This runs both feeds and exits non-zero if either failed, removing the previous process-status masking while retaining per-feed `AirtableSyncLog` history. Local zsh checks passed for the all-success, literacy-failure, and numeracy-failure branches; the next scheduled full execution remains the Render runtime verification of the wrapper.
- `PYTHON_VERSION=3.13.4` was added to the shared environment group after Render's Python 3.14 default failed to build the pinned scientific dependency stack. Rebuilds succeeded on 3.13.4.

### Environment incident and remaining release work

The shared environment group initially carried a stale localhost `DATABASE_URL`, so the first managed literacy run failed closed before data mutation. During repair, one attempted edit appended the production URL to the stale value, causing a second pre-mutation failure whose private Render log included the production database connection string. The shared variable was then replaced cleanly, and managed logs 919 and 920 proved the repaired value. Do not reproduce the credential. It still requires coordinated rotation across Render and the local production-only configuration after explicit authorization.

Read-only rotation inventory identified the consumers that must move together: `masi-shared-env` is linked to `daily-syncs`, `sync_airtable_sessions_daily`, and both incremental services; the web service has its own `DATABASE_URL`; the retained full cron has a standalone `DATABASE_URL` in addition to the shared group; backend `.env` contains `DATABASE_URL`, `PROD_DATABASE_URL`, `INTERNAL_DATABASE_URL`, and `EXTERNAL_DATABASE_URL`; frontend `.env.local` contains `DATABASE_URL`, `INTERNAL_DATABASE_URL`, and `EXTERNAL_DATABASE_URL`. Values were not revealed during this inventory.

Frontend commit `08764bb` is now on frontend `main`, both Vercel contexts deployed it successfully, and the production protected route redirects unauthenticated users to Clerk. Backend production rollout is otherwise complete. Remaining cross-repository work is to verify the authenticated freshness payload and responsive light/dark dashboard, prove open-page version-driven revalidation, rotate the exposed database credential, update the release logs with those outcomes, and close the handoff.

## 14 August 2026 — Production rollout authorized; pre-release baseline verified

Status at 17:12 UTC: Jim authorized the full backend-first rollout. The source is still uncommitted and no production write, migration, deploy, sync, or schedule change has occurred in this finalization pass yet.

### Current source and production baseline

- Backend `main` and `origin/main` both resolve to `1845c32`; the Youth Sessions reliability work remains the only intended release scope. The unrelated local `.gitignore` edit for a youth-payments CSV remains explicitly excluded.
- Production has not applied migration `0046_airtable_sync_cursor`, and the cursor table does not yet exist.
- Production contains 25,076 literacy session rows and 6,623 numeracy session rows.
- The most recent full syncs completed successfully on 14 August: literacy processed 25,016 records from 12:01–12:06 UTC, and numeracy processed 6,582 records from 12:06–12:07 UTC. The preceding 04:00 UTC runs and 13 August runs were also successful.
- The production freshness URL currently returns `404`, as expected before this backend source is deployed.
- Live, read-only Airtable preflights requested every selected literacy and numeracy field used by the new importer. Both requests returned HTTP 200 with a record and no unknown-field error.

### Current Render baseline

- Existing cron job: `sync_airtable_sessions_daily` (`crn-d3skb1ili9vc73algubg`), Frankfurt region, Standard instance, auto-deploy on commit from backend `main`.
- Current schedule: `0 4,12 * * *` (04:00 and 12:00 UTC).
- Current command: `python manage.py sync_airtable_literacy_sessions_2026; python manage.py sync_airtable_numeracy_sessions_2026`.
- The service links the `masi-shared-env` environment group plus the session-specific Airtable variables; no new secret values are required.
- Cron notifications use the workspace default, which sends failure notifications.
- Operational caveat to resolve during schedule finalization: the semicolon deliberately lets numeracy run after a literacy failure, but the final numeracy exit status can mask the earlier failure at the process level. Per-feed `AirtableSyncLog` records still preserve each command outcome.

### Verification rerun against the current working tree

- `env DATABASE_URL=sqlite:///:memory: PYTHONDONTWRITEBYTECODE=1 venv/bin/python manage.py test api.tests_airtable_sync api.tests_sync_health api.tests_sync_session_commands` — 16 tests passed.
- `env DATABASE_URL=sqlite:///:memory: PYTHONDONTWRITEBYTECODE=1 venv/bin/python manage.py makemigrations --check --dry-run` — no model/migration drift.
- `env DATABASE_URL=sqlite:///:memory: PYTHONDONTWRITEBYTECODE=1 venv/bin/python manage.py check` — no system-check issues.
- `env DATABASE_URL=sqlite:///:memory: PYTHONDONTWRITEBYTECODE=1 venv/bin/python manage.py test api` — all 547 API tests passed in 15.887 seconds.
- `git diff --check` — passed.

### Authorized next sequence

1. Commit and push only the backend reliability files and this release record.
2. Wait for the backend web and cron services to deploy that commit successfully.
3. Apply migration `0046_airtable_sync_cursor` to production.
4. Run separate full literacy and numeracy bootstraps and verify logs, row counts, and cursors.
5. Create separate, staggered 15-minute incremental jobs, retain an off-hours full reconciliation, and keep failure notifications enabled.
6. Deploy the paired frontend, then perform authenticated live freshness and automatic-revalidation checks before closing the handoff.

## 10 August 2026 — Finalization handoff recorded

The 4 August Youth Sessions work remains present but uncommitted and without production proof. The canonical cross-repository handoff is `../../frontend/masi-website/documentation/handoffs/2026-08-10-youth-sessions-sync-finalization.md`, and both repositories’ `AGENTS.md` and `CLAUDE.md` now require the next conversation to raise it with Jim. No implementation, test, deployment, migration, sync, or Render schedule was changed or re-verified in this documentation-only pass.

## Maintenance contract

Every material backend change must update this file in the same change. Each entry must distinguish source implementation, local verification, migrations, scheduling, deployment, and live data proof. Unfinished release work remains listed until verified closed.

## Current snapshot

- Runtime: Django 5.1+, Django REST Framework, PostgreSQL in production, Clerk JWT authentication.
- Session facts: `LiteracySession2026` and `NumeracySession2026`, idempotently keyed by unique Airtable record ID.
- Audit history: `AirtableSyncLog` records attempts, counts, errors, completion, and structured details.
- Incremental control state: `AirtableSyncCursor` stores the acknowledged Airtable creation-time watermark separately from audit history.
- Release state of the latest entry: backend committed, migrated, deployed, bootstrapped, and verified through automatic production schedules; frontend deployed. Authenticated dashboard behavior and database credential rotation remain open.

## 4 August 2026 — Incremental session ingestion and freshness control plane

Status: local implementation verified; production release work outstanding.

### Problem

The literacy and numeracy jobs scanned their complete Airtable tables on each run. With more than 22,000 literacy rows, a full pass took roughly four to five minutes and the twice-daily cadence left staff-facing data silently stale between runs.

### Built

- Added migration `0046_airtable_sync_cursor` and the one-row-per-feed `AirtableSyncCursor` model.
- Added a shared Airtable client with retained query parameters across pagination, selected-field requests, 30-second timeouts, bounded retry for rate limits and transient server errors, and per-feed PostgreSQL advisory locks.
- Added an immutable `CREATED_TIME()` watermark with a five-minute replay overlap.
- Added `--incremental-new` to both 2026 session commands. Default invocation remains a full upsert.
- Made upsert, cursor advancement, and successful log completion one database transaction. Failed database work cannot advance the cursor.
- Limited the existing-record lookup to incoming Airtable IDs, avoiding a full PostgreSQL ID scan on small incremental runs.
- Full runs initialize or advance the cursor from the sync start, closing the race where records are created during a long paginated scan.
- Added authenticated `GET /api/youth-sessions/freshness/` with fresh, syncing, stale, failed, and never-synced states. It evaluates the newest attempt as well as the newest success, so a recent failure cannot hide behind an older green log.
- Added configurable `YOUTH_SESSIONS_SYNC_CADENCE_MINUTES` (default 15) and `YOUTH_SESSIONS_STALE_AFTER_MINUTES` (default 30).

### Safety model

The incremental cursor answers “which immutable Airtable creation times have been durably acknowledged?” It does not attempt to encode audit history. The replay overlap and Airtable-record-ID upserts provide at-least-once ingestion without duplicate database rows.

### Verification

- `env DATABASE_URL=sqlite:///:memory: PYTHONDONTWRITEBYTECODE=1 venv/bin/python manage.py test api.tests_airtable_sync api.tests_sync_health api.tests_sync_session_commands` — 16 tests passed.
- `env DATABASE_URL=sqlite:///:memory: PYTHONDONTWRITEBYTECODE=1 venv/bin/python manage.py makemigrations --check --dry-run` — no model/migration drift.
- `env DATABASE_URL=sqlite:///:memory: PYTHONDONTWRITEBYTECODE=1 venv/bin/python manage.py check` — no system-check issues.
- `env DATABASE_URL=sqlite:///:memory: PYTHONDONTWRITEBYTECODE=1 venv/bin/python manage.py test api` — all 547 API tests passed.

### Production release work still required

1. Deploy the backend and apply migration `0046_airtable_sync_cursor`.
2. Run one successful full literacy and numeracy sync after deployment. This is the authoritative bootstrap and also verifies selected Airtable field names against the live schema.
3. Create frequent Render cron jobs for each command with `--incremental-new`; target cadence is every 15 minutes. Separate jobs are preferred so one feed’s failure cannot mask or suppress the other.
4. Retain a daily off-hours full run for edit/FK reconciliation.
5. Verify new Airtable rows reach PostgreSQL within the promised cadence, then verify the freshness endpoint changes version and the open frontend dashboard revalidates.
6. Configure Render failure notifications and alert when no successful run lands within the 30-minute freshness window.

Do not enable the incremental schedule before the migration and successful full bootstrap. An unbootstrapped incremental command fails closed by design.

### Known boundary

This slice incrementally ingests newly created records. The Airtable session tables do not currently expose a suitable last-modified field, so edits remain the responsibility of the daily full upsert. The existing full sync does not reconcile source deletions; guarded deletion/retirement semantics are a later slice and must not be claimed as complete.

## Open follow-ups

- Add a suitable Airtable last-modified field and extend the watermark to incremental edits.
- Design guarded fact-record retirement or deletion reconciliation with anomaly thresholds and explicit recovery behavior.
- Add external alert delivery for stale/failed `AirtableSyncLog` health; the endpoint and UI now expose the state, but no paging channel is configured here.
