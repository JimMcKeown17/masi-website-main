# Backend Build Log

Last updated: 14 August 2026

This is the project-level implementation and release log for the Django repository. It starts with the current work rather than reconstructing older history. Domain history and source topology remain in `data_map.md` and `airtable_pipeline_sync.md`.

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
- Release state of the latest entry: implemented and verified by the focused and complete SQLite-backed Django suites; rollout is authorized but not yet committed, migrated, scheduled, deployed, or verified live.

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
