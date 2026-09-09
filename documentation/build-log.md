# Backend Build Log

Last updated: 8 September 2026

This is the project-level implementation and release log for the Django repository. It starts with the current work rather than reconstructing older history. Domain history and source topology remain in `data_map.md` and `airtable_pipeline_sync.md`.

## 4 September 2026 - Finance read capability

Status: implementation commit `eeab6526a1b47e2babf9993995365d7c38b12b4b` is on
`main` and `origin/main`. Render deployment `dep-dadhtj95efls7395vrm0` reached
`Live` for that exact commit in 1m38s, applied migration `0050`, and passed the
approved production role and capability checks.

- One evaluator table maps Django permission `api.read_finance` to application capability
  `finance.read`. `finance.publish` is reserved in the capability vocabulary but has no
  Django permission until WP2. The evaluator returns a sorted list, gives `ADMIN` an
  explicit application override, reads direct and group permissions without Django's
  `has_perm` superuser shortcut, and fails closed for anonymous, inactive, or profile-less
  users.
- Migration `0050_finance_read_capability` declares the custom permission and idempotently
  creates `Finance Managers` with that grant. It assigns no users and preserves existing
  memberships and unrelated group grants. Its reverse removes only this grant from the
  group, preserving the group and any members.
- `/api/me/` now returns the evaluator's sorted `capabilities` list alongside the existing
  profile fields. `IsFinanceReader` uses the same evaluator, so the UI contract and API
  trust boundary cannot drift into separate role rules. `/api/finance/snapshot/` remains
  the single response endpoint; no per-surface endpoint or permission was introduced.
- RED evidence was captured before implementation: the ADMIN `/api/me/` contract failed
  with missing `capabilities`, and the fresh-database group contract failed because
  `Finance Managers` did not exist. Each turned green after its corresponding evaluator
  and migration slice.
- Focused finance capability and snapshot endpoint checks: 20 tests passed. Full
  `manage.py test api`: 626 tests passed with two existing skips. `manage.py check` passed,
  and `makemigrations --check --dry-run` reported no changes. These automated checks used
  in-memory SQLite; the Render and production checks below are separate evidence.
- Render's exact deployment log showed
  `Applying api.0050_finance_read_capability... OK`. A privacy-safe production readback
  then confirmed migration `0050` is recorded, `Finance Managers` has
  `api.read_finance`, the group has zero members, and `api.publish_finance` does not
  exist.
- The read-only production role check used existing active profiles and the deployed
  source views without printing identities or finance payloads. `STAFF` received HTTP
  403 from `/api/finance/snapshot/` and an empty finance capability list from `/api/me/`;
  `PROJECT MANAGER` received 403 and an empty list; `ADMIN` received 200 and
  `["finance.read"]`. No production row was changed.

## 4 September 2026 - Youth Budget reads restricted to programme managers

Status: implementation commit `8e8c2fe` is on `main` and `origin/main`. Render deployment
`dep-dadhba3m8hqs73fheen0` reached `Live` for that exact commit in 1m58s, with no
migrations to apply. The approved production role check passed.

- `GET /api/youth-budget/` and `POST /api/youth-budget/preview/` now use the same
  `IsAdminOrProjectManager` trust boundary as the Youth Budget write endpoints. The
  permission message is generic because the class protects WIG, School Programme, and
  Youth Budget surfaces rather than WIG alone.
- RED was captured separately for each endpoint before its implementation change:
  `VIEWER` received HTTP 200 from summary, then HTTP 200 from preview, while each new
  acceptance test required HTTP 403. Each test turned green after only its endpoint's
  permission decorator changed.
- The final endpoint tests deny `VIEWER`, `STAFF`, `MENTOR`, `FUNDER`, `YOUTH`, an
  unknown role, an authenticated user without a profile, and an anonymous request.
  Both `ADMIN` and `PROJECT MANAGER` are positively covered on both endpoints.
- `YouthBudgetEndpointTests`: 22 tests passed. The focused Youth Budget plus shared
  permission regression set: 210 tests passed with one optional fixture skip. Full
  `manage.py test api`: 614 tests passed with two existing skips. `manage.py check`
  passed, and `makemigrations --check --dry-run` reported no changes. These automated
  checks used in-memory SQLite.
- The production check used existing active profiles and invoked the deployed source
  views against the production database without printing identities or payloads. A
  `STAFF` profile received HTTP 403 from both summary and preview; a `PROJECT MANAGER`
  profile received HTTP 200 from both. The saved 2026 scenario already existed before
  the summary calls, so the check was read-only and changed no production row.

## 4 September 2026 - Finance access hotfix: ADMIN only

Status: hotfix commit `dc74019` is on `main` and `origin/main`. Render deployment
`dep-dadglenavr4c73asv8b0` reached `Live` for that exact commit in 1m39s. The backend
trust boundary is production-verified; the paired Project Manager Clerk/browser check is
recorded as pending in the frontend release log.

- `GET /api/finance/snapshot/` now admits only an authenticated user whose Django
  `UserProfile.role` is `ADMIN`. `PROJECT MANAGER`, every other role, a missing profile,
  and anonymous access fail closed. WIG, closures, School Programme Grid, and youth-budget
  permissions are unchanged in this release.
- RED: the new Project Manager endpoint test received HTTP 200 instead of the required 403.
  GREEN: after separating `IsFinanceReader` from `IsAdminOrProjectManager`, the same test
  received 403 and the response retained a finance-specific denial message.
- `api.tests_finance_snapshot.FinanceSnapshotEndpointTests`: 8 tests passed.
- `api.tests_finance_snapshot`: 30 tests passed with one optional fixture check skipped.
- Full `manage.py test api`: 609 tests passed with two existing skips.
- `manage.py check` passed and `makemigrations --check --dry-run` reported no changes.
- All automated tests used in-memory SQLite. Separately, a privacy-safe read-only check ran
  the deployed finance view against the production database with an existing Project Manager
  profile and returned HTTP 403 with `Finance dashboards are limited to admins.` No identity
  fields were printed and no production row was changed. This proves the backend permission
  trust boundary; it does not substitute for a real Clerk/browser session.

## 4 September 2026 - Finance snapshot production release

Status: finance API commit `e0a0267` is on `main` and `origin/main`. Render deployment
`dep-dadg0uqjnfac73fm00vg` reached `Live` for that exact commit in 1m43s. The
production database contains the approved 2026 finance snapshot.

### Deployment and migration proof

- Render's build completed successfully and deployed the finance model, loader, and protected
  endpoint. The subsequent explicit production `migrate --noinput` reported `No migrations to
  apply`, proving the build had already advanced production through migration
  `0049_finance_snapshot`.
- An anonymous production request to `/api/finance/snapshot/?year=2026` returned 403, proving
  the deployed route is present and retains its role gate. Authenticated production UI proof
  remains a separate boundary; the available browser was signed out.

### Publication proof

- The source workbook SHA-256 was
  `9784baa19fc5b2288e7b5afdc81f8a653109bb571ff4cfbc619cfd1e49f8f532`.
  Candidate run `2026-09-04T17:29:01Z-9784ba` carried payload SHA-256
  `6c50654af4903ba6c38991cfcb17086f9948646bf488c02d57f5205bf579c7e8`.
- The production dry run found no existing 2026 snapshot and matched schema 1.0.0, 50
  contracts, 342 contract lines, 32 coverage groups, 733 findings, 26 in-scope findings, and
  nine in-scope errors. It emitted no anti-rollback refusal, so `--force` was not used.
- The exact previewed file was applied with `--apply`. Privacy-safe ORM readback returned
  exactly one 2026 row and reproduced both full hashes, the run ID, all structural counts, and
  every per-code/severity/scope finding count.

## 3 September 2026 - Real finance snapshot loaded into isolated PostgreSQL

- The corrected `20260901 - Masinyusane Management Accounts.xlsx` published as run
  `2026-09-03T16:37:09Z-31ed61`. The source workbook SHA-256 is
  `31ed6169075fcd90f4c29e0d3dda0f3ff22583a48cfcec59156357d81d722b09`; the canonical
  figures SHA-256 is `6c50654af4903ba6c38991cfcb17086f9948646bf488c02d57f5205bf579c7e8`.
- The loader's read-only preview accepted the forward move from the 31 August fixture to the
  1 September real workbook. `--apply` then restated only accounting year 2026 in
  `masi_finance_dashboard_local`. PostgreSQL readback returned exactly one snapshot with the
  same run ID, both hashes, schema 1.0.0, 50 contracts, 342 lines, 32 coverage groups, and 733
  findings. The existing `masi_db` and all production, internal, and external databases were
  untouched.
- Current-year findings were deliberately preserved in the stored payload: nine acknowledged
  `OVER_ALLOCATED_ROW` errors (R14,611.82 excess), six `CATEGORY_NOT_IN_BLOCK` warnings, one
  `STALE_CACHED_SPENT` warning, five `ASSERTED_LINE` notices, and five `MISSING_BUDGET` notices.
  There are no current-year orphan or missing contract keys, and all 50 contract codes are
  present and unique.
- The six category warnings remain operator-visible: GYD travel/meetings/other fees; KWF
  interns/field monitors; KWF travel/meetings/other fees; Tsitsikamma Skills Development
  books/laptops/printing/T-shirts; Tsitsikamma Skills Development ad-hoc support; and Zazi NMB
  travel. The stale-cache warning is TSI Skills `Other`: recomputed R4,400 versus cached R0;
  published figures use the recomputed value.
- `KWF-NGO-26` currently records an R80,000 budget and R160,000 allocated across three ledger
  rows (R79,900, R100, and R80,000), so its published remaining balance is negative R80,000.
  This was preserved as source truth rather than silently corrected.
- An anonymous request to the local finance endpoint returned 403. The authenticated browser
  proof and responsive rendering are recorded in the frontend build log. This is local evidence
  only: no production migration/load, merge, push, deployment, or production API check occurred.

## 2 September 2026 - Finance snapshot local PostgreSQL proof

- Created the isolated local PostgreSQL database `masi_finance_dashboard_local`, owned by the existing
  local `jim` role. The existing `masi_db` data was not changed, and no production, internal, or external
  database URL was used.
- Applied the backend migration graph through `api.0049_finance_snapshot`, previewed
  `api/test_data/finance-snapshot-example.json` with no write, then applied that reviewed fixture.
  ORM readback returned exactly one `FinanceSnapshot`: accounting year 2026, run id
  `2026-09-01T12:00:00Z-0a1b2c`.
- `manage.py check` against that PostgreSQL database reported no issues. This is local PostgreSQL proof,
  not production migration, deployment, authentication, browser, or real-workbook publication proof.
- The local `.env` database password contains a URI-reserved character that must be percent-encoded for
  ordinary Django/psql URL parsing. These commands normalized it only in process; the secret was neither
  printed nor rewritten.
- Real-workbook publication remains blocked in the publisher before any artifact or database load. After
  correcting the Zazi gross-salary semantics, its dry run reports 14 current-year errors: five missing KWF
  contract keys and nine independently over-allocated expenditure rows. Production follow-ups below remain
  intentionally unperformed.

## 1 September 2026 - Finance snapshot loader and API

- Added `FinanceSnapshot` (migration 0049): one row per accounting year holding the masi-finance
  finance snapshot (schema 1.0.0, `api/contracts/finance-snapshot-1.0.0.json`) with structured
  provenance (run id, workbook name/date/mtime/sha256, payload sha256, published_at, loaded_at).
- Added `load_finance_snapshot <path> [--apply] [--force]`. Read-only preview by default: prints
  provenance, per-contract lifetime / in-year / remaining with deltas against the published row,
  removed contracts, and finding counts. `--apply` re-checks under a row lock inside the write
  transaction and restates the year. An artifact with an older workbook date is refused unless `--force`;
  the same date with a different workbook hash is refused too, since neither publish time nor file mtime
  proves which content is newer; the same workbook with different figures (payload digest) is refused as
  well. Unknown `schema_version` and a payload digest that does not match the figures are refused. The
  schema and fixture copies are pinned by content digest. Run files in masi-finance `outputs/publish/` are
  the publication history.
- Added `GET /api/finance/snapshot/` behind `IsFinanceReader` (ADMIN / PROJECT MANAGER). Negative
  matrix tested: anonymous, VIEWER, FUNDER, STAFF, MENTOR, YOUTH, and profile-less users are refused.
- Golden fixture `api/test_data/finance-snapshot-example.json` is shared with masi-finance and the
  Next.js dashboard; content-digest constants pin both copies in every suite, and a second test compares
  the schema copy with the masi-finance checkout when present.
- Verification: the 29-test finance module passed with one optional sibling-checkout comparison skipped;
  `makemigrations --check --dry-run` reported no changes, a fresh SQLite database migrated through 0049,
  and `check` reported no issues. The full 608-test API run had 605 passes, two skips, and one unrelated
  worktree-location-sensitive literacy-export path failure; that exact test passed on unchanged main in
  its canonical checkout. All database checks used SQLite in memory. This is not production proof.
- Operational follow-ups: migrate production (`scripts/prod_manage.sh migrate`), then publish the first
  real snapshot with `scripts/prod_manage.sh load_finance_snapshot <path>` dry run, review, and only
  then `--apply` with explicit authorisation.

## 1 September 2026 - Independent NYS and SEF theoretical subsidy scenarios

Status: backend commit `5f418f9` and frontend commit `bbcf24b` are on `main` and
`origin/main`. Render deployed the backend as live deployment
`dep-dabnb4rncjis73df5lvg` and applied migration `0048`. Both linked Vercel projects
deployed the frontend successfully. Authenticated production checks verified the saved
zero-SEF state and an unsaved 200-SEF preview. The production Airtable publication and
the shared Budget Scenario remain unchanged.

### Contract and projection policy

- Added an expand-contract `BudgetScenario` schema for independent NYS and SEF
  contribution, full-time count, part-time count, exact start date, and exact end date.
  Migration `0048_budgetscenario_subsidy_schemes` copies existing NYS values into the
  canonical NYS fields and preserves the temporary legacy aliases. Existing rows migrate
  with zero SEF jobs, so the suggested 200-job SEF plan cannot silently alter a shared
  scenario. New unsaved defaults expose the suggested 200 full-time SEF jobs to the UI.
- NYS defaults to R1,900, 127 full-time jobs, 41 part-time jobs, 1 September through
  31 December. SEF defaults to R1,400, 200 full-time jobs, zero part-time jobs,
  1 October through 31 March of the following year. Defaults are derived from the
  scenario year rather than hardcoded to 2026.
- Airtable NYS and SEF assignments are deliberately excluded from V1 projected relief.
  The scenario is a complete theoretical plan applied to current, non-Yebo, non-ringfenced
  core youth. A single shared capacity pool prevents the same modelled youth from
  receiving both subsidies. Requests above current eligible capacity are reported as a
  future-hire shortfall and do not reduce the projection.
- Scheme allocation is deterministic: earlier start dates allocate first, NYS wins an
  exact-date tie, and part-time allocations precede full-time allocations. Proportional
  largest-remainder assignment avoids accidental school-order bias when capacity is
  constrained.
- A scheme contributes its full monthly cap only when its inclusive date interval overlaps
  at least one exact paid school date in that projection month. Contributions are capped
  by earned gross plus UIF and are not prorated by working-day share. A part-time scheme
  removes the youth from Masi payroll from its first qualifying paid date and does not put
  the youth back on Masi payroll after the scheme ends.
- `POST /api/youth-budget/preview/`, the saved scenario endpoint, summary, and projection
  serializers expose canonical scheme fields and backend-authored requested, modelled,
  and shortfall values. Legacy NYS names remain accepted during the compatibility window;
  conflicting canonical and legacy writes fail validation rather than choosing one.
- `Vacancy Start Month` remains an open-post hiring-plan input and is intentionally not
  used to allocate theoretical subsidies to current youth.

### Airtable source-information lane

- Extended `sync_airtable_youth` with a bounded Combined Youth fetch and a one-to-one
  enrichment join. The Combined table's direct `Funder`, `SEF (Current Status)`,
  `SEF Start Date`, and `SEF End Date` fields populate canonical source-only fields on
  `Youth`. The original Basic Airtable record ID remains the local source identity.
- Enrichment is fail-closed. Missing Combined configuration, fetch/schema failures,
  missing links, multiple links, or missing targets do not erase a previously complete
  subsidy snapshot. Basic creates and updates may still publish, but subsidy fields remain
  unchanged for existing rows, new rows remain unknown, and the command exits nonzero.
- The success or failure receipt is versioned. The summary endpoint uses the latest
  complete receipt for source counts and freshness; if the latest attempt failed it keeps
  the last complete counts and reports the warning. A missing complete receipt produces
  unavailable values, never fabricated zeroes.
- Source counts are organisation-wide informational totals: active employees whose
  `Funder` is NYS, and active employees whose `Funder` is SEF with active SEF status.
  They are not combined with the theoretical scenario and do not affect funding verdicts.
- The command now rejects an empty canonical Airtable result before orphan calculations,
  performs creates, updates, and orphan deletion in one transaction, requests only the
  required stable fields, and makes a dry run execute the complete transform and report
  all would-change and enrichment counts without writing.

### Verification

- `env DATABASE_URL=sqlite:///:memory: PYTHONDONTWRITEBYTECODE=1 venv/bin/python manage.py test api.tests_youth_budget api.tests_sync_airtable_youth api.tests_youth_budget_migrations`:
  all 93 focused projection, API, Airtable, and migration tests passed.
- `env DATABASE_URL=sqlite:///:memory: PYTHONDONTWRITEBYTECODE=1 venv/bin/python manage.py test api`:
  all 579 API tests passed after the final Combined-field correction.
- `env DATABASE_URL=sqlite:///:memory: PYTHONDONTWRITEBYTECODE=1 venv/bin/python manage.py check`:
  system check passed with no issues.
- `env DATABASE_URL=sqlite:///:memory: PYTHONDONTWRITEBYTECODE=1 venv/bin/python manage.py makemigrations --check --dry-run`:
  no model changes beyond checked-in migration `0048` were detected.
- A fresh disposable SQLite database migrated from zero through `0048` successfully,
  including the legacy-to-canonical data copy.
- A real read-only Airtable dry run initially failed closed because the draft requested
  old lookup-style field names from the Combined table. A field-name-only inspection
  identified the direct Combined fields, the mapping was corrected, and the complete
  backend suite was rerun.
- The final real Airtable dry run fetched and enriched 1,898 canonical youth: all 1,898
  links matched one-to-one, with zero missing links, multiple links, or missing targets.
  Against the disposable 12-row fixture it reported 1,886 would-create, 12 would-update,
  zero would-skip, and zero would-delete. Those database deltas describe only the
  disposable fixture, not production. The command ended with `DRY RUN`; no local fixture
  or production database rows changed.
- Render identifies `5f418f9` as the last successfully deployed feature commit.
  Deployment `dep-dabnb4rncjis73df5lvg` completed in 1m41s; its log records
  `Applying api.0048_budgetscenario_subsidy_schemes... OK`, a successful build, Gunicorn
  startup, and the service becoming live.
- Both Vercel deployment contexts completed successfully for frontend commit `bbcf24b`.
- The authenticated production page loaded the canonical NYS and SEF fields from the
  migrated saved scenario: 127 NYS full-time, 41 NYS part-time, NYS R1,900 from
  1 September to 31 December, and zero saved SEF jobs with the R1,400, 1 October to
  31 March suggestion visible.
- Selecting `Use planned 200` without saving requested 368 combined jobs, modelled the
  full shared capacity of 323, assigned 155 modelled SEF jobs after NYS, and reported
  45 jobs requiring future hires. The at-plan headline moved from R688,314 over budget
  to R254,314 over budget. `Reset to saved` restored zero SEF and the R688,314 headline.
  No Save action was used.
- Desktop and narrow responsive production renderings were inspected. The two new scheme
  cards, source warning, combined status, date controls, and moved Holiday Pay and Mentor
  Reserve fields fit the narrow viewport. The pre-existing 850-pixel Funding Pots table
  remains the only wide element and stays clipped by its existing bounded scroller.
- A production-database `sync_airtable_youth --dry-run` then fetched 1,898 canonical youth
  and reported zero creates, 1,898 updates, zero skips, zero orphan deletes, 1,898 matched
  enrichment links, and zero missing links, multiple links, or missing targets. It ended
  in dry-run mode and changed no production rows.

### Release work still required

1. Obtain fresh count-specific authorization before publishing the reviewed production
   dry-run result: zero creates, 1,898 updates, zero skips, zero orphan deletes, and all
   1,898 enrichment links matched. Re-run the preflight immediately before `--apply` and
   stop if any count changes.
2. After an authorized apply, read back the complete source receipt and source-only
   NYS/SEF counts. Do not infer publication from the successful dry run.
3. Exercise a saved exact-date boundary only when an operator intends to replace the
   shared scenario; live deployment verified the controls and unsaved 200-SEF preview but
   deliberately did not press Save.
4. Treat activating 200 SEF jobs in the shared Budget Scenario as a separate scenario
   write requiring explicit operator intent; the migration and deployment did not do it.

## 1 September 2026 - Budget horizon, working-date provenance, and preview API

Status: backend commit `4392964` and frontend commit `39ff288` are on their respective
`main` and `origin/main` branches. Render deployed the backend successfully as live
deployment `dep-dabij415efls739n0sl0` and applied migration `0047`. Both linked Vercel
projects deployed the frontend successfully. Authenticated production browser checks
verified the live default and Mid-November preview paths without saving shared state.

### Backend contract and policy

- Added `BudgetScenario.last_paid_programme_date` with migration `0047` and the requested
  default of 30 November 2026. The value must be inside the scenario year and no later
  than the supported 2026 horizon. It caps the exact in-term weekday list used for core
  and rural wage calculations.
- Projection rows now expose `working_dates` as ISO dates alongside `school_days`. This
  makes the costed calendar inspectable and keeps the frontend from recreating term,
  holiday, or horizon policy.
- Added authenticated `POST /api/youth-budget/preview/`. It overlays validated draft
  fields on the saved scenario in memory, recalculates all dependent outputs, and performs
  no database write. Scenario persistence remains restricted to ADMIN and PROJECT MANAGER
  through the existing PATCH endpoint.
- Added a unique ringfenced committed/at-plan monthly projection for the chart. It costs
  the union population once, while existing per-pot projections remain independent for
  funder feasibility and surplus reporting.
- Added a mentor operating estimate equal to the arithmetic mean of the latest three
  published `MonthlyYouthExpenditure.mentor_amount` values. The response includes method,
  exact source months and values, and monthly amount. Mentor is a full-month estimate for
  every projected month touched by the horizon and does not alter the core Funding Pot
  verdict.
- NYS policy is unchanged: the monthly contribution is not prorated by working-day share
  and remains capped at the youth's earned gross plus UIF. Core and rural wage earning,
  however, use only the exact eligible dates through the selected end date.

### Verification

- `venv/bin/python manage.py test api.tests_youth_budget`: all 63 tests passed.
- `venv/bin/python manage.py test api`: all 562 tests passed.
- `env DATABASE_URL=sqlite:///:memory: PYTHONDONTWRITEBYTECODE=1 venv/bin/python manage.py makemigrations --check --dry-run`:
  no model changes beyond the checked-in migration were detected.
- `env DATABASE_URL=sqlite:///:memory: PYTHONDONTWRITEBYTECODE=1 venv/bin/python manage.py check`:
  system check passed with no issues.
- Frontend `pnpm test:unit`: all 6 tests passed.
- Frontend `pnpm exec tsc --noEmit` and `pnpm lint` passed; lint retained one unrelated
  existing `image-debug` warning.
- Network-enabled frontend `pnpm build` passed and generated all 27 static pages.
- Render identifies `4392964` as the last successfully deployed commit. Deployment
  `dep-dabij415efls739n0sl0` completed in 1m59s; its log records
  `Applying api.0047_budgetscenario_last_paid_programme_date... OK`, a successful build,
  Gunicorn startup, and the service becoming live.
- Both Vercel deployment statuses completed successfully for frontend commit `39ff288`.
- An authenticated production reload returned the new preview-backed UI and its category
  forecast. The default 30 November path showed 21 November working days and the existing
  core-only R718,965 over-budget headline. Mid-November recalculated to 10 November working
  days and R386,871 over budget, with November core R195,749, mentor R81,586, and rural
  R52,148. Restoring Full November returned the original headline and 21-day projection.
  The test did not invoke Save, so it did not mutate the shared scenario.
- Desktop light-mode and narrow responsive rendering were inspected live. The new date
  control and headline cards fit the mobile viewport; wide Funding Pots content remains in
  its existing bounded horizontal scroller. The application currently has no dark theme,
  so no dark-mode production claim is made.

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

## 2026-09-05 WP2a stage 2A: finance runs foundation

Status: stage 2A implemented and verified on SQLite; PostgreSQL release evidence remains PENDING.
Approved revision 4 at `/tmp/wp2-plan-for-backend.md`; stage 2B is excluded.
The previous localhost:5544 sandbox denial is superseded by the authorized SQLite
workflow. No PostgreSQL or production evidence is claimed.

### SQLite RED evidence (before implementation)

Every module below ran separately with the exact command pattern
`DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py test api.tests_finance_<module> --noinput --verbosity=2`.
Complete logs are in gitignored `venv/wp2-evidence/sqlite-red-<module>.log`.
Missing implementation errors below occurred inside tests, after SQLite database
creation; they are not environment failures. Assertion failures are distinguished
from those prerequisite errors. PostgreSQL-only tests are intentionally skipped.

#### capabilities

```text
FAIL: test_fresh_database_has_an_empty_finance_managers_group_with_the_read_grant (api.tests_finance_capabilities.FinanceManagerMigrationContractTests.test_fresh_database_has_an_empty_finance_managers_group_with_the_read_grant)
AssertionError: False is not true
FAIL: test_exact_released_mapping (api.tests_finance_capabilities.FinancePublishMappingTests.test_exact_released_mapping)
AssertionError: {'api.read_finance': 'finance.read'} != {'api.read_finance': 'finance.read', 'api.publish_finance': 'finance.publish'}
FAIL: test_admin_receives_finance_read_without_a_django_permission_grant (api.tests_finance_capabilities.MeFinanceCapabilitiesTests.test_admin_receives_finance_read_without_a_django_permission_grant)
AssertionError: Lists differ: ['finance.read'] != ['finance.publish', 'finance.read']
Ran 11 tests in 1.133s
FAILED (failures=3)
```

#### capability_migrations

```text
ERROR: test_upgrade_copies_all_read_grants_no_publish_and_reverse_restores (api.tests_finance_capability_migrations.CapabilityMigrationTests.test_upgrade_copies_all_read_grants_no_publish_and_reverse_restores)
django.db.migrations.exceptions.NodeNotFoundError: Node ('api', '0051_finance_runs_foundation') not a valid node
FAIL: test_fresh_install_permissions (api.tests_finance_capability_migrations.CapabilityMigrationTests.test_fresh_install_permissions)
AssertionError: False is not true
Ran 2 tests in 0.083s
FAILED (failures=1, errors=1)
```

#### current

```text
ERROR: test_audit_unknown_fields_and_unsupported_methods_rejected (api.tests_finance_current.FinanceCurrentTests.test_audit_unknown_fields_and_unsupported_methods_rejected)
ImportError: cannot import name 'FinanceRun' from 'api.models'
ERROR: test_compatibility_equal_mismatch_missing_dependency (api.tests_finance_current.FinanceCurrentTests.test_compatibility_equal_mismatch_missing_dependency)
ImportError: cannot import name 'FinanceRun' from 'api.models'
ERROR: test_current_only_approved_and_single_kind_compatible (api.tests_finance_current.FinanceCurrentTests.test_current_only_approved_and_single_kind_compatible)
ImportError: cannot import name 'FinanceRun' from 'api.models'
ERROR: test_list_visibility_detail_and_cursor (api.tests_finance_current.FinanceCurrentTests.test_list_visibility_detail_and_cursor)
ImportError: cannot import name 'FinanceRun' from 'api.models'
ERROR: test_negative_matrix_api_service_commands_and_candidate_visibility (api.tests_finance_current.FinanceCurrentTests.test_negative_matrix_api_service_commands_and_candidate_visibility)
ImportError: cannot import name 'FinanceRun' from 'api.models'
ERROR: test_publish_only_does_not_gain_approved_read (api.tests_finance_current.FinanceCurrentTests.test_publish_only_does_not_gain_approved_read)
ImportError: cannot import name 'FinanceRun' from 'api.models'
Ran 6 tests in 0.009s
FAILED (errors=6)
```

#### facts

```text
ERROR: test_bad_attribution_rolls_back_all_inserts (api.tests_finance_facts.FactsTests.test_bad_attribution_rolls_back_all_inserts)
ModuleNotFoundError: No module named 'api.services'
ERROR: test_duplicate_row_and_stream_constraints (api.tests_finance_facts.FactsTests.test_duplicate_row_and_stream_constraints)
ModuleNotFoundError: No module named 'api.services'
ERROR: test_golden_counts_order_digest_and_attribution (api.tests_finance_facts.FactsTests.test_golden_counts_order_digest_and_attribution)
ModuleNotFoundError: No module named 'api.services'
ERROR: test_insert_failure_rolls_back_rows (api.tests_finance_facts.FactsTests.test_insert_failure_rolls_back_rows)
ModuleNotFoundError: No module named 'api.services'
ERROR: test_materialisation_refuses_failed_and_existing_facts (api.tests_finance_facts.FactsTests.test_materialisation_refuses_failed_and_existing_facts)
ModuleNotFoundError: No module named 'api.services'
ERROR: test_nonzero_and_owned_line_constraints (api.tests_finance_facts.FactsTests.test_nonzero_and_owned_line_constraints)
ModuleNotFoundError: No module named 'api.services'
Ran 6 tests in 0.003s
FAILED (errors=6)
```

#### import

```text
ERROR: test_command_actor_required_and_active (api.tests_finance_import.LegacyImportTests.test_command_actor_required_and_active)
ModuleNotFoundError: No module named 'api.services'
ERROR: test_command_imports_and_exact_preview_writes_nothing (api.tests_finance_import.LegacyImportTests.test_command_imports_and_exact_preview_writes_nothing)
ModuleNotFoundError: No module named 'api.services'
ERROR: test_existing_run_refuses_import (api.tests_finance_import.LegacyImportTests.test_existing_run_refuses_import)
ModuleNotFoundError: No module named 'api.services'
ERROR: test_import_verbatim_provenance_actor_and_replay_after_overwrite (api.tests_finance_import.LegacyImportTests.test_import_verbatim_provenance_actor_and_replay_after_overwrite)
ModuleNotFoundError: No module named 'api.services'
ERROR: test_invalid_provenance_digest_and_insert_failure_write_nothing (api.tests_finance_import.LegacyImportTests.test_invalid_provenance_digest_and_insert_failure_write_nothing)
ModuleNotFoundError: No module named 'api.services'
ERROR: test_snapshot_view_never_reads_legacy_table (api.tests_finance_import.LegacyImportTests.test_snapshot_view_never_reads_legacy_table)
ModuleNotFoundError: No module named 'api.services'
Ran 6 tests in 0.004s
FAILED (errors=6)
```

#### runs_approval

```text
ERROR: test_all_three_rollback_guards_and_override_notes (api.tests_finance_runs_approval.ApprovalTests.test_all_three_rollback_guards_and_override_notes)
ModuleNotFoundError: No module named 'api.services'
ERROR: test_candidate_approval_records_actor (api.tests_finance_runs_approval.ApprovalTests.test_candidate_approval_records_actor)
ModuleNotFoundError: No module named 'api.services'
ERROR: test_current_cannot_be_approved_again (api.tests_finance_runs_approval.ApprovalTests.test_current_cannot_be_approved_again)
ModuleNotFoundError: No module named 'api.services'
ERROR: test_digest_count_pair_and_structural_corruption_refused (api.tests_finance_runs_approval.ApprovalTests.test_digest_count_pair_and_structural_corruption_refused)
ModuleNotFoundError: No module named 'api.services'
ERROR: test_failed_and_never_approved_superseded_refuse (api.tests_finance_runs_approval.ApprovalTests.test_failed_and_never_approved_superseded_refuse)
ModuleNotFoundError: No module named 'api.services'
ERROR: test_failure_injection_keeps_old_current (api.tests_finance_runs_approval.ApprovalTests.test_failure_injection_keeps_old_current)
ModuleNotFoundError: No module named 'api.services'
ERROR: test_findings_require_acknowledgement_and_nonblank_note (api.tests_finance_runs_approval.ApprovalTests.test_findings_require_acknowledgement_and_nonblank_note)
ModuleNotFoundError: No module named 'api.services'
ERROR: test_reapproval_sequence_preserves_uploader_and_acyclic_chain (api.tests_finance_runs_approval.ApprovalTests.test_reapproval_sequence_preserves_uploader_and_acyclic_chain)
ModuleNotFoundError: No module named 'api.services'
ERROR: test_self_cross_tuple_and_existing_cycles_refuse (api.tests_finance_runs_approval.ApprovalTests.test_self_cross_tuple_and_existing_cycles_refuse)
ModuleNotFoundError: No module named 'api.services'
Ran 9 tests in 0.004s
FAILED (errors=9)
```

#### runs_concurrency

```text
Ran 3 tests in 0.000s
OK (skipped=3)
```

#### runs_demote

```text
ERROR: test_command_uses_same_guards_and_audit (api.tests_finance_runs_demote.DemoteTests.test_command_uses_same_guards_and_audit)
ModuleNotFoundError: No module named 'api.services'
ERROR: test_demote_integrity_failure_is_atomic (api.tests_finance_runs_demote.DemoteTests.test_demote_integrity_failure_is_atomic)
ModuleNotFoundError: No module named 'api.services'
ERROR: test_first_real_run_restores_import_and_reapproves (api.tests_finance_runs_demote.DemoteTests.test_first_real_run_restores_import_and_reapproves)
ModuleNotFoundError: No module named 'api.services'
ERROR: test_missing_predecessor_candidate_and_blank_note_refuse (api.tests_finance_runs_demote.DemoteTests.test_missing_predecessor_candidate_and_blank_note_refuse)
ModuleNotFoundError: No module named 'api.services'
Ran 4 tests in 0.003s
FAILED (errors=4)
```

#### runs_model

```text
ERROR: test_actor_and_predecessor_are_protected (api.tests_finance_runs_model.FinanceRunModelTests.test_actor_and_predecessor_are_protected)
ImportError: cannot import name 'FinanceRun' from 'api.models'
ERROR: test_approval_audit_is_paired_and_required (api.tests_finance_runs_model.FinanceRunModelTests.test_approval_audit_is_paired_and_required)
ImportError: cannot import name 'FinanceRun' from 'api.models'
ERROR: test_failed_requires_failure_and_zero_facts (api.tests_finance_runs_model.FinanceRunModelTests.test_failed_requires_failure_and_zero_facts)
ImportError: cannot import name 'FinanceRun' from 'api.models'
ERROR: test_legacy_cannot_be_a_candidate_or_have_producer (api.tests_finance_runs_model.FinanceRunModelTests.test_legacy_cannot_be_a_candidate_or_have_producer)
ImportError: cannot import name 'FinanceRun' from 'api.models'
ERROR: test_status_kind_and_year_are_closed (api.tests_finance_runs_model.FinanceRunModelTests.test_status_kind_and_year_are_closed)
ImportError: cannot import name 'FinanceRun' from 'api.models'
ERROR: test_success_requires_payload_and_digests (api.tests_finance_runs_model.FinanceRunModelTests.test_success_requires_payload_and_digests)
ImportError: cannot import name 'FinanceRun' from 'api.models'
ERROR: test_upload_identity (api.tests_finance_runs_model.FinanceRunModelTests.test_upload_identity)
ImportError: cannot import name 'FinanceRun' from 'api.models'
Ran 8 tests in 0.007s
FAILED (errors=7, skipped=1)
```

#### snapshot

```text
FAIL: test_every_invocation_refuses_before_io_or_database (api.tests_finance_snapshot.LoadFinanceSnapshotCommandTests.test_every_invocation_refuses_before_io_or_database) (args=[], options={})
AssertionError: "retired; use the Upload page" does not match "Error: the following arguments are required: path"
FAIL: test_every_invocation_refuses_before_io_or_database (api.tests_finance_snapshot.LoadFinanceSnapshotCommandTests.test_every_invocation_refuses_before_io_or_database) (args=['missing.json'], options={})
AssertionError: expected retired-command refusal; got Snapshot file does not exist: <clone>/missing.json
FAIL: test_every_invocation_refuses_before_io_or_database (api.tests_finance_snapshot.LoadFinanceSnapshotCommandTests.test_every_invocation_refuses_before_io_or_database) (args=['missing.json'], options={'apply': True, 'force': True})
AssertionError: expected retired-command refusal; got Snapshot file does not exist: <clone>/missing.json
Ran 22 tests in 1.520s
FAILED (failures=3, skipped=1)
```

#### snapshot_compat

```text
ERROR: test_backend_schema_copy_is_packaged_schema (api.tests_finance_snapshot_compat.SnapshotCompatTests.test_backend_schema_copy_is_packaged_schema)
FileNotFoundError: [Errno 2] No such file or directory: '/private/tmp/claude-501/-Users-jimmckeown-Development-masi-finance/ad6dc3ff-eeee-4bc4-995b-e7cdd68661bd/scratchpad/backend-clone/api/contracts/finance-snapshot-1.1.0.json'
ERROR: test_golden_projection_schema_digest_identity_and_new_codes (api.tests_finance_snapshot_compat.SnapshotCompatTests.test_golden_projection_schema_digest_identity_and_new_codes)
ModuleNotFoundError: No module named 'api.finance_snapshot_compat'
Ran 2 tests in 0.004s
FAILED (errors=2)
```

### Implemented

- Added `FinanceRun`, `LedgerRow`, and `LedgerAllocation` in migration
  `0051_finance_runs_foundation`, with version/status/audit checks, one approved run
  per tuple, upload/fact identities, protected audit references, and query indexes.
- Migration creates read/publish permissions, copies every direct and group legacy
  read grant, and grants publish to nobody. Reversal copies current read grants back
  before deleting the new permissions; explicit auth/contenttypes dependencies make
  the reverse historical model state accurate.
- Added only `api.publish_finance -> finance.publish` to the capability evaluator and
  `IsFinancePublisher`; ADMIN receives both registered capabilities. Neither
  superuser nor PROJECT MANAGER/STAFF roles imply grants, and publish does not imply read.
- Shared transactional services use PostgreSQL tuple advisory locks followed by row
  locks. Approval revalidates stored supported versions, facts and summary counts,
  then enforces all three rollback guards, including the same-schema-major payload
  comparison. Demotion approves only the recorded predecessor, records the actor,
  and preserves acyclic multi-step recovery. Injected transition errors roll back.
- Materialisation uses the installed publisher's schema and arithmetic validators,
  then reconstructs persisted facts and reconciles counts/digests, line/contract
  lifetime and accounting-year totals, owned unbound amounts, and adjusted coverage.
  Matched, owned-unbound, and ownerless allocations remain distinct. Empty verified
  ledgers approve successfully. Callers creating candidates must wrap creation and
  materialisation in the same transaction (the stage 2B upload path).
- Exact-target legacy import validates original schema/digest/invariants/provenance,
  retains unknown producer as null, and preserves the original document and timestamps.
  Command preview writes nothing. Replay returns the existing UUID/status/audit from
  FinanceRun without querying FinanceSnapshot, even after legacy-row deletion.
- Original implementation (superseded by D32 below) read approved FinanceRun only. Imported 1.0.0 is verbatim with
  its original wrapper; 2.0.0 projects to packaged 1.1.0 with binding-digest identities,
  all findings, legacy-format run ID, UTC timestamps, and a recomputed flat digest.
- Added list/detail/approve/demote/current endpoints and the import/demote commands.
  Read/publish visibility is independent, mutations reject audit/unknown fields and
  malformed options, and list history uses bounded cursor pagination.
- Retired `load_finance_snapshot` before input/database I/O. A test-only copy of its
  exact pre-WP2 source from `bbfd714` actually executes against a changed synthetic
  artifact: the legacy table changes while snapshot/current/year serving and recovery
  to the import remain unchanged. No live database or workbook was used.
- Added exact `.gitignore` exceptions for the packaged 1.1.0 schema copy and supplied
  synthetic 2.0.0 golden artifact. Their installed-package parity is checked.

### Draft corrections and GREEN evidence

- Replaced the PostgreSQL-only `setUp` assertion with vendor skips. Split upload
  identity (both vendors) from the approved partial-unique constraint (PostgreSQL).
- Original endpoint fixtures now import valid legacy provenance. Replaced the optional
  sibling-checkout schema comparison with the installed-package comparison, removing
  that optional skip and external-checkout dependency.
- The supplied golden artifact does not contain every new finding code; a separate
  synthetic variant checks TEXT_DATE, MISSING_CONTRACT_PERIOD and ORPHAN_CONTRACT_CODE.
- Initial focused GREEN attempt: 54 tests, 1 failure, 3 errors, 1 skip. Fixed the
  serializer's non-field error shape and migration reverse dependencies. Explicitly
  registered compatible producer pairs reuse their registered schema shape while
  validating the stored producer; unregistered pairs still refuse.
- Follow-up focused run: 48 tests passed. Extended tests initially exposed an invalid
  coverage-test assumption: the first golden row is out of accounting year. The
  negative fixture now changes an in-year row; out-of-year facts remain faithfully
  stored. `api.tests_finance_runs_approval api.tests_finance_facts`: 18 tests passed,
  including explicit ANTI_ROLLBACK assertions for each of the three guards.
- `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py test api --noinput`:
  **Ran 675 tests in 17.862s; OK (skipped=7)**. No failures/errors.
- Final exact implementation/test tree, with named skip inventory:
  `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py test api --noinput --verbosity=2`:
  **Ran 675 tests in 18.013s; OK (skipped=7)** — 668 passed. Full log:
  gitignored `venv/wp2-evidence/sqlite-full-suite-final.log`.
- `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py check`:
  **System check identified no issues (0 silenced).**
- `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py makemigrations --check --dry-run`:
  **No changes detected.**
- `git diff --check`: passed. The pre-existing WhiteNoise missing `staticfiles/`
  warning remains in RED and GREEN logs; stage 2A introduced no new warning.
- Initial Git staging and the tests/resources commit succeeded:
  `6037593 test(finance): cover run foundation contracts`. The subsequent
  `git add documentation/build-log.md` and foundation commit were both denied at
  `.git/index.lock` with `Operation not permitted`. Implementation remains staged
  but uncommitted; this updated log also has unstaged evidence changes. The tree is
  intact. No alternate checkout, Git-metadata workaround, push or deployment was used.

### PostgreSQL-only tests (supervisor must execute, not skip)

- `api.tests_finance_runs_model.FinanceRunModelTests.test_partial_unique_current`
- `api.tests_finance_runs_concurrency.FinanceConcurrencyTests.test_two_concurrent_approvals_one_wins_one_refuses`
- `api.tests_finance_runs_concurrency.FinanceConcurrencyTests.test_different_tuples_do_not_share_lock`
- `api.tests_finance_runs_concurrency.FinanceConcurrencyTests.test_import_uses_same_lock_and_replays_after_release`
- `api.tests_finance_runs_concurrency.FinanceConcurrencyTests.test_transition_select_for_update_locks_existing_rows`
- `api.tests_finance_runs_concurrency.FinanceConcurrencyTests.test_concurrent_imports_serialize_before_first_insert`

### Remaining PENDING and evidence boundary

- **Historical commit state:** the supervisor subsequently committed the original
  foundation as `55af11d`; round 1 below starts from that clean tip.
- **PENDING — PostgreSQL full-suite execution belongs to the supervisor and is the
  required release evidence**, including the conditional unique constraint, separate
  connections, advisory-lock contention, and `select_for_update`. SQLite is functional
  evidence only. No PostgreSQL connection was attempted in this continuation.
- **PENDING — existing private-fixture integration test**:
  `api.tests_youth_budget.RealLedgerSeedTests.test_real_csv_parses_june_total_and_trimmed_april`
  is the seventh skip, with reason `real payroll ledger not on this machine`.
  The CSV is absent from this clone. The requested zero-non-PostgreSQL-skips condition
  therefore remains unmet; no fixture was fabricated or copied from another checkout.
- **PENDING — stage 2B** upload endpoint, preflight and benchmarks remain excluded.
  Stage 2A's run-list POST returns 405. D32 moves the dependency pin, build check,
  and required Render token environment variable into the foundation (round 1 below).
  No schedule change is required.
- **PENDING — release/cutover**: deploy and apply migration 0051; perform the approved
  exact-target legacy import/year inventory before run-only readers serve existing
  data; finish stage 2B/capacity gates, real upload/approval, and role/browser probes.
  No production database, script, migration, deployment, import or credentials were
  accessed or changed. This log is not production, browser, or release proof.

### Review fixes, round 1

Binding supervisor decisions D32/D33 supersede the original stage 2A reader and
release split above. Starting tree: clean `feat/wp2a-finance-runs` at `55af11d`;
the prior pending-foundation-commit note is historical.

RED, before implementation:
`DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py test api.tests_finance_review --noinput`
reported **Ran 7 tests in 0.198s; FAILED (failures=6, errors=1)**.
Exact names in `api.tests_finance_review` and observed assertions:

- `DependencyReleaseTests.test_publisher_pin_is_in_deployment_requirements`:
  `AssertionError: Missing pinned publisher deployment dependency` (pin absent).
- `DependencyReleaseTests.test_build_checks_publisher_immediately_after_install`:
  `AssertionError: '' !=` the required import/version check.
- `FoundationSnapshotTests.test_legacy_endpoint_is_unchanged_before_and_after_import`:
  `AssertionError: 404 != 200` before import.
- `ApprovalServabilityTests.test_lowercase_timestamp_approves_and_projects`:
  `ValueError: Invalid isoformat string: '2026-09-01t10:00:00z'`.
- `ApprovalServabilityTests.test_projection_failure_refuses_before_superseding_with_value_free_code`:
  `AssertionError: 200 != 409`.
- `ApprovalServabilityTests.test_projection_schema_failure_refuses_before_superseding`:
  `AssertionError: 200 != 409`.
- `CutoverTimestampTests.test_lowercase_timestamp_approve_then_snapshot_get_200`:
  approval returned 200, then snapshot GET gave `AssertionError: 500 != 200`.

Full RED output: gitignored `venv/wp2-review/red.log`. The first diagnostic run
had 5 tests; its two failure-injection subtests shared a promoted candidate, so
they were separated before the definitive 7-test RED run above.

Foundation changes and GREEN evidence:

- Restored `api/views/finance.py` byte-for-byte from pre-WP2 `bbfd714`; verified
  by comparing file bytes with `git show bbfd714:api/views/finance.py`. It reads
  FinanceSnapshot exclusively. Run endpoints and the compatibility module remain
  available. No runtime fallback was introduced.
- Foundation endpoint fixtures now use legacy rows without importing. The new
  before/import/after regression compares the entire response and the imported
  compatibility wrapper, then deletes the import to prove the reader stays legacy.
  Import/recovery tests exercise the run projection directly in the foundation;
  the separate cutover restores their endpoint-level assertions and run-only years.
- Added the exact D32 private Git pin and immediate post-install import/version
  check, plus local token/manual-wheel instructions in `README.md`. Executed the
  exact import/version check successfully against the already-installed 0.2.0
  wheel. This is NOT a network install or tag/authentication proof; the supervisor
  must verify the dependency install after the tag exists. Render requires the
  `MASI_FINANCE_GITHUB_TOKEN` service secret for the foundation build.
- `utc_seconds` is the single projection timestamp normalizer, using the same
  `upper().replace('Z', '+00:00')` rule as the installed packaged validator.
  Approval uses the real compatibility projection (including its schema and
  invariants) with the exact prospective approval timestamp before demoting or
  promoting any row. Projection failures return only `SNAPSHOT_PROJECTION_INVALID`.
  The same precondition covers re-approval and demotion through shared approval.
- Focused command:
  `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py test api.tests_finance_review api.tests_finance_import api.tests_finance_current api.tests_finance_snapshot api.tests_finance_snapshot_compat api.tests_finance_runs_approval api.tests_finance_runs_demote --noinput`
  — **Ran 62 tests in 3.329s; OK**.
- Foundation full suite:
  `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py test api --noinput`
  — **Ran 681 tests in 18.276s; OK (skipped=7)** (674 passed).
  Six PostgreSQL-only skips and the existing unavailable private payroll fixture
  skip are the same named inventory above. No failures/errors. Full log:
  gitignored `venv/wp2-review/foundation-full.log`.
- `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py check`:
  **System check identified no issues (0 silenced).**
- `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py makemigrations --check --dry-run`:
  **No changes detected.** Migration 0051 is unchanged.
- `git diff --check`: passed. Existing missing-staticfiles warning remains.

Required deploy order (D32): **foundation deploy -> `import_legacy_finance_snapshot`
-> parity check -> cutover deploy**. Deploy the foundation with the dependency secret
and migration 0051 first. Inventory existing years, preview then apply each authorized
exact year/legacy-row/actor import, and compare the full legacy endpoint document and
wrapper with the imported run projection before deploying the separate run-only
reader cutover. The cutover commit title is
`feat(finance): cut the snapshot reader over to finance runs`.
No production access, deployment, import, network installation, PostgreSQL test, or
schedule change was performed here. PostgreSQL execution belongs to the supervisor.
The signed-zero digest regression remains deferred until the rebuilt publisher
wheel is installed; this pass does not alter that contract.

Git/fallback state: staging the named foundation files failed at `.git/index.lock`
with `Operation not permitted`. No new commit was created and no Git-metadata
workaround was attempted. Foundation fixes remain uncommitted. The separate cutover
is supplied as `documentation/wp2a-cutover.patch`, to apply on top of the foundation
and commit last with the title above. The delivered working tree is FOUNDATION.

Separate cutover patch verification (temporarily applied locally, then restored):

- `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py test api --noinput`:
  **Ran 682 tests in 18.510s; OK (skipped=7)** (675 passed; same six PostgreSQL
  tests and one unavailable private payroll fixture). Full log:
  gitignored `venv/wp2-review/cutover-full.log`.
- Includes HTTP candidate approval with `2026-09-01t10:00:00z` followed by snapshot
  GET 200 and canonical `2026-09-01T10:00:00Z`. Legacy-only data returns 404 in the
  cutover; imported 1.0.0 is verbatim with wrapper parity; approved 2.0.0 projects
  to 1.1.0. Restored endpoint tests cover approved-only years, stale-loader
  isolation, no legacy queries, and restoration to the imported predecessor.
- `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py check`:
  **System check identified no issues (0 silenced).**
- `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py makemigrations --check --dry-run`:
  **No changes detected.** `git diff --check`: passed.
- Patch application/reversal is checked against the exact tested file bytes;
  foundation view remains byte-for-byte `bbfd714` after restoration.

#### Separate snapshot reader cutover

This final change applies `feat(finance): cut the snapshot reader over to finance runs`.
The snapshot endpoint now reads only approved FinanceRun rows, returning imported
1.0.0 verbatim or the validated 1.1.0 projection. No runtime fallback exists.
The foundation delivery/patch-preparation state above is historical after applying
this change. Deploy this cutover only after foundation deployment, authorized
legacy import and parity verification. The 682-test cutover verification above
covers this code; PostgreSQL, dependency installation and deployment remain pending.

### Review fixes, round 2

D33 closes review round-1 finding 4. Starting tree: clean standalone clone on
`feat/wp2a-finance-runs` at `1c3e0ad`, with foundation round 1 and D32 cutover
committed. The earlier uncommitted/deferred-wheel notes are historical.
Installed publisher 0.2.0 serializes negative zero as `0.00`; its packaged money
schema still accepts signed zero and leading zeroes, so backend validation must
explicitly enforce the binding D33 representation.

Test inventory addition: `api/tests_finance_signed_zero.py`, `SignedZeroTests`:

- `test_negative_subcent_amount_materialises_with_identical_digests`
- `test_non_canonical_zero_payload_is_refused_value_free`
- `test_reconstruction_normalises_signed_decimal_zero_in_every_money_field`
- `test_money_pattern_refuses_noncanonical_strings`

RED command, before service changes:
`DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py test api.tests_finance_signed_zero --noinput`
— **Ran 4 tests in 0.071s; FAILED (failures=9)**, no errors/skips.
Failing names: `test_non_canonical_zero_payload_is_refused_value_free` (five
subtests: row amount, coverage_amount, coverage spend, contract total, line total),
`test_money_pattern_refuses_noncanonical_strings` (three subtests), and
`test_reconstruction_normalises_signed_decimal_zero_in_every_money_field`.
The real-XLSX regression already passed with released D33 publisher serialization;
it is not claimed as a backend RED failure. Earlier fixture diagnostics used an
unsupported formula shape, then exposed subtest transaction contamination; both
were corrected before this definitive RED run. Log: gitignored
`venv/signed-zero-red.log`.

Implementation and verification:

- `_money_string` is the single formatter for reconstructed row amount,
  coverage_amount and allocation amount, explicitly returning `0.00` for signed
  zero. Raw-cell row-key generation is untouched; the XLSX regression proves that
  raw -0.004 and raw zero retain different D21 keys despite identical money strings.
- The backend's run-2.0.0 schema validation tightens the shared money definition to
  `^-?(0|[1-9][0-9]*)\.[0-9]{2}$`, excludes a trailing newline, and refuses `-0.00`.
  Every referenced money field (including nullable values, derived figures and
  totals) uses that definition. Failure remains the existing value-free
  `SCHEMA_INVALID` / 409; no new error code or legacy schema change.
- The real in-memory openpyxl XLSX contains Expenditure Amount=-0.004 and a
  matching -0.004 allocation with a SUM(SUMIFS(...)) budget binding. Publisher
  rounding omits the zero allocation (zero allocation facts are forbidden).
  Candidate creation uses the existing fixture helper, then real service
  materialisation and approval. Stored-row reconstruction preserves both facts
  and payload digests and approval preserves stored hashes. Stage 2A has no upload
  service/HTTP endpoint; refusal checks the actual service exception/code/status
  with no log records, and the caller's transaction leaves no candidate/fact rows.
  A separate sign-preserving Decimal seam covers every reconstruction money field
  independently of database sign loss.
- Focused GREEN:
  `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py test api.tests_finance_signed_zero --noinput`
  — **Ran 4 tests in 0.063s; OK**, no skips. Log: gitignored
  `venv/signed-zero-green.log`.
- Full GREEN:
  `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py test api --noinput`
  — **Ran 686 tests in 11.170s; OK (skipped=7)**, 679 passed, no failures/errors.
  Log: gitignored `venv/signed-zero-full.log`.
- `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py check`:
  **System check identified no issues (0 silenced).**
- `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py makemigrations --check --dry-run`:
  **No changes detected.**
- `git diff --check`: passed. Existing missing-staticfiles warning remains.

PENDING — supervisor PostgreSQL full-suite gate, including the new real-XLSX
materialisation/approval/digest test. None of the four new tests is PostgreSQL-only;
all run on both databases. The six existing PostgreSQL-only tests are the exact
model/concurrency inventory above. The seventh skip remains the unavailable private
payroll fixture, `api.tests_youth_budget.RealLedgerSeedTests.test_real_csv_parses_june_total_and_trimmed_april`.
This is local SQLite evidence only. No network, PostgreSQL or production access
was attempted. Migration files, the cutover view, requirements and the build script
are unchanged. No new migration, configuration, schedule or one-off operation is
required; deployment/release gates remain as recorded above.

Git/fallback: `git add api/services/finance_runs.py api/tests_finance_signed_zero.py
documentation/build-log.md` failed creating `.git/index.lock` with
`Operation not permitted`. No commit was created; all three files remain intact
and uncommitted. No Git-metadata workaround or alternate checkout was used.
Final `git diff --check`: passed.


## 2026-09-06 WP2a stage 2B

Read approved revision 4 sections 3.5, 3.6, 3.8, 3.9 and 8.1, repository guidance, prior foundation build records and finance endpoint documentation. Existing concurrency module and runs URL are extended, not replaced.

RED before implementation:
`DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py test api.tests_finance_runs_upload api.tests_finance_upload_safety api.tests_finance_runs_concurrency --noinput`
— Ran 29 tests in 0.100s; FAILED (failures=13, errors=18, skipped=6). Subtests account for the failure/error totals. Exact failing names:

```text
ERROR: test_internal_producer_failure_and_untrusted_error_are_not_failed_rows (api.tests_finance_runs_upload.FinanceUploadTests.test_internal_producer_failure_and_untrusted_error_are_not_failed_rows) (error=<class 'RuntimeError'>)
ERROR: test_internal_producer_failure_and_untrusted_error_are_not_failed_rows (api.tests_finance_runs_upload.FinanceUploadTests.test_internal_producer_failure_and_untrusted_error_are_not_failed_rows) (error=<class 'masi_finance.publish.run_artifact.RunArtifactError'>)
ERROR: test_internal_producer_failure_and_untrusted_error_are_not_failed_rows (api.tests_finance_runs_upload.FinanceUploadTests.test_internal_producer_failure_and_untrusted_error_are_not_failed_rows) (error=<class 'masi_finance.publish.run_artifact.RunArtifactError'>)
ERROR: test_known_producer_failure_creates_one_safe_failed_run (api.tests_finance_runs_upload.FinanceUploadTests.test_known_producer_failure_creates_one_safe_failed_run)
ERROR: test_permission_before_bytes_and_unsupported_methods (api.tests_finance_runs_upload.FinanceUploadTests.test_permission_before_bytes_and_unsupported_methods)
ERROR: test_compressed_cap_missing_lying_and_true_length_stops_at_plus_one (api.tests_finance_upload_safety.WorkbookSafetyTests.test_compressed_cap_missing_lying_and_true_length_stops_at_plus_one)
ERROR: test_declared_length_invalid_before_read (api.tests_finance_upload_safety.WorkbookSafetyTests.test_declared_length_invalid_before_read)
ERROR: test_declared_rows_columns_and_product (api.tests_finance_upload_safety.WorkbookSafetyTests.test_declared_rows_columns_and_product)
ERROR: test_defused_xml_rejects_entities (api.tests_finance_upload_safety.WorkbookSafetyTests.test_defused_xml_rejects_entities)
ERROR: test_envelope_type_and_basename (api.tests_finance_upload_safety.WorkbookSafetyTests.test_envelope_type_and_basename)
ERROR: test_missing_duplicate_sheets_and_headers (api.tests_finance_upload_safety.WorkbookSafetyTests.test_missing_duplicate_sheets_and_headers)
ERROR: test_spoofed_dimensions_sparse_headers_and_data_beyond_header (api.tests_finance_upload_safety.WorkbookSafetyTests.test_spoofed_dimensions_sparse_headers_and_data_beyond_header)
ERROR: test_valid_body_above_default_django_memory_limit (api.tests_finance_upload_safety.WorkbookSafetyTests.test_valid_body_above_default_django_memory_limit)
ERROR: test_valid_body_never_accesses_body_and_buffer_closes (api.tests_finance_upload_safety.WorkbookSafetyTests.test_valid_body_never_accesses_body_and_buffer_closes)
ERROR: test_zip_duplicate_and_paths (api.tests_finance_upload_safety.WorkbookSafetyTests.test_zip_duplicate_and_paths)
ERROR: test_zip_encrypted (api.tests_finance_upload_safety.WorkbookSafetyTests.test_zip_encrypted)
ERROR: test_zip_entry_count (api.tests_finance_upload_safety.WorkbookSafetyTests.test_zip_entry_count)
ERROR: test_zip_expanded_and_ratio_limits (api.tests_finance_upload_safety.WorkbookSafetyTests.test_zip_expanded_and_ratio_limits)
FAIL: test_http_request_body_property_is_never_read (api.tests_finance_runs_upload.FinanceUploadTests.test_http_request_body_property_is_never_read)
FAIL: test_mutation_metadata_rejected (api.tests_finance_runs_upload.FinanceUploadTests.test_mutation_metadata_rejected) (field='uploaded_by')
FAIL: test_mutation_metadata_rejected (api.tests_finance_runs_upload.FinanceUploadTests.test_mutation_metadata_rejected) (field='uploaded_at')
FAIL: test_mutation_metadata_rejected (api.tests_finance_runs_upload.FinanceUploadTests.test_mutation_metadata_rejected) (field='status')
FAIL: test_mutation_metadata_rejected (api.tests_finance_runs_upload.FinanceUploadTests.test_mutation_metadata_rejected) (field='manifest')
FAIL: test_mutation_metadata_rejected (api.tests_finance_runs_upload.FinanceUploadTests.test_mutation_metadata_rejected) (field='payload')
FAIL: test_mutation_metadata_rejected (api.tests_finance_runs_upload.FinanceUploadTests.test_mutation_metadata_rejected) (field='producer_version')
FAIL: test_mutation_metadata_rejected (api.tests_finance_runs_upload.FinanceUploadTests.test_mutation_metadata_rejected) (field='approved_by')
FAIL: test_no_temporary_files_or_storage_and_large_http_body (api.tests_finance_runs_upload.FinanceUploadTests.test_no_temporary_files_or_storage_and_large_http_body)
FAIL: test_raw_upload_manifest_version_digests_metrics (api.tests_finance_runs_upload.FinanceUploadTests.test_raw_upload_manifest_version_digests_metrics)
FAIL: test_second_publisher_replay_review_approve_preserves_uploader (api.tests_finance_runs_upload.FinanceUploadTests.test_second_publisher_replay_review_approve_preserves_uploader)
FAIL: test_sheet_failure_is_failed_history (api.tests_finance_runs_upload.FinanceUploadTests.test_sheet_failure_is_failed_history)
FAIL: test_unexpected_failure_rolls_back_all_inserts_value_free (api.tests_finance_runs_upload.FinanceUploadTests.test_unexpected_failure_rolls_back_all_inserts_value_free)
```

Contract clarification: the installed 2.0.0 manifest forbids additional properties. Foundation stores parse_duration_ms, total_duration_ms and peak_memory_bytes in dedicated model fields. Preserve exact manifest/schema compatibility and record measurements in those fields; no migration or schema fork.

Implementation and final verification:

- Added a raw-stream context manager with positive declared-length validation,
  actual-byte cap (including missing/false lengths), SHA-256, dated basename and
  MIME checks. The HTTP view uses the configured WSGI server's framed input rather
  than DRF Request.stream or Django's Content-Length-limited wrapper. It never
  reads request.body or configures Django's upload-memory setting.
- ZIP safety independently inflates bounded chunks with zlib before ZipExtFile
  scanning: actual expanded counts, CRC and consumed compressed sizes must agree.
  This prevents an understated central-directory file_size from hiding expansion.
  Entry/encryption/path/duplicate/ratio/expansion checks precede the tuple lock.
- Defused XML scans metadata, shared-string header markers and sheet coordinates
  with incremental element removal. Required sheets/headers, declared and streamed
  bounds, physical header position, rectangular product and nonblank cells past H
  are checked before the producer. ZIP/XML envelope errors return safe 400 without
  history; known sheet/domain errors create one failed run with fixed phase/code/
  message. Generic decode errors, unknown exception codes, schema/fact corruption
  and internal exceptions return value-free 500 after rollback.
- Uploads use the existing nonblocking tuple lock and global source-SHA/producer
  idempotency key. Replays bypass sheet scanning and production and preserve the
  uploader; a second publisher reviews and approves the original candidate with
  their own approval audit. Candidate creation reuses materialise_facts and the
  existing schema, canonical-zero, digest and persisted-fact reconciliation checks.
  Approval/demotion services, the cutover view, migrations and legacy commands are
  unchanged. The existing runs route now handles POST; PUT/PATCH/DELETE remain 405.
- Measurements include stream/ZIP/preflight/producer/fact insertion and digest
  checks through the final transactional metrics save. Database commit and HTTP
  rendering occur afterward; supervisor end-to-end wall timings must include them.
  The manifest remains exactly the released artifact manifest, with metrics in the
  foundation's existing dedicated fields. Tracemalloc starts/stops with the upload
  scope; overlapping in-process calls conservatively share its peak rather than
  stopping another upload's tracing. Sync upload workers provide isolated scopes;
  absolute process RSS is a separate measurement, not a scoped allocation claim.
- Added benchmark_finance_upload: requires a real active publisher actor, reads the
  named local workbook through the same service (not HTTP), writes candidate/failed
  runs, and emits basename, bytes, SHA, producer/tag, schema, run/status, service
  status, timing/allocation peak, platform-normalized process peak RSS, fact counts
  and DB engine. Idempotent replays are labeled and expose original stored metrics;
  they are not successful recomputation benchmarks.
- Added defusedxml==0.7.1, matching the installed version. build.sh is unchanged.
  No migration, environment-variable change, schedule or one-off operation is
  required by this code change. No network or production access was performed.

Expanded acceptance includes the actual 32 MiB + one-byte stopping point; HTTP
missing/lying lengths; a valid >2.5 MB request under default Django settings; a
request.body property that raises; ZIP metadata understatement; the exact 4,000,000
cell boundary and streamed product evasion; unsafe XML refusal; no temporary-file
or storage calls on upload; real producer/facts/digest/approval and command paths.
Synthetic XLSX/ZIP bodies are generated in tests; no real workbook is committed.

The first full run found one obsolete foundation assertion that POST on runs was
unsupported (721 tests, one failure, nine skips). Updated only that assertion to
PUT in tests_finance_current.py; POST is now explicitly authorized by stage 2B.
An intermediate command test over-mocked all Path.open calls, including installed
schema resources; narrowed its mock to the synthetic input path before final GREEN.

Final GREEN:

- `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py test api --noinput`
  — **Ran 724 tests in 12.277s; OK (skipped=9)**: 715 passed, no failures/errors.
  Log: gitignored `venv/upload-full-green.log`. Existing missing-staticfiles warning
  remains; intentionally malformed ZIP fixture warnings are locally suppressed.
- `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py check`
  — **System check identified no issues (0 silenced).**
- `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py makemigrations --check --dry-run`
  — **No changes detected.**
- `git diff --check` — **passed**.

PENDING — supervisor PostgreSQL full-suite gate. The following eight tests are
PostgreSQL-only; concurrency skips explicitly say
`Requires PostgreSQL advisory locks and separate connections.`:

- `api.tests_finance_runs_model.FinanceRunModelTests.test_partial_unique_current`
- `api.tests_finance_runs_concurrency.FinanceConcurrencyTests.test_two_concurrent_approvals_one_wins_one_refuses`
- `api.tests_finance_runs_concurrency.FinanceConcurrencyTests.test_different_tuples_do_not_share_lock`
- `api.tests_finance_runs_concurrency.FinanceConcurrencyTests.test_import_uses_same_lock_and_replays_after_release`
- `api.tests_finance_runs_concurrency.FinanceConcurrencyTests.test_transition_select_for_update_locks_existing_rows`
- `api.tests_finance_runs_concurrency.FinanceConcurrencyTests.test_concurrent_imports_serialize_before_first_insert`
- `api.tests_finance_runs_concurrency.FinanceConcurrencyTests.test_first_ever_same_tuple_uploads_one_completes_one_conflicts` (new)
- `api.tests_finance_runs_concurrency.FinanceConcurrencyTests.test_different_tuple_uploads_complete_while_first_is_locked` (new)

The ninth skip is the pre-existing unavailable private payroll fixture:
`api.tests_youth_budget.RealLedgerSeedTests.test_real_csv_parses_june_total_and_trimmed_april`.

PENDING — supervisor section 3.8 benchmarks on PostgreSQL and the release build:
largest-valid 20260829 successful full path with facts; historical 20260513 rejection;
sparse/spoofed/product and largest allowed rectangle/string/ZIP envelopes; successful
2,000/10,000/largest duplicate groups; exact source IDs/counts/hashes and scaling;
<60-second full request timing, 512 MiB absolute worker RSS and the >30-second
queue-review trigger. Real workbooks were not available in this clone.

PENDING — supervisor two-upload concurrency probe: same tuple one completion/one
409 while held; different tuples both progress; readers continue serving the prior
approved run; actual WSGI framing/ingress behavior, worker count W>=3, instance memory,
aggregate peak <=75%, and reader latency/status. SQLite passing/skips are not
PostgreSQL, deployment, production-data or capacity evidence.

Git/fallback: staging the twelve named change files failed creating `.git/index.lock`
with `Operation not permitted`. No commit was created. All changes remain intact
and uncommitted in this clone; no Git-metadata workaround or alternate checkout was
used. Final `git diff --check`: passed.

### Review fixes, round 1

Scope: supervisor-authorized stage 2B fixes on the standalone clone at `b84f1d4`,
branch `feat/wp2a-finance-runs`. Read approved plan sections 3.5, 3.8 and 8.1,
`CLAUDE.md`, this log and finance endpoint documentation. No network, production
access, PostgreSQL execution, publisher edits, approval/demotion changes, cutover
changes, migrations or legacy-import changes. All database commands below use
`DATABASE_URL=sqlite:///:memory:` and the clone's `venv/bin/python`.

RED, captured before each corresponding implementation:

1. Package selection, `venv/review-r1-red1.log`:
   `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py test api.tests_finance_upload_safety.WorkbookSafetyTests.test_alternate_selected_workbook_rejected_before_producer api.tests_finance_upload_safety.WorkbookSafetyTests.test_ambiguous_workbook_and_shared_string_selection_rejected api.tests_finance_upload_safety.WorkbookSafetyTests.test_scanned_sheet_paths_match_openpyxl_selected_paths --noinput`
   — **Ran 3 tests in 0.017s; FAILED (failures=4)**. The alternate workbook and
   three ambiguous/default/shared-string selection cases were accepted; the
   canonical path comparison already passed.
   Additional HTTP RED, `venv/review-r1-red1-http.log`:
   `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py test api.tests_finance_upload_safety.WorkbookSelectionHTTPTests --noinput`
   — **Ran 1 test in 0.021s; FAILED (failures=1)**, HTTP 500 instead of the expected
   stable HTTP 400 rejection before producer invocation.
2. D36 measurement semantics, `venv/review-r1-red2.log`:
   `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py test api.tests_finance_runs_upload.FinanceUploadTests.test_upload_records_sampled_process_rss_without_tracemalloc api.tests_finance_runs_upload.FinanceUploadTests.test_process_rss_linux_pages_and_resource_fallback api.tests_finance_runs_upload.FinanceUploadTests.test_rss_sampler_observes_peak_and_stops_on_exception api.tests_finance_runs_upload.FinanceUploadTests.test_benchmark_trace_allocations_is_opt_in_and_separate --noinput`
   — **Ran 4 tests in 1.046s; FAILED (failures=2, errors=2)**: request tracing was
   invoked, the sampler/helper was absent, and the opt-in command flag was absent.
3. Sheet declarations and bounded model batches, `venv/review-r1-red3.log`:
   `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py test api.tests_finance_upload_safety.WorkbookSafetyTests.test_sheet_doctype_or_entity_rejected_before_xml_parser api.tests_finance_runs_upload.FinanceUploadTests.test_materialise_facts_bounds_model_batches_and_preserves_facts --noinput`
   — **Ran 2 tests in 2.285s; FAILED (failures=5)**. Four sheet/declaration subcases
   reached the patched XML parser; the upload attempted an unbounded model batch.

Implementation:

- Verified installed openpyxl `reader/excel.py` (`_find_workbook_part`,
  `read_strings`, `read_workbook`, `read_worksheets`), `reader/workbook.py` and
  `packaging/relationship.py`. The reader selects among XLTM/XLTX/XLSM/XLSX
  content-type overrides before considering defaults, and independently selects
  shared strings by content type. Preflight now defused-parses `[Content_Types].xml`,
  requires exactly one canonical workbook override, rejects competing/default
  workbook selections and duplicate part overrides, and allows only canonical,
  unambiguous shared strings. It parses canonical workbook relationships, rejects
  duplicate IDs and invalid required-sheet relationship types/modes, and uses the
  exact paths openpyxl consumes for accepted packages. Stable failure:
  `WORKBOOK_METADATA_INVALID`, HTTP 400 with no run. The regression archive keeps
  benign canonical parts but selects an alternate workbook/rels with an LCV1 cell;
  both producer and openpyxl mocks remain uncalled. A separate successful fixture
  compares the scanned sheet paths with openpyxl's actual read-only sheet paths.
- D36 removes tracemalloc entirely from the upload service. A per-request thread
  samples `/proc/self/statm` resident pages times page size every 10ms, with
  `resource.getrusage(RUSAGE_SELF).ru_maxrss` as the fallback (bytes on macOS, KiB
  converted to bytes elsewhere). It samples the initial and final RSS and joins
  on success, replay or exception. The stored sample is finalized after fact
  reconciliation, immediately before the metrics save. This is absolute process
  RSS, includes baseline/concurrent activity, and can miss sub-10ms spikes; the
  fallback is the lifetime process high-water mark, not a request-local delta.
  `peak_memory_bytes` keeps its field name; its model field description is a code
  comment so no schema migration is introduced. As already established in stage
  2B, the installed manifest schema has no measurement fields and forbids extra
  properties: measurements remain in the existing FinanceRun metadata fields;
  the exact producer manifest is preserved. The benchmark's `--trace-allocations`
  opt-in adds a separate `python_peak_allocation_bytes`, labels RSS semantics,
  stops its owned tracer in `finally`, and refuses an already active tracer.
- Every required sheet is checked for literal DOCTYPE or ENTITY declarations
  before any XML parser sees its bytes, including UTF-16/32 null-separated forms.
  Stable failure: `SHEET_XML_DECLARATION`, handled as unsafe XML (HTTP 400, no run).
  Ordinary UTF-8 ledger XML is checked for well-formedness by C Expat without
  element callbacks. Compiled byte regexes remove only simple interior cells
  whose columns are within the parsed nonblank H, whose row coordinates fit the
  retained actual row extent, and whose shared-string indexes are valid. All row
  tags, dimensions, headers, outside-H cells and unusual cells survive for the
  original defused checks. Namespace rebinding, comments/CDATA, alternate attribute
  syntax/encodings and complex rows retain the full defused path. No unsafe cell
  is accepted merely because the fast grammar cannot recognize it. Funder Budgets
  retains full defused semantic scanning after the declaration guard. Exact row,
  column, H, R*H, required-header, duplicate-header and beyond-H/formula checks
  remain in place. Differential regression cases compare the fast path with the
  original scanner, including understated extents, escaped/prefixed coordinates,
  invalid shared indexes, blank/nonblank outside-H cells and formula-only cells.
- Fact construction now creates at most 2,000 model instances per batch and calls
  `bulk_create(batch_size=2000)` for both rows and allocations. Only row-key-to-PK
  scalars survive between batches; allocation objects no longer retain row model
  instances. The PK map is released before persisted-ledger reconstruction. The
  service does not retain an explicit serialized JSON payload string alongside
  these batches. The artifact and reconstructed fact dictionaries still exist
  during the required integrity check; digest/count/money reconciliation and the
  enclosing atomic transaction are preserved. The new 4,002-row/4,002-allocation
  regression executes real SQLite inserts, requires three bounded batches of each
  model, and exercises the normal persisted-fact reconciliation.

Producer investigation (installed publisher unchanged):

- Source inspection of `publish/ledger.py:61-89,125-165` shows run-mode
  `read_ledger(bounded=True)` calls `_bounded_headers`, which opens the workbook
  again and streams the entire Expenditure sheet with formulas before the normal
  data-only ledger pass. Legacy `build_snapshot` calls unbounded `read_ledger` and
  performs only the latter pass. This extra full-sheet pass is a concrete likely
  contributor to the supervisor's 11.6s versus 6.05s; the real timings cannot be
  apportioned from source inspection alone.
- Run mode also adds `read_contract_keys` (another workbook open/full budget read),
  full-width bounded budget checks instead of legacy A:F retention during reading,
  fact capture/identity/serialization, and schema-2/fact validation. Source paths
  show five workbook opens versus three in legacy snapshot production. Each open
  rereads shared strings where present. No publisher change or bypass was made.
- Executed an in-memory synthetic 10,001-row/10,001-allocation probe with timing
  wrappers (no tracemalloc): total **2.908s**, five workbook opens **0.015s** total;
  `read_ledger` **1.233s**, including `_bounded_headers` **0.595s**;
  budget blocks **0.008s**, contract keys **0.003s**, rollups **0.091s**,
  ledger facts **0.060s**, serialization **0.047s**, fact validation **0.035s**.
  Timings are inclusive and nested, not additive. This confirms the extra pass,
  not the distribution of the supervisor's real-workbook 11.6s. The synthetic
  workbook has inline strings and cannot quantify repeated real shared-string cost.
  Reproducible local probe: `DATABASE_URL=sqlite:///:memory: PYTHONPATH=. venv/bin/python venv/review_producer_profile.py`.

Fixture correction supplied by the supervisor (not rerun on private workbooks here):
D15's `20260829` is no longer structurally valid under publisher 0.2.0: it predates
contract Start Date and End Date columns and fails preflight with
`CONTRACT_KEY_HEADER`, as does `20260513 copy`. This supersedes the earlier stage
2B pending-fixture description. The largest valid workbook is now `20260901`;
the supervisor benchmarks that file (reported 12,132,538 bytes, 23,914 fact rows,
18,445 allocations). Historical workbook rejections remain separate evidence.

GREEN:

- After item 1: focused safety/upload modules — **39 tests in 0.754s; OK**.
- After item 2: focused safety/upload modules — **43 tests in 0.502s; OK**.
- After item 3 and differential safety regressions:
  `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py test api.tests_finance_upload_safety api.tests_finance_runs_upload --noinput`
  — **50 tests in 4.405s; OK**, `venv/review-r1-green3.log`.
- `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py test api --noinput`
  — **Ran 739 tests in 25.468s; OK (skipped=9)**, 730 passed, no failures/errors.
  Log: gitignored `venv/review-r1-full-green.log`.
- `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py check`
  — **System check identified no issues (0 silenced).**
- `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py makemigrations --check --dry-run`
  — **No changes detected.** No migration, environment variable, schedule or
  one-off data operation is required for these local fixes.
- `git diff --check` — **passed** before the final documentation entry; final
  documentation-inclusive check recorded below.

PENDING — supervisor PostgreSQL full-suite gate. Eight PostgreSQL-only tests keep
named reasons: seven concurrency cases say `Requires PostgreSQL advisory locks
and separate connections.`; the conditional unique-current constraint says
`Requires PostgreSQL conditional unique constraint release evidence.` The ninth,
pre-existing payroll-fixture skip says `real payroll ledger not on this machine`.
The existing missing-staticfiles warning remains. SQLite does not prove PostgreSQL
locking, batching/round trips, release, deployment, production data or field behavior.

PENDING — supervisor re-benchmark of `20260901` with PostgreSQL inserts, without
`--trace-allocations`: target scan <=2s, total <20s, peak RSS <300MB on the supervisor
laptop. These targets are not established by synthetic tests. Also retain the plan's
<60s request/512MiB worker gates, >30s queue-revival review, duplicate-heavy and
maximum-envelope fixtures, historical rejections, same/different-tuple concurrency,
W>=3 reader capacity, aggregate memory <=75%, and release-build/Render timing.
Optional allocation-traced benchmarks must be labeled separately and cannot stand
in for the default request-path latency. No real workbook benchmark ran here.

Additional local scanner timing: the final fast scanner processed a dense synthetic
25,000x76 ledger (1.9 million rectangular cells) in **3.021s**. The unchanged full
defused sheet scanner on the same synthetic fixture took **10.380s** before the
final regex tuning (the earlier fast version took 3.572s). The fast number includes
`scan_workbook`; the baseline times the ledger sheet alone. No RSS or PostgreSQL
claim is attached to this probe, and its 3.021s is not the <=2s current-workbook gate.
Command: `DATABASE_URL=sqlite:///:memory: PYTHONPATH=. venv/bin/python venv/review_scan_benchmark.py`.
Synthetic scripts/logs are local, gitignored evidence under `venv/`; no workbook
bytes or real finance data were added to tracked files.

Git/final verification: staging exactly the seven changed tracked files failed with
`Unable to create .../.git/index.lock: Operation not permitted`. No commit was
created and no Git-metadata workaround was attempted. The pre-existing untracked
`.review-detached.pid` was left untouched. Final documentation-inclusive
`git diff --check`: **passed**. Changes remain local and uncommitted in this clone;
PostgreSQL and real-workbook re-benchmark gates remain PENDING for the supervisor.

### Review fixes, round 2

D38 removes the regex-sliced thin-ledger fast path. The supervisor confirmed on
its private 12,132,538-byte `20260901` workbook that the greedy `[^<>]*` in the
row-1 cell regex consumes the slash in an empty styled cell such as
`<c r="BX1" s="2"/>`. The alternative then matches through row 2's first closing
cell, crossing `</row>`; defusedxml rejects the sliced fragment with a mismatched
tag, mapped to `XML_INVALID`. Synthetic openpyxl fixtures lacked the trailing
self-closing header cells. XML slicing also depends on attribute order and
namespace syntax, so D38 requires removal rather than another regex repair.

RED before implementation (gitignored log `venv/review-r2-red.log`):

```sh
source venv/bin/activate
DATABASE_URL=sqlite:///:memory: python manage.py test api.tests_finance_upload_safety.WorkbookSafetyTests.test_trailing_empty_styled_header_cells_scan api.tests_finance_upload_safety.WorkbookSafetyTests.test_reordered_cell_attributes_scan api.tests_finance_upload_safety.WorkbookSafetyTests.test_namespace_prefixed_cells_scan --noinput
```

**Ran 3 tests in 0.036s; FAILED (errors=2).** The trailing-styled-cell and
reordered-attribute regressions raise `XML_INVALID`; the prefixed-cell control
already passes. All three use literal trailing `<c r="…" s="2"/>` cells (prefixed
in the namespace case), compare acceptance with the canonical workbook and
require populated data beyond the unchanged H to reject with
`LEDGER_DATA_BEYOND_HEADER`.

Implementation: every required sheet part now uses the unchanged streaming
`_xml_events` / defusedxml element checks after the bounded byte-level declaration
guard. Removed `_thin_ledger`, `_SIMPLE_CELLS`, `_ROW`, `_ROW_NUMBER`,
`_decimal_range`, `_CELL_ATTRS`, `_SIMPLE_VALUE`, and the preliminary raw Expat
pass/imports (`ParserCreate`, `ExpatError`) and fast-path encoding detection.
Exact R, H, R×H, actual/declared coordinate bounds, required/duplicate headers,
shared-string validity and beyond-H/formula checks remain unchanged. Canonical
package selection (`WORKBOOK_METADATA_INVALID`), D36 RSS sampling without request
tracemalloc, benchmark `--trace-allocations` opt-in, bounded fact batches and
`SHEET_XML_DECLARATION` rejection before parsers are retained from round 1.

Deleted only these fast-path-internal tests:

- `WorkbookSafetyTests.test_fast_scan_preserves_defused_bounds_and_semantics`
  (compares the two implementations that are now the same scanner).
- `WorkbookSafetyTests.test_fast_scan_discards_only_valid_interior_cells`
  (asserts byte removal by the deleted helper).

The declaration-guard test retains its parser mocks and assertions, removing only
its mock of the deleted `ParserCreate` symbol. No other existing tests changed.
Round 2 modifies only the parser, safety tests and this log; the other four
round-1 files are preserved. No approval/demotion services, cutover view,
migration, legacy import command or publisher package changes were made.

GREEN (all Django commands activate this clone's venv and set
`DATABASE_URL=sqlite:///:memory:`):

- `python manage.py test api.tests_finance_upload_safety api.tests_finance_runs_upload api.tests_finance_runs_concurrency --noinput`
  — **Ran 58 tests in 4.652s; OK (skipped=7)**, 51 passed.
  Log: `venv/review-r2-focused.log`. An earlier focused invocation mistakenly
  named nonexistent `api.tests_finance_upload_http`: 52 tests, one import error;
  corrected to the stage-2B concurrency module above before the final gate.
- `python manage.py test --noinput`
  — **Ran 740 tests in 25.223s; OK (skipped=9)**, 731 passed, no failures/errors.
  Log: `venv/review-r2-full-green.log`. Net test count: 739 + 3 regressions - 2
  deleted fast-path-internal tests = 740.
- `python manage.py check` — **System check identified no issues (0 silenced).**
- `python manage.py makemigrations --check --dry-run` — **No changes detected.**
- `git diff --check` — **passed**; final documentation-inclusive working-tree and
  staged diff checks also passed before commit.

Seven PostgreSQL concurrency tests skip with `Requires PostgreSQL advisory locks
and separate connections.` The unique-current test skips with `Requires
PostgreSQL conditional unique constraint release evidence.` The ninth skip is
`real payroll ledger not on this machine`. The existing missing-staticfiles
warning remains. No migrations, environment changes, schedules or one-off data
operations are required. Evidence is local SQLite/source only; no network or
production access was performed.

PENDING — supervisor PostgreSQL full suite, `check` and
`makemigrations --check --dry-run` against this round-2 tree. The supplied
round-1 PostgreSQL result (739 tests OK, skipped=1, checks clean) is historical
and does not establish this gate.

PENDING — supervisor real-workbook preflight/scan and full-path PostgreSQL
re-benchmark of the operator's `20260901` file (12,132,538 bytes), default RSS
measurement without allocation tracing. The workbook is unavailable here.
D38 accepts the supervisor's prior 5.7s streaming scan; D37 sets the request
budget to the 300s gunicorn timeout. Those decisions supersede the earlier
round-1 scan <=2s / total <20s targets and older 60s request budget in this log;
no synthetic test is a new real-workbook timing or capacity result. Retain
release RSS, duplicate-heavy/maximum-envelope and concurrent-reader capacity
gates for supervisor verification.

Git: initial staging of the seven named tracked files succeeded. After the final
log update, both re-staging the log and the conventional commit attempt failed
creating `.git/index.lock` with `Operation not permitted`. No commit was created;
HEAD remains `b84f1d4`. All seven files remain intact and uncommitted: the code
and earlier log entry are staged, with the final log additions unstaged. No
Git-metadata workaround was attempted. The pre-existing untracked
`.review-detached.pid` remains untouched and excluded. Final working-tree and
staged `git diff --check` both passed.

### Review fixes, round 3

Scope: local standalone clone on `feat/wp2a-finance-runs`, starting at `75bffe1`.
Applied the supplied round-3 findings and D38 streaming-only constraint with plan
sections 3.5, 3.8 and 8.1. No network or production access; all Django commands
activate `venv/bin/activate` and set `DATABASE_URL=sqlite:///:memory:`. Fixtures
are generated in memory. No approval/demotion service, cutover view, migration,
legacy import or publisher changes.

RED, before parser implementation (`venv/review-r3-red.log`):

```sh
DATABASE_URL=sqlite:///:memory: python manage.py test api.tests_finance_upload_safety.WorkbookSelectionHTTPTests.test_trailing_slash_target_http_rejected_before_producer_or_openpyxl api.tests_finance_upload_safety.WorkbookSafetyTests.test_sheet_scan_never_reads_whole_member --noinput
```

**Ran 2 tests in 0.021s; FAILED (failures=2).** The trailing-slash fixture includes
both distinct entries with an oversized LCV1 header in the normalized target;
it reached the mocked producer and returned 500 instead of 400. The streaming
regression failed at the forbidden `ZipFile.read` of the worksheet. Its expanded
sheet exceeds 64 KiB; metadata reads remain allowed.

Changes:

- Resolve relative relationship targets with `posixpath.normpath` after joining
  the source directory, and strip exactly one leading slash for absolute targets,
  matching the installed openpyxl 3.1.5 `get_dependents` implementation. Require
  unchanged canonical resolution, reject trailing slashes, dot/traversal/doubled
  slash/backslash targets, and require exact ZIP membership before scanning.
  Canonical absolute/relative and exact mixed-case absolute names remain accepted;
  case-mismatched entry references reject. ZIP preflight also rejects distinct
  entry names that normalize to one path with `WORKBOOK_METADATA_INVALID`.
  The HTTP regression now asserts 400 with that code, no run and no producer or
  openpyxl invocation.
- Replace whole-sheet reads with a declaration pass in 64 KiB chunks and eight
  bytes of overlap after NUL removal. Reopen the member directly into the single
  defusedxml event scanner. No worksheet-sized byte buffer, second XML parser or
  regex XML slicing. Split DOCTYPE/ENTITY tests cover UTF-8, UTF-16 LE/BE and
  UTF-32 LE/BE and assert rejection before the XML parser.
- Add `FinanceUploadTests.test_later_fact_batch_failure_rolls_back_run_rows_and_allocations`:
  real SQLite inserts reach 2,000, 4,000 and 4,002 objects, then an exception after
  the third row batch or third allocation batch returns 500 and leaves no run,
  rows or allocations. Confirm the existing
  `test_upload_sampler_joined_on_success_replay_and_exception` passes for all
  three outcomes, including joined sampler threads. No service changes needed.

GREEN:

- `python manage.py test api.tests_finance_upload_safety api.tests_finance_runs_upload --noinput`
  — **Ran 58 tests in 6.258s; OK**, no skips. Log: `venv/review-r3-focused.log`.
- `python manage.py test --noinput`
  — **Ran 747 tests in 19.036s; OK (skipped=9)**, 738 passed, zero failures/errors.
  Log: `venv/review-r3-full-green.log`.
- `python manage.py check` — **System check identified no issues (0 silenced).**
- `python manage.py makemigrations --check --dry-run` — **No changes detected.**
- `git diff --check` — **passed** before this log update; final documentation-
  inclusive check is recorded below.

Seven concurrency tests skip with `Requires PostgreSQL advisory locks and separate
connections.` The unique-current constraint test skips with `Requires PostgreSQL
conditional unique constraint release evidence.` The ninth, existing skip is
`real payroll ledger not on this machine`. The existing missing-staticfiles warning
remains. No migrations, environment changes, schedules or one-off data operations
are required. These are local SQLite and source results only.

PENDING — supervisor PostgreSQL full-suite gate, system check and migration drift
check on the round-3 result; SQLite does not establish locking or release evidence.

PENDING — supervisor real `20260901` workbook scan RSS and PostgreSQL full-path
re-benchmark without allocation tracing. Target scan peak returns to approximately
104 MB (round-0 level), versus the supplied approximately 238 MB regression result.
No real workbook or RSS benchmark was run here. Retain D37's 300s request budget,
D38's streaming scan, and the release RSS/concurrency/reader-capacity gates.

Final documentation-inclusive `git diff --check`: **passed**. Staging the four
named files failed creating this clone's `.git/index.lock` with `Operation not
permitted`; no commit or workaround was attempted. All four changes remain intact
and uncommitted. The pre-existing untracked `.review-detached.pid` is untouched.

### Review fixes, round 4

Scope: supervisor-authorized local round 4 starting at `b8d78a7`, plan 3.8
and supplied D15/D29–D31/D38 constraints. Only the parser, upload error
classification, safety tests and this log change. Approval/demotion logic,
cutover, migrations, legacy import and publisher are untouched. No network,
production access or external writes; fixtures are generated in memory.

RED first: `source venv/bin/activate`, then
`DATABASE_URL=sqlite:///:memory: python manage.py test api.tests_finance_upload_safety --noinput`
— **Ran 41 tests in 6.458s; FAILED (failures=11), no errors**.
Log: `venv/review-r4-red.log`. An initial fixture iteration had one incorrect
central-directory filename slice; corrected before this recorded RED run.
Named new tests in `WorkbookSafetyTests`:

- `test_metadata_part_caps_before_parsing`
- `test_shared_strings_actual_expansion_cap_with_understated_directory`
- `test_metadata_actual_expansion_cap_with_understated_directory`
- `test_shared_string_four_million_count_cap`
- `test_shared_string_length_cap_including_rich_text`
- `test_shared_strings_declaration_before_parser`
- `test_normal_shared_strings_stream_and_resolve_headers` (passing control)

Also `WorkbookSelectionHTTPTests.test_part_and_string_limits_http_before_producer`.
The initial HTTP-only RED ran 1 test with 2 subtest failures in 0.026s.
The final RED includes it. Tests assert stable errors; HTTP tests require 400,
no FinanceRun, and no producer or openpyxl invocation.

Implementation: central-directory checks and independently counted zlib output
both enforce 1 MiB per `[Content_Types].xml`, `xl/workbook.xml` and every `.rels`
part, and 64 MiB for `xl/sharedStrings.xml`, with `PART_SIZE_LIMIT`. Metadata
reads use `archive.open` with cap-plus-one before `fromstring`. Metadata trees
remain, but their input is bounded to 1 MiB. Independent inflation drains buffered
zlib output even when the last compressed input was consumed, stopping at EOF;
the 64 MiB-plus-one lying-directory regression exposed this boundary. Each output
chunk remains at most 64 KiB. Existing CRC, total, ratio and general entry limits
remain enforced. The repetitive expansion fixtures lift only the ratio limit to
isolate actual expansion; valid-comment metadata fixtures use random hex padding
to stay within the normal ratio limit. Shared-string whole-part reads are forbidden
by a `ZipFile.read` mock; this is structural bounded-read evidence, not RSS proof.

Shared strings retain their existing `archive.open` / defusedxml iterparse path,
now preceded by the same chunked, encoding-aware declaration guard as worksheets.
Count at most 4,000,000 `si` entries and at most 32,767 characters across each
string's text/rich-text runs; both reject with `SHARED_STRING_LIMIT`. Only an
index-aligned list of recognized header labels or boolean nonblank markers is
retained, never a list of full string contents. Each completed string is cleared.
The normal shared-string fixture resolves ledger headers and verifies identical
labels/markers. The upload error branch now treats the two new codes as 400
rejections instead of creating failed runs; no approval/demotion changes.

Cap rationale: 1 MiB generously bounds package declarations, sheet metadata and
relationship maps under the existing 256-entry envelope, independent of cell
volume. The supplied real-workbook reference has approximately 47,000 shared
strings: 64 MiB allows roughly 1.4 KiB of XML per reference string on average,
while bounding the part that openpyxl subsequently materializes. This is headroom
rationale, not a measured part size or RSS guarantee. The 4,000,000-string cap
matches the cell envelope (roughly 85 times the reference count); the independent
64 MiB cap also applies, so these maxima need not be jointly attainable.
32,767 characters is Excel's cell text limit. No real workbook was available or
measured here, and no acceptance bound was relaxed.

GREEN commands all activate this clone's venv and set
`DATABASE_URL=sqlite:///:memory:`. Final results recorded below.

PENDING — supervisor PostgreSQL full suite, `check`, and
`makemigrations --check --dry-run` on this round-4 tree. Seven concurrency tests
skip with `Requires PostgreSQL advisory locks and separate connections.` The
unique-current test skips with `Requires PostgreSQL conditional unique constraint
release evidence.` The ninth skip is `real payroll ledger not on this machine`.

PENDING — supervisor real-workbook scan/RSS and successful PostgreSQL full-path
re-benchmark, including maximum-envelope/string-heavy, duplicate-heavy and
concurrent-reader capacity gates. Retain D38 streaming and the previously recorded
D37 300s request budget. SQLite is not PostgreSQL, release, or production proof.
No migrations, environment changes, schedules or one-off operations are required.

Final GREEN:

- `python manage.py test api.tests_finance_upload_safety --noinput` — **41 tests
  in 6.450s; OK**, no skips (`venv/review-r4-focused.log`).
- `python manage.py test --noinput` — **755 tests in 27.221s; OK (skipped=9)**,
  746 passed, no failures/errors (`venv/review-r4-full-green.log`).
- `python manage.py check` — **System check identified no issues (0 silenced).**
- `python manage.py makemigrations --check --dry-run` — **No changes detected.**
- `git diff --check` — **passed**, including this documentation update.

The existing missing-staticfiles warning remains. All evidence is local.

Git: staging the four named files failed creating `.git/index.lock` with
`Operation not permitted`. No commit was created or workaround attempted; all
four changes remain intact and uncommitted. The pre-existing untracked
`.review-detached.pid` is untouched. Final documentation-inclusive
`git diff --check` passed.

### Review fixes, round 5

Scope: local standalone clone at `51bd114`, plan 3.8 and supplied
D15/D29–D31/D38 constraints. No network or production access.

RED first, before parser changes: activate `venv/bin/activate`, then
`DATABASE_URL=sqlite:///:memory: python manage.py test api.tests_finance_upload_safety.SharedStringComplexityTests api.tests_finance_upload_safety.SharedStringComplexityHTTPTests --noinput`.
**Ran 8 tests in 1.279s; FAILED (failures=7, errors=1)**.
Recorded output: `venv/review-r5-red.log`. Named regressions:

- `test_millions_empty_runs_rejected_early_under_200_mib`
- `test_1024_empty_runs_accepted_1025_rejected`
- `test_all_descendants_count_together`
- `test_text_length_rejected_at_offending_t_end`
- `test_part_node_budget_includes_root_and_every_element`
- `test_completed_elements_cleared_and_detached`
- `test_plain_strings_and_accepted_string_heavy_openpyxl_under_512_mib`
  (passing control)
- `test_node_limit_http_400_no_run_producer_or_openpyxl`

The malicious fixture contains all 2,200,000 runs in a ZIP_STORED workbook,
constructed incrementally in BytesIO with hand-written metadata and headers.
The RED event wrapper aborts at event 2,061 to avoid reproducing a 585 MiB
allocation. HTTP RED reaches the mocked producer and errors, proving the absent
early rejection. RSS tests run in fresh venv Python subprocesses so earlier tests'
process-wide high-water marks cannot contaminate their measurements; no disk
fixture, temporary file or network is used.

Implementation: each `si` admits at most 1,024 descendant elements, counted on
start events regardless of tag (including `r`, `t`, `rPh`, `phoneticPr`, `rPr`
and formatting descendants). The 1,025th child rejects immediately. Text length
is accumulated at each `t` end event, when ElementTree makes its complete text
available, and the offending `t` rejects above 32,767 characters. Entry count is
checked at `si` start. All three use `SHARED_STRING_LIMIT`; existing HTTP mapping
returns 400 without a run or producer/openpyxl invocation. Nested `si` is invalid.

The supplied review's Excel rich-text-run practical limit is far below 1,024,
and the supplied real-workbook shared strings are plain; this generous complexity
allowance protects openpyxl's later per-entry materialization as well as the
scanner. This is supplied context, not a fresh workbook or Excel-spec inspection.
Clarification of conflicting deliverable wording: 1,024 `<r><t/></r>` runs contain
2,048 child elements and cannot pass a 1,024-child cap. Tests therefore accept
1,024 empty `<r/>` runs and reject 1,025, and separately accept 512 `<r><t/></r>`
runs (exactly 1,024 children) and reject any additional descendant. The explicit
all-child-elements cap takes precedence; no cap is relaxed.

The part budget is `2 * MAX_SHARED_STRINGS = 8,000,000` elements, including the
root and all entries/descendants. Two nodes per plain `si/t` entry ties total XML
complexity to the 4,000,000-cell/entry envelope; rich formatting consumes that
same budget, rather than multiplying four million entries by 1,024. Because the
root also counts, four million plain `si/t` entries are not jointly admissible.
The existing entry count and 64 MiB expanded-part limits remain independent.
A reduced-budget exact-boundary test also asserts the production constant.

The shared iterparse loop now clears every completed element and removes it from
its parent after the consumer handles its end event. Both string and worksheet
scanners consume leaf values before removal; they no longer retain XML subtrees
until the enclosing entry, cell, row or part closes. Shared-string text retained
per entry is bounded by the text cap; only labels/boolean markers survive across
entries. ElementTree also has bounded input-chunk read-ahead. The worksheet
scanner retains cell values and row/header summaries instead of XML trees.

Focused GREEN: `DATABASE_URL=sqlite:///:memory: python manage.py test api.tests_finance_upload_safety --noinput`
— **49 tests in 14.769s; OK, no skips** (`venv/review-r5-focused.log`).
The 2,200,000-run rejected scan consumed **2,051 iterparse events** and peaked at
**116,113,408 bytes (110.734375 MiB)**, below the unchanged 200 MiB rejection gate.
The accepted synthetic fixture (1,000 plain 24,000-character strings and 100
strings with 512 `r/t` runs each) passed ZIP preflight, scan and real openpyxl
read-only loading/content assertions at **146,210,816 bytes (139.4375 MiB)**,
below the unchanged 512 MiB gate. These isolated-process RSS values include
fixture creation, imports, preflight and scan (plus openpyxl for the accepted
case); they are not scoped Python-allocation peaks or successful producer/facts
full-path release evidence. Real-workbook paths and producer package are unchanged.

Final GREEN (venv activated, `DATABASE_URL=sqlite:///:memory:`):

- `python manage.py test --noinput` — **763 tests in 43.384s; OK (skipped=9)**,
  **754 passed**, zero failures/errors (`venv/review-r5-full-green.log`).
  Fresh subprocess measurements in this full run: rejected peak **119,652,352
  bytes (114.109375 MiB)** at **2,051 events**; accepted peak **145,162,240 bytes
  (138.4375 MiB)**. Both unchanged memory gates pass.
- `python manage.py check` — **System check identified no issues (0 silenced).**
- `python manage.py makemigrations --check --dry-run` — **No changes detected.**
- `git diff --check` — **passed**, including the documentation update.

PENDING — supervisor PostgreSQL full-suite/check/migration-drift gate. Seven
concurrency tests skip with `Requires PostgreSQL advisory locks and separate
connections.` The unique-current test skips with `Requires PostgreSQL conditional
unique constraint release evidence.` The ninth skip remains `real payroll ledger
not on this machine`. Existing missing-staticfiles warnings remain.

PENDING — supervisor real-workbook re-benchmark and successful PostgreSQL
producer/facts full-path measurements, including maximum-envelope/string-heavy,
duplicate-heavy and concurrent-reader capacity cases against the unchanged
512 MiB worker gate. The accepted synthetic openpyxl measurement above covers
only its stated fixture/path. No deployment, production or real-workbook proof
is claimed. No migrations, environment changes, schedules or one-off operations
are required by this change. Only the parser, safety tests and this log change;
the pre-existing `.review-detached.pid` is untouched.

Git: staging the three named files was denied creating `.git/index.lock` with
`Operation not permitted`. No commit or workaround was attempted; the three
changed files remain intact and uncommitted. Final documentation-inclusive
`git diff --check` passed.

### Review fixes, round 6

Scope: standalone clone at `73cea44`, plan section 3.8 and supplied
D15/D29–D31/D38 constraints; structural upload validation only.

RED first, before parser changes (venv activated):
`DATABASE_URL=sqlite:///:memory: python manage.py test api.tests_finance_upload_safety.Round6StructureTests api.tests_finance_upload_safety.Round6StructureHTTPTests --noinput`
— **Ran 9 tests in 0.492s; FAILED (failures=11)**, no errors. Subtests account
for the failure total. Log: `venv/review-r6-red.log`. Named regressions:

- `test_exact_out_of_entry_fixture_rejected_at_second_event_under_200_mib`
- `test_shared_string_root_must_be_canonical_sst`
- `test_nested_wrapper_outside_entries_rejected_before_descending`
- `test_stray_element_between_valid_entries_rejected_on_start`
- `test_plain_shared_string_part_and_real_openpyxl_path_unchanged` (passing control)
- `test_worksheet_root_must_be_canonical_before_descending`
- `test_worksheet_part_budget_counts_unmodeled_elements_on_start`
- `test_worksheet_retained_metadata_and_row_subtrees_bounded_on_start`
- `test_exact_out_of_entry_fixture_never_calls_producer_or_openpyxl`

The exact ZIP_STORED fixture is 24,202,796 bytes, with 2,200,000 `<r><t/></r>`
runs directly under `sst` and valid required-sheet headers. Both scanner and HTTP
regressions abort RED safely if a third event is requested; they never send this
unsafe fixture to real openpyxl. Fixtures and isolated RSS probes use memory only.

Implementation and local source evidence:

- Shared-string start events require the canonical SpreadsheetML `sst` root and
  direct-child `si` entries. An unexpected element outside an entry rejects on
  its own start event, before requesting any descendant event. Reuse the stable,
  value-free `SHARED_STRING_LIMIT` code and existing HTTP 400/no-run mapping.
  No non-entry extension elements are supported: openpyxl 3.1.5
  `reader/strings.py:10` (`read_string_table`) clears only `si`, retaining other
  subtrees until the complete part is parsed. Existing entry/descendant/text/part
  caps and completed-element removal remain in force.
- Worksheet start events require the canonical SpreadsheetML `worksheet` root.
  Correction to the request's premise: this revision had an 8,000,000-element
  shared-string part budget, but no worksheet element counter. Add the same
  numeric ceiling per scanned worksheet, counting every element regardless of
  whether the scanner models it. Worksheet structural/budget failures reuse
  `XML_INVALID`, preserving value-free HTTP 400 behavior without service edits.
- Installed openpyxl 3.1.5 `worksheet/_reader.py:125` (`WorkSheetParser.parse`)
  clears rows and dispatched metadata at their end events, but does not detach
  their empty shells. Unrecognized nodes remain attached; recognized metadata
  is built from complete subtrees and stored on the parser. Thus the large part
  budget alone is insufficient. Add a cumulative 65,536-node retained-structure
  cap for all non-row elements plus row shells, and independently the same cap
  for each row's complete subtree. All counts check start events, include unknown
  descendants, and cannot reset through an unknown wrapper. This leaves room for
  the 50,000-row envelope plus metadata while bounding retained node structure
  separately from eight million streamed nodes. These are conservative node
  bounds, not proof that every accepted workbook fits the worker RSS budget;
  existing expanded-byte bounds still apply and release benchmarking stays open.
  `WorkSheetParser.parse_dimensions` at line 172 clears elements until dimension
  or sheetData; the full row iterator above has the relevant retention behavior.
- Added `test_worksheet_retained_budget_includes_cleared_row_shells` after the
  source inspection to cover repeated cleared rows. The first implementation run
  exposed a test-fixture issue: the reduced sheet1 node ceiling also applied to
  larger sheet2. Narrowed that exact-boundary check to its intended sheet; no
  production cap was relaxed. Plain shared strings and actual openpyxl loading
  retain their expected values; the generated real-producer tests remain in the
  full suite. No real financial workbook was inspected or re-benchmarked here.

Focused GREEN (venv activated, `DATABASE_URL=sqlite:///:memory:`):
`python manage.py test api.tests_finance_upload_safety --noinput`
— **59 tests in 16.365s; OK**, no skips (`venv/review-r6-focused.log`).
Exact rejected out-of-entry scan: **118,063,104 bytes (112.59375 MiB)** absolute
process peak RSS, **2 events**, **24,202,796 upload bytes**. The fresh subprocess
includes imports, in-memory fixture construction, preflight and scan; no disk
fixture or temporary file is created. HTTP independently proves no producer or
openpyxl call and no FinanceRun creation. The prior inside-entry rejection and
accepted string-heavy openpyxl regressions also remain GREEN.

Final GREEN (venv activated, `DATABASE_URL=sqlite:///:memory:`):

- `python manage.py test --noinput` — **773 tests in 45.234s; OK (skipped=9)**,
  **764 passed**, zero failures/errors (`venv/review-r6-full-green.log`).
  Exact out-of-entry rejected scan: **117,915,648 bytes (112.453125 MiB)**,
  **2 events**, **24,202,796 bytes**; below the 200 MiB rejection gate.
  Prior inside-entry rejected peak: **118,046,720 bytes**, 2,051 events;
  accepted string-heavy openpyxl peak: **147,210,240 bytes**.
- `python manage.py check` — **System check identified no issues (0 silenced).**
- `python manage.py makemigrations --check --dry-run` — **No changes detected.**
- `git diff --check` — **passed**, including this documentation update.

PENDING — supervisor PostgreSQL full-suite/check/migration-drift gate. Seven
concurrency tests skip with `Requires PostgreSQL advisory locks and separate
connections.` One unique-current test skips with `Requires PostgreSQL conditional
unique constraint release evidence.` The ninth skip is `real payroll ledger
not on this machine`. The existing missing-staticfiles warning remains.

PENDING — supervisor real-workbook scan/RSS re-benchmark and successful
PostgreSQL producer/facts full-path release measurements, including maximum
cell/string envelopes, duplicate-heavy paths and concurrent-reader capacity.
Verify the new worksheet retained-structure bounds on the largest valid real
workbook; do not relax them without repeated memory evidence. Local synthetic
SQLite/openpyxl results are not PostgreSQL, release, deployment or production
proof. No migrations, environment changes, schedules or one-off operations are
required. No network, production access, or writes outside this clone occurred.
Only parser, safety tests and this log change; approval/demotion, cutover,
migration, legacy import and publisher remain unchanged. The pre-existing
untracked `.review-detached.pid` is untouched.

Git: staging the three named files was denied creating `.git/index.lock` with
`Operation not permitted`. No commit or workaround was attempted; the tree is
intact and uncommitted. Final documentation-inclusive `git diff --check` passed.

## 2026-09-07 WP4 slice A backend stage

Authority: approved revision 2 `/tmp/wp4-plan-for-backend.md`, extending released
WP2a at `b6dcfc1` in this standalone `feat/wp4a-budgets-backend` clone.
Supervisor D15, D17.1, D21, D29–D31, D33, D36–D38 remain binding. No network or
production access. This stage uses the supervisor-installed publisher from
masi-finance main `480dc00`; its distribution metadata remains `0.2.0` while its
installed contract verifier includes budgets. `requirements.txt` and `build.sh`
remain unchanged: the deployment pin moves at the next unique publisher release,
when the budgets upload pin and cumulative supported-pair registry must be updated.
This installed-development-build evidence is not a tagged publisher release.

### RED before implementation

`DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py test api.tests_finance_budgets api.tests_finance_budget_safety api.tests_finance_budget_current --noinput --verbosity=2`
— **Ran 21 tests in 0.677s; FAILED (failures=8, errors=9, skipped=2)**.
Log: gitignored `venv/wp4-evidence/red.log`. Failures are unsupported upload
metadata (400); errors are unsupported `ledger_run_id`/scanner kind arguments.
Two existing-behavior controls passed. The PostgreSQL tests skip by engine with
`Requires PostgreSQL advisory locks, row locks and separate connections; SQLite is functional evidence only.`

Exact named RED suite (all names from approved 7-A items 6–8):

- `api.tests_finance_budgets.BudgetTests.test_budget_raw_upload_reuses_candidate_transaction`
- `api.tests_finance_budgets.BudgetTests.test_same_bytes_new_dependency_is_new_candidate`
- `api.tests_finance_budgets.BudgetTests.test_replay_preserves_uploader_and_status`
- `api.tests_finance_budgets.BudgetTests.test_dependency_factless_missing_corrupt_candidate_refuses`
- `api.tests_finance_budgets.BudgetTests.test_dependency_fk_and_manifest_must_agree`
- `api.tests_finance_budgets.BudgetTests.test_budget_approval_revalidates_derived_and_dependency`
- `api.tests_finance_budgets.BudgetTests.test_funders_retained_candidate_still_approves_after_pin_update`
- `api.tests_finance_budgets.BudgetTests.test_demote_replay_reapprove_preserves_acyclic_recovery`
- `api.tests_finance_budgets.BudgetTests.test_all_mutations_require_publish_and_actors_are_server_derived`
- `api.tests_finance_budget_safety.BudgetSafetyTests.test_31_sheet_unsized_export_reaches_producer`
- `api.tests_finance_budget_safety.BudgetSafetyTests.test_stream_cap_and_unsafe_zip_create_no_history`
- `api.tests_finance_budget_safety.BudgetSafetyTests.test_dimension_spoof_duplicate_nodes_and_shared_strings_reject_early`
- `api.tests_finance_budget_safety.BudgetSafetyTests.test_external_link_and_missing_referenced_sheet_refuse`
- `api.tests_finance_budget_safety.BudgetSafetyTests.test_empty_ancillary_is_not_empty_required_sheet`
- `api.tests_finance_budget_safety.BudgetSafetyTests.test_parser_diagnostics_never_leak_auxiliary_values`
- `api.tests_finance_budget_current.BudgetCurrentTests.test_same_management_sha_is_compatible_across_kinds`
- `api.tests_finance_budget_current.BudgetCurrentTests.test_missing_kind_tolerated_but_unresolved_dependency_is_not`
- `api.tests_finance_budget_current.BudgetCurrentTests.test_new_funder_current_marks_old_budget_incompatible_without_recompute`
- `api.tests_finance_budget_current.BudgetCurrentTests.test_budget_approval_does_not_change_funder_snapshot_or_years`
- `api.tests_finance_budget_current.BudgetPostgresTests.test_postgres_racing_approval_upload_and_injected_failure_preserve_current`
- `api.tests_finance_budget_current.BudgetPostgresTests.test_postgres_dependency_admission_uses_consistent_lock_order`

### Implementation and interpretation

- Migration `0052_finance_budget_runs` adds the protected dependency FK and budgets
  shape, preserving every funder row and immutable JSON. The existing unconditional
  `finance_upload_identity` necessarily becomes conditional on `kind=funders`:
  same name, same four columns and exactly the same funder uniqueness behavior.
  Leaving it unconditional would prohibit the expressly required budget replay
  against a new dependency. Budgets have a separate five-column partial unique key.
- Same-year/kind dependency validation is a model/service invariant; cross-row
  equality cannot be expressed in a portable SQL CHECK. The FK protects retention;
  SQL checks require dependency on candidate/approved/superseded/failed budgets,
  prohibit it for funders and prohibit budget fact counts/digests.
- Shared service owns upload transaction, replay, measured RSS, history insertion
  and all approval/demotion behavior. Sorted `(budgets, year)` then `(funders, year)`
  advisory locks precede row locks in both upload and transitions. Dependencies may
  be retained superseded, but must have validated 2.0.0 committed ledger facts.
- Budgets approval invokes packaged calculation replay and its own serving schema;
  it never invokes the funder 1.1.0 projection. Retained precise inputs, all digest
  bindings and signed residual membership are checked before current changes.
- The shared streaming scanner adds a budget profile; all released ZIP, expansion,
  shared-string/declaration and retained-node limits stay in force. No XML slicing.
- WP2b rows endpoints are absent at this base. Bring forward only bounded BC/Year
  reads and CSV/XLSX export at the planned run-scoped paths, with the pinned ledger,
  finite stored-BC variant resolution through `excel_equal`, and per-request access
  checks. No generic metrics/diff/filter-token API is added.

### Additional acceptance checks and diagnostic RED

- Extended the named functional tests with safe failed-run retention/replay,
  protected FK and SQL checks, error acknowledgement/note, all three anti-rollback
  cases, actual contributor exports/access revocation, budget-only current and two
  different ledger UUIDs sharing the same Management Accounts SHA.
- `BudgetMigrationTests.test_upgrade_preserves_every_funder_field_and_constraint`
  executes 0051 → 0052 on SQLite with both a successful 2.0.0 funder and imported
  1.0.0 run. Every old field compares equal; dependency is null; funder illegal
  state/payload/audit and duplicate-upload writes still refuse. No data migration.
- `BudgetTests.test_odd_cent_half_shares_replay_without_assigning_residuals_to_inputs`
  builds an actual synthetic funder workbook with 0.01 ledger Amount, two explicit
  budget halves and fractional-cent budget assertions. Each displayed actual is
  0.01 with group residual -0.01; month-3 projection is 0.02 each. Approval replays
  with openpyxl forbidden. Residuals never become calculation inputs.
- Additional diagnostic RED:
  `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py test api.tests_finance_budget_safety.BudgetSafetyTests.test_scanner_unknown_decode_and_warning_channels_are_value_free --noinput`
  — **Ran 1 test in 0.010s; FAILED (failures=1)**, exposing synthetic stdout,
  stderr and warning text (`venv/wp4-evidence/diagnostic-red.log`). The budgets-only
  scanner boundary now discards/restores stdout/stderr, captures category/count
  diagnostics, converts unknown scanner exceptions to WORKBOOK_DECODE_FAILURE and
  appends only PARSER_WARNING info to successful derived findings.
- Producer diagnostic regression separately exposed jsonschema's multi-argument
  exception representation: safe RUN_SCHEMA_INVALID is matched against its fixed
  `message`, not a one-element `args` tuple. Unknown decoder errors remain
  WORKBOOK_DECODE_FAILURE; unexpected service/database failures remain HTTP 500
  and cannot create a plausible failed run. The released funder boundary is intact.
- 31-sheet unsized fixture now actually reaches the installed producer and returns
  a candidate. Unsafe stream/ZIP/shared-string tests prove no producer/openpyxl
  invocation or budget history. Additional sparse-sheet aggregate/65-sheet/header
  tests enforce the bounded profile before producer work. Synthetic workbooks are
  built entirely in memory with fixed metadata/ZIP timestamps for stable replay.
- CSV/XLSX use the same authorized BC/Year queryset and WP2's stable
  `(date, sheet_row, row_key)` order. Pages are 100 rows; exports cap at 50,000.
  `format` is the download format, not DRF renderer selection (the first export
  test exposed a 404, corrected locally). XLSX is an in-memory new workbook;
  source uploads are never retained or reconstructed.

### Section 8 evidence rows

| Evidence | Backend-stage result / supervisor gate |
|---|---|
| Local source / workbook acceptance | Synthetic full raw upload → detail → approval → current → contributors/export → demote/reapprove executed locally; real input PENDING. |
| Adversarial plan review | Revision 2 APPROVED per supplied approval; no new independent implementation review claimed. |
| Slice A RED / focused GREEN | Initial 21-test RED above; final focused suite recorded below. Slice B PENDING. |
| Full suites / PostgreSQL / skips / warnings | SQLite results below; PostgreSQL and other repositories PENDING. Existing missing-staticfiles warning and private payroll skip remain. |
| Publisher commit / unique tag | Supervisor-supplied main 480dc00 installed, metadata 0.2.0; unique tag/release pin PENDING. |
| Budget schema SHA-256 | `4e35186a43eaf30cacb9ffc305db8c7f1be954905b9d87ee12afbfae417889b8`; backend copy exactly equals installed resource. |
| Synthetic golden SHA-256 / equality | `86c6ada0f86a592d3228544cfe5917d3183a61910e5c97769735d6a49f7c0497`; backend copy exactly equals installed golden; frontend equality PENDING. |
| Wheel/sdist / isolated installed checks | Four installed resources verified, digest mismatch still fails closed. Separate wheel/sdist build hashes and isolated installs PENDING with publisher release. |
| Backend commit / migration / Render | Migration 0052 executes on SQLite; commit result below; PostgreSQL migration and Render deployment PENDING. |
| Frontend / Vercel targets | PENDING supervisor/frontend stage. |
| Real original-export rejection | PENDING coordinate-only diagnosis, timing and sampled RSS; no real workbook was supplied or accessed. |
| Corrected-export upload / approval | PENDING operator-corrected export and exact named ledger, UUIDs/digests/counts and private actor audit. |
| Parser / full-path benchmark | Command supports `--kind budgets --ledger-run-id UUID`, shared RSS measurement and actual file path; real successful/rejection runs, PostgreSQL, worker/aggregate memory, timeout margin and reader latency PENDING. |
| Cross-kind current / retained run | SQLite same/mismatch/absent-kind, unchanged snapshot/years and retained funder approval verified; production PENDING. |
| Transaction / recovery | SQLite rollback and acyclic recovery verified; named PostgreSQL races and lock order PENDING. |
| Arithmetic reconciliation | Packaged retained-input replay, odd-cent shares, tamper/rehash rejection and synthetic contributor parity verified; real BC/share/orphan/Year reconciliation PENDING. |
| Minimal UI / exports | Backend CSV/XLSX parity verified; browser/screenshots/keyboard and frontend rendering PENDING. |
| Sheets acquisition / secrets | PENDING slice B; no credentials, Google integration or schedule added. |
| Production reader probes | PENDING ADMIN, read-only Finance Manager, PROJECT MANAGER and plain STAFF live probes. No production access. |

Required supervisor command shape (writes a candidate/failed run to its explicitly
configured test/release database):
`venv/bin/python manage.py benchmark_finance_upload '<dated-export-path>' --actor-user-id <authorized-id> --year 2026 --kind budgets --ledger-run-id <exact-ledger-uuid>`.
No real-export byte count, SHA, latency, RSS, actor or run identity is invented here.
No new environment variables, schedules, credentials or automatic operations.

Full-suite integration exposed two test-isolation issues before final GREEN:
`venv/wp4-evidence/full-final.log` — 806 tests in 48.886s, one failure and one
error, 11 skips. Replay rebuilt a ZIP across a wall-clock second and got new bytes;
the synthetic builder now canonicalizes core/ZIP timestamps. The new migration
TransactionTestCase flushed migration-seeded Finance Managers grants before the
released fresh-install test inspected them. The migration probe now runs in a
separate explicitly in-memory SQLite subprocess, leaving the shared test database
and released tests unchanged. It remains SQLite migration evidence only.

### Final GREEN and gate inventory

- Focused: `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py test api.tests_finance_budgets api.tests_finance_budget_safety api.tests_finance_budget_current --noinput`
  — **Ran 33 tests in 4.398s; OK (skipped=2)**, 31 passed. Log:
  `venv/wp4-evidence/focused-final.log`, SHA-256
  `9405c1e5f50ef0f292f80e6d371965fb1aea546fa3f580acfd5eeb32121e69be`.
  The subsequent fixture-isolation corrections were verified in the final full run.
- Isolation regression: named budget migration + recovery + released capability
  migration tests — **4 tests in 5.021s; OK**, no skips
  (`venv/wp4-evidence/isolation-green.log`).
- Full exact code/test tree:
  `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py test api --noinput --verbosity=2`
  — **Ran 806 tests in 51.727s; OK (skipped=11)**: **795 passed**, zero failures/errors.
  Log: `venv/wp4-evidence/full-green.log`, SHA-256
  `d9e3f1235cc6c18db3527216b6fc9a04f797d28eca4fd90b05f301efacfeb3b7`.
- `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py check`:
  **System check identified no issues (0 silenced).**
- `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py makemigrations --check --dry-run`:
  **No changes detected.** Exactly one new migration: `0052_finance_budget_runs`.
- `git diff --check`: **passed**. Protected `requirements.txt`, `build.sh`,
  `api/finance_snapshot_compat.py` and `api/views/finance.py` have no diff.
- The installed verifier regression now asserts all four named resources and
  still proves `CONTRACT_RESOURCE_DIGEST_MISMATCH` before migrations.
- Initial named RED log SHA-256:
  `6ca94df6670edf1d7cd1b5f2ceb7bf3e9b9d87f6c824a46f17cfaade2dbaf4ad`.
- Existing WhiteNoise missing-staticfiles warning remains; no new unexplained
  warning or xfail. Existing hostile funder safety probes also remain GREEN:
  out-of-entry rejected RSS 119,586,816 bytes / 2 events; inside-entry rejected
  RSS 117,637,120 bytes / 2,051 events; accepted string-heavy RSS 145,555,456 bytes.
  These are synthetic process measurements, not real budget capacity evidence.

PENDING PostgreSQL tests — must execute without SQLite skips at supervisor gate:

1. `api.tests_finance_budget_current.BudgetPostgresTests.test_postgres_racing_approval_upload_and_injected_failure_preserve_current`
2. `api.tests_finance_budget_current.BudgetPostgresTests.test_postgres_dependency_admission_uses_consistent_lock_order`
3. `api.tests_finance_runs_model.FinanceRunModelTests.test_partial_unique_current`
4. `api.tests_finance_runs_concurrency.FinanceConcurrencyTests.test_two_concurrent_approvals_one_wins_one_refuses`
5. `api.tests_finance_runs_concurrency.FinanceConcurrencyTests.test_different_tuples_do_not_share_lock`
6. `api.tests_finance_runs_concurrency.FinanceConcurrencyTests.test_import_uses_same_lock_and_replays_after_release`
7. `api.tests_finance_runs_concurrency.FinanceConcurrencyTests.test_transition_select_for_update_locks_existing_rows`
8. `api.tests_finance_runs_concurrency.FinanceConcurrencyTests.test_concurrent_imports_serialize_before_first_insert`
9. `api.tests_finance_runs_concurrency.FinanceConcurrencyTests.test_first_ever_same_tuple_uploads_one_completes_one_conflicts`
10. `api.tests_finance_runs_concurrency.FinanceConcurrencyTests.test_different_tuple_uploads_complete_while_first_is_locked`

The other skip is unchanged:
`api.tests_youth_budget.RealLedgerSeedTests.test_real_csv_parses_june_total_and_trimmed_april`
— `real payroll ledger not on this machine`.
PostgreSQL 0052 migration/constraint preservation, real original-export rejection,
corrected-export acceptance/RSS/capacity, new publisher release/pin, deployment and
production role probes remain **PENDING**. This stage is local backend evidence only.

Git result: **uncommitted**. Staging the 17 explicitly named deliverable files was
refused at this clone's `.git/index.lock` with `Operation not permitted`.
No metadata workaround, alternate checkout, network, push or commit was attempted.
All files remain intact; documentation-inclusive `git diff --check` passed.

## WP4 backend stage, review fixes round 1

RED first on bd27991, SQLite in memory, installed publisher supplied at 480dc00.
Command: `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py test api.tests_finance_sheet_order --noinput`.
Result: **Ran 5 tests in 0.462s; FAILED (failures=4)** (two passing controls;
two row-order failures and two cell-order subtest failures). Log: `venv/wp4-order-red.log`.
Names in `api.tests_finance_sheet_order.SheetOrderUploadTests`:
- `test_budget_populated_row_8_after_row_9_refuses_before_producer`
- `test_budget_ordered_row_8_reaches_hierarchy_failure`
- `test_funders_populated_expenditure_row_after_higher_row_refuses_before_producer`
- `test_funders_ordered_expenditure_reaches_candidate_with_ledger_row`
- `test_decreasing_cells_refuse_before_producer_for_both_kinds`

Both reversed-row uploads incorrectly returned 201 candidates; the funders
candidate lost its ledger row. Ordered budget F8=999 reached the expected
BUDGET_HIERARCHY_INVALID failed run; ordered funders retained one ledger row.
Both cell-order subtests incorrectly returned 201.
Use existing stable unsafe-structure code `XML_INVALID` for order violations
(the initial RED expected proposed SHEET_ROW_ORDER/SHEET_CELL_ORDER codes; all
failures occurred at the preceding HTTP status assertion). This preserves the
released shared service's no-history boundary without changing funders services.

Implementation: the shared streaming scanner requires strictly increasing row
coordinates per scanned part and strictly increasing cell columns within their
containing row, at start events. Both kinds reject violations as `XML_INVALID`
before producer execution or FinanceRun insertion. All released limits remain
unchanged; no regex slicing, service edits, models or migrations were added.
New regressions use raw authenticated HTTP uploads, real installed producers as
spies, and exact before/after FinanceRun identity sets on refusals.

Focused GREEN: **Ran 5 tests in 0.373s; OK**, zero skips
(`venv/wp4-order-green.log`). First full run: **Ran 811 tests in 52.114s;
FAILED (failures=4, skipped=11)** (`venv/wp4-order-full.log`). Four existing
header/bounds tests generated duplicate rows and now hit the earlier structural
guard. Their fixtures now append cells to the existing row or use increasing
rows, retaining the original expected limit codes. The retained-row-shell cap
fixture also uses increasing coordinates so it still exercises its node limit.

PENDING supervisor PostgreSQL gate: all ten tests listed in the preceding stage
(two budget lock/race tests, seven released concurrency tests, partial unique
constraint test), PostgreSQL migration/constraint validation. Named SQLite skip
reasons remain `Requires PostgreSQL advisory locks, row locks and separate
connections; SQLite is functional evidence only.`, `Requires PostgreSQL advisory
locks and separate connections.`, and `Requires PostgreSQL conditional unique
constraint release evidence.` The eleventh skip remains `real payroll ledger not
on this machine`. Real-export rejection/acceptance and capacity benchmarking for
both kinds remain PENDING under D38; no real workbook, network or production
operation was performed. Deployment and live verification remain PENDING.
No environment variables, schedules or one-off migrations are required by this fix.

Final GREEN: `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py test api --noinput`
— **Ran 811 tests in 52.216s; OK (skipped=11)**: **800 passed**, zero failures/errors.
Log: `venv/wp4-order-full-green.log`. Existing missing-staticfiles warning remains.
`DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py check` — **System check
identified no issues (0 silenced).**
`DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py makemigrations --check --dry-run`
— **No changes detected.** `git diff --check` — **passed**.
Evidence is local synthetic SQLite only; PostgreSQL and live gates remain above.

Git result: **uncommitted**. Staging the four deliverable files was refused at
this clone's `.git/index.lock`: `Operation not permitted`. Tree left intact;
pre-existing `.review-detached.pid` untouched. No metadata workaround attempted.

## WP4 backend stage, review fixes round 2

Scope: shared sheet scanner only, starting on `feat/wp4a-budgets-backend` at
`aa3bc5a`, with the supervisor-supplied publisher from main `480dc00` installed.
Read plan section 5.2 and decisions D29-D31/D38. No funders service changes,
new models, migrations, environment variables, schedules or one-off operations.

RED first, before scanner changes:
`DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py test api.tests_finance_sheet_order --noinput`
— **Ran 9 tests in 3.285s; FAILED (failures=76)**, zero skips.
Log: `venv/wp4-structure-red.log`. This is 75 structural subtest failures plus
one canonical-control fixture assertion: the first funders data cell is a date,
not an inline string. The fixture now locates its existing inline-string cell.
The other ten structural cases already refused. The new named tests, all under
`api.tests_finance_sheet_order.SheetOrderUploadTests`, are:
- `test_budget_noncanonical_structure_refuses_before_producer`
- `test_funders_noncanonical_structure_refuses_before_producer`
- `test_budget_canonical_inline_string_and_empty_styled_cell`
- `test_funders_canonical_inline_string_and_empty_styled_cell`
Retained tests run in the same RED/GREEN command:
- `test_budget_populated_row_8_after_row_9_refuses_before_producer`
- `test_budget_ordered_row_8_reaches_hierarchy_failure`
- `test_funders_populated_expenditure_row_after_higher_row_refuses_before_producer`
- `test_funders_ordered_expenditure_reaches_candidate_with_ledger_row`
- `test_decreasing_cells_refuse_before_producer_for_both_kinds`

Consumer checked from the installed openpyxl **3.1.5** source, not assumed:
`venv/lib/python3.13/site-packages/openpyxl/worksheet/_reader.py`,
`WorkSheetParser.parse` (125-170), `parse_cell` (189-244), `parse_row` (282-304),
and `worksheet/_read_only.py`, `_cells_by_row` / `_get_row` (60-138).
- `parse()` dispatches main-namespace rows at end events without checking their
  parent. Nested rows therefore emit before their populated containing row;
  the read-only counter can then skip the containing row. Rows outside
  sheetData or inside cells are also dispatched. Multiple, misplaced or foreign
  sheetData containers do not constrain this row dispatch; missing sheetData
  is not validated as a required singleton.
- `parse_row()` calls `parse_cell()` for every direct child regardless of its
  local name or namespace. An x child or foreign-namespace cell with a canonical
  v child is interpreted as a cell. The F8=999 then E8 case can be truncated when
  iteration derives width from the last cell. A nested row already cleared at
  its end event remains a direct child and can be interpreted as an empty cell.
- Missing cell r is inferred from the preceding column; missing row r is inferred
  from the preceding row. Some noncanonical forms are normalized (lowercase cell
  columns and integer-valued decimal row numbers); other malformed coordinates
  raise during parsing. The scanner now refuses before any of these interpretations.
- A c outside a direct row is not independently emitted by the consumer; a wrapped
  or nested c is not traversed as another cell by parse_row. Foreign rows are not
  dispatched as rows. These shapes can therefore be ignored/reinterpreted rather
  than preserving the scanner's populated-input model, and are refused.

Implementation: a parent-tag stack is maintained on every start/end event in
all scanned sheet parts for both kinds. Structural checks run at start events
before coordinate order checks. Exactly one main-namespace sheetData must be a
root worksheet child (absence checked at end of part). Every row must be a direct
child of that container. Every direct row child must be a main-namespace c with
an explicit canonical r; every c must be a direct row child. Foreign/unqualified
structural names are refused. Row r must be explicit and canonical, child row
numbers must match, and round-1 strictly increasing row/column order remains.
All structural refusals use existing XML_INVALID before producer/history. Existing
numeric bounds, resource ceilings and their codes remain unchanged; coordinate
syntax failures at this structural boundary use XML_INVALID. No regex slicing.

Regression matrix: **17 shapes x 3 budget parts = 51 raw authenticated uploads**;
**17 shapes x 2 funders parts = 34 raw authenticated uploads**. Each requires HTTP
400/XML_INVALID, no producer call, and an unchanged exact FinanceRun identity set.
Shapes: nested row; x child; foreign-namespace child; missing/malformed cell r;
missing/malformed row r; second/missing/nested/foreign sheetData; row outside
sheetData; row inside cell; foreign row; c outside row; c inside c; wrapped c.
Includes the exact populated Expenditure row 2/nested row 3 and budget row 8
F8=999/nested row 9 reproductions, plus budget x F8=999 followed by c E8.
Ordered budget controls still reach BUDGET_HIERARCHY_INVALID; ordered funders
retain their ledger row. Both canonical-variety controls include an inline-string
cell and a serialized empty self-closing styled cell and reach candidates (funders
retain one ledger row).

Focused GREEN: **Ran 9 tests in 1.984s; OK**, zero skips.
Log: `venv/wp4-structure-green.log`.

First full run: **Ran 815 tests in 54.010s; FAILED (failures=1, skipped=11)**,
log `venv/wp4-structure-full-green.log`. The retained-row-subtree limit fixture
used a direct row child a, so the new structure check correctly refused on start
event 4 rather than the expected node-cap event 6. Changed only that fixture to
canonical c/is/t nesting with explicit A1, retaining the same limit of 3, expected
six-event rejection, released ceiling assertion and XML_INVALID code.

PENDING supervisor PostgreSQL gate: ten PostgreSQL-only tests (two budget lock/race
tests, seven released concurrency tests, one conditional unique-constraint test),
plus PostgreSQL migration/constraint validation. Named reasons unchanged:
`Requires PostgreSQL advisory locks, row locks and separate connections; SQLite is functional evidence only.`,
`Requires PostgreSQL advisory locks and separate connections.`, and
`Requires PostgreSQL conditional unique constraint release evidence.` The remaining
skip is `real payroll ledger not on this machine`. D38 real-export rejection,
corrected acceptance and capacity/RSS benchmarks for both kinds remain PENDING;
deployment and live verification remain PENDING. No network, production access,
or changes outside this clone. These results are local synthetic SQLite evidence.

Git result: **uncommitted**. This session explicitly grants read-only access to
this clone's `.git`; no staging/commit or metadata workaround was attempted.
Deliverables: `api/parsers/finance_workbook.py`, `api/tests_finance_sheet_order.py`,
`api/tests_finance_upload_safety.py`, `documentation/build-log.md`.
Pre-existing `.review-detached.pid` untouched. Evidence logs remain in ignored venv.

Final GREEN:
- `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py test api --noinput`
  — **Ran 815 tests in 54.143s; OK (skipped=11)**: **804 passed**, zero failures/errors.
  Log: `venv/wp4-structure-full-green-final.log`. Existing missing-staticfiles
  warning remains; no new unexplained warning or xfail.
- `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py check`
  — **System check identified no issues (0 silenced).**
- `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py makemigrations --check --dry-run`
  — **No changes detected.**
- Documentation-inclusive `git diff --check` — **passed**.

## WP4 backend stage, fix pass 3 (real-export hyperlinks)

D40 supervisor finding: supporting-document worksheet hyperlinks were refused
as external data references. Local baseline: cd8cf15 on feat/wp4a-budgets-backend.
Authority: plan section 5.2 and D29–D31/D38, with the task's binding D40 admission.
Installed openpyxl 3.1.5 worksheet/_reader.py parse() maps HYPERLINK_TAG to
HyperlinkList sheet properties, separately from rows/cells; verified locally.

RED before parser changes, using DATABASE_URL=sqlite:///:memory: and venv/bin/python:
`manage.py test api.tests_finance_budgets.BudgetTests.test_worksheet_hyperlinks_preserve_candidate_figures api.tests_finance_budgets.BudgetTests.test_external_reference_refusals_preserve_history_before_producer --noinput`
— Ran 2 tests in 0.325s; FAILED (errors=1), one passed. Hyperlink fixture confirmed
both serialized worksheet relationship parts have the exact OOXML hyperlink Type
and TargetMode="External", then failed in scan with BUDGET_EXTERNAL_REFERENCE.
All seven refusal controls passed over authenticated HTTP, with no producer call
and the unchanged exact FinanceRun identity set. Log: venv/wp4-hyperlinks-red.log.

Implementation: an External TargetMode is allowed only with Type exactly
http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink
in a .rels part whose immediate directory is xl/worksheets/_rels. Nested paths
and workbook-level hyperlinks are excluded. Every other external mode still
raises BUDGET_EXTERNAL_REFERENCE. externalLinks/ parts, vbaProject.bin and external
formula references remain refused. No target is read, resolved, fetched, logged
or persisted by this change. The funders kind does NOT run _budget_relationships;
its path and funders services are unchanged.

The positive regression uses openpyxl cell.hyperlink on required-sheet F6 and
ancillary-sheet A1, explicitly scans after preflight, then creates a candidate via
authenticated raw HTTP with the real producer. The complete stored derived payload
matches the unlinked control and contains no target URL. Negative HTTP cases:
worksheet image, worksheet unknown Type, workbook hyperlink, nested non-worksheet
hyperlink, externalLinks part, VBA part, and [Book] formula reference.

First focused post-fix run: Ran 2 tests in 0.378s; FAILED (errors=1) because the
new assertion incorrectly indexed payload['derived']. FinanceRun.payload already
stores derived; corrected the assertion to compare the complete payloads.
Focused GREEN: Ran 2 tests in 0.373s; OK, zero skips.
Log: venv/wp4-hyperlinks-green.log.

PENDING supervisor: PostgreSQL full API gate, including ten PostgreSQL-only tests
and migration/constraint validation; D38 real-export re-check for budget acceptance
and funders retention, with capacity/RSS evidence. No real operator export was
available here. Named PostgreSQL skip reasons remain:
- Requires PostgreSQL advisory locks, row locks and separate connections; SQLite is functional evidence only.
- Requires PostgreSQL advisory locks and separate connections.
- Requires PostgreSQL conditional unique constraint release evidence.
The other existing skip is: real payroll ledger not on this machine.
No new migration, environment variable, schedule or one-off operation is required.
All evidence here is local synthetic SQLite evidence; deployment/live verification
are not claimed. No network or production access occurred.

Git: uncommitted because this session's filesystem policy explicitly grants only
read access to .git; no metadata write or workaround attempted. Changed files:
api/parsers/finance_workbook.py, api/tests_finance_budgets.py,
documentation/build-log.md. Pre-existing .review-detached.pid remains untouched;
run logs are in ignored venv.

Final GREEN:
- DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py test api --noinput
  — Ran 817 tests in 54.377s; OK (skipped=11): 806 passed, zero failures/errors.
  Log: venv/wp4-hyperlinks-full-green.log.
- DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py check
  — System check identified no issues (0 silenced).
- DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py makemigrations --check --dry-run
  — No changes detected.
- Documentation-inclusive git diff --check — passed.

## WP4 backend stage, fix pass 4 (Excel error cells)

Baseline edd2ef7 on feat/wp4a-budgets-backend; installed publisher supplied by
the supervisor from masi-finance main 480dc00. Binding D41 supersedes section
5.2's Excel-error-cache wording: preflight owns safety/shape; producer owns meaning.

RED before parser edits, authenticated HTTP with the real producer wrapped by a spy:
`DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py test api.tests_finance_budgets.BudgetTests.test_actual_label_excel_error_preserves_candidate_payload api.tests_finance_budgets.BudgetTests.test_ancillary_excel_error_preserves_candidate_payload api.tests_finance_budgets.BudgetTests.test_budget_amount_excel_error_records_producer_failure --noinput`
— Ran 3 tests in 0.409s; FAILED (failures=3), zero skips. All three reached
HTTP 201 but the producer was called zero times because scan refused error cells.
Log: venv/wp4-excel-errors-red.log. Fixture reload verifies error data_type=e.

Implementation removes only the error-typed-cell require and its code from the
budget scanner. No replacement semantic check; every other preflight code/limit
and the funders services remain unchanged. The two accepted-error HTTP tests
compare the complete stored derived payload to an unedited control and require
a candidate with no failure. The consumed F6 error uses the real producer once
and retains a failed run with phase=producer, code/message=BUDGET_AMOUNT_INVALID,
the selected dependency and no payload.

Tests removed: none. Rewritten:
`api.tests_finance_budget_safety.BudgetSafetyTests.test_parser_diagnostics_never_leak_auxiliary_values`
previously relied indirectly on the deleted error refusal; now a row 5001
inline-string fixture exercises existing SHEET_BOUNDS and preserves the assertion
that private cell text is absent from diagnostics. Initial focused post-fix run:
30 tests in 6.817s; FAILED (failures=1), because this rewritten test expected
BUDGET_SHEET_LIMIT instead of the existing SHEET_BOUNDS. Corrected only its assertion.
Focused final GREEN: 30 tests in 6.855s; OK, zero skips.
Log: venv/wp4-excel-errors-focused-green-final.log.

PENDING supervisor: PostgreSQL full API gate (ten PostgreSQL-only tests,
including two budget lock/race tests, seven released concurrency tests and one
conditional unique-constraint test), plus migration/constraint validation.
Named skip reasons unchanged:
- Requires PostgreSQL advisory locks, row locks and separate connections; SQLite is functional evidence only.
- Requires PostgreSQL advisory locks and separate connections.
- Requires PostgreSQL conditional unique constraint release evidence.
The other existing skip is: real payroll ledger not on this machine.
PENDING supervisor D38 real-export re-check: budget acceptance, funders retention
and capacity/RSS evidence. All results here are local synthetic SQLite evidence.
No new migrations, environment variables, schedules or one-off operations required.
No network, production access, changes outside this clone or funders service edits.

Git: uncommitted; session filesystem policy explicitly makes .git read-only.
No staging/commit or metadata workaround attempted. Deliverables:
api/parsers/finance_workbook.py, api/tests_finance_budgets.py,
api/tests_finance_budget_safety.py, documentation/build-log.md.
Pre-existing .review-detached.pid untouched; evidence logs in ignored venv.

First full run, started before the privacy-test assertion correction:
Ran 820 tests in 54.587s; FAILED (failures=1, skipped=11); the sole failure was
that same SHEET_BOUNDS versus BUDGET_SHEET_LIMIT assertion.
Log: venv/wp4-excel-errors-full-green.log.

Final GREEN:
- `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py test api --noinput`
  — Ran 820 tests in 54.466s; OK (skipped=11): 809 passed, zero failures/errors.
  Log: venv/wp4-excel-errors-full-green-final.log. Existing missing-staticfiles
  warning remains; no new unexplained warning or xfail.
- `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py check`
  — System check identified no issues (0 silenced).
- `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py makemigrations --check --dry-run`
  — No changes detected.
- Documentation-inclusive `git diff --check` — passed.
- `rg -n BUDGET_EXCEL_ERROR api` — no remaining code/test references.

## WP4 backend stage, fix pass 5 (cell payload parity)

Baseline 364848e, feat/wp4a-budgets-backend; installed publisher supplied from
masi-finance main 480dc00. Read plan section 5.2 and D29-D31/D38; inspected
installed openpyxl 3.1.5 WorkSheetParser.parse_cell/parse_formula,
Text.content, RichText/InlineFont/PhoneticText, CellRichText.from_tree,
read_string_table and Serialisable.from_tree.

RED before scanner edits:
`DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py test api.tests_finance_cell_payloads --noinput`
Initial run: 35 tests in 2.424s, FAILED (failures=34). Replaced the rejection
mock with a wrapped real producer so RED demonstrates actual downstream behavior,
not an invalid mock artifact. Final RED output: venv/wp4-cell-payload-red-final.log.
Test names: CellPayloadUploadTests.test_{budgets,funders}_{shape}_refused,
where shape is wrapped_v, duplicate_v, nested_v, unknown_cell_child,
foreign_cell_child, wrapped_inline_t, unknown_inline_child, wrapped_shared_t,
unknown_shared_child, duplicate_f, nested_f, duplicate_is, duplicate_plain_t,
duplicate_run_t, nested_run_properties, foreign_shared_child.
Controls: test_{budgets,funders}_payload_controls and
test_rich_header_scanner_matches_openpyxl.
Final RED: Ran 35 tests in 2.819s; FAILED (failures=34), zero skips.
The 32 malformed-payload tests failed refusal assertions; the rich-header test
failed both inline/shared subtests because preflight missed the required header.
Both original control tests passed. All tests use raw authenticated uploads.

Implementation: shared streaming _Payload validates main-namespace c children
(f/v/is, each at most once), text-only v/f, and the is/si child grammar from
Text/RichText/InlineFont/PhoneticText. Only r/rPh repeat; rPr properties are known
leaf children, phoneticPr is a leaf. Unknown/foreign children, wrappers, duplicate
singletons, nested text leaves and ignored mixed text refuse as XML_INVALID.
Text.content projection uses direct plain t first, then direct r/t in run order;
rPh text is excluded. Shared-string projection also mirrors read_string_table's
x005F_ removal. Existing sst/si strictness, per-entry descendant bound, every
released limit/code and clearing/detaching remain intact; no regex XML slicing.
No funders service edits, new migration, environment variable, schedule or one-off
operation. No network or production access; all writes stay inside this clone.

Focused initial GREEN: 35 tests in 2.495s; OK, zero skips.
Log: venv/wp4-cell-payload-focused-green.log.
First full GREEN: 855 tests in 61.757s; OK (skipped=11), 844 passed.
Log: venv/wp4-cell-payload-full-green.log.
Controls then strengthened to use valid rich-text headers and require candidate
status on every accepted case. This exposed a fixture issue: arbitrary formula
in budget L1 violates the producer's date contract (BUDGET_MONTH_INVALID).
Intermediate focused run: 35 tests in 2.520s, FAILED (failures=1).
Changed that control to the supported M1 formula INT(MONTH(L1)) with cached v=3;
the funders control retains its formula plus cached date at A2.
Final focused GREEN: 35 tests in 2.564s; OK, zero skips.
Log: venv/wp4-cell-payload-focused-green-final.log.

Regressions: 16 named malformed-payload tests per kind, each requiring HTTP 400,
XML_INVALID, no producer call and an unchanged FinanceRun identity set. Per-kind
controls require HTTP 201/candidate and inspect the exact producer input stream
with openpyxl in both data-only and formula modes: plain date, rich shared string
with rPr, rich inline string, both with phoneticPr/rPh, formula plus cached v.
Rich header assertion covers inline/shared plain-after-run XML, ignored phonetic
text and shared-string escape removal; scanner input to _label equals the
openpyxl header value Date.

PENDING supervisor: PostgreSQL full API gate, including ten PostgreSQL-only
tests and migration/constraint validation. Existing named skip reasons:
- Requires PostgreSQL advisory locks, row locks and separate connections; SQLite is functional evidence only.
- Requires PostgreSQL advisory locks and separate connections.
- Requires PostgreSQL conditional unique constraint release evidence.
The eleventh existing skip is: real payroll ledger not on this machine.
PENDING supervisor D38 real-workbook re-check: budget acceptance, released funders
retention, capacity/RSS evidence. Synthetic local SQLite is not PostgreSQL,
real-export, deployment or live-data proof.

Git: uncommitted because session policy explicitly makes .git read-only; no
metadata write/workaround attempted. Deliverables: api/parsers/finance_workbook.py,
api/tests_finance_cell_payloads.py, documentation/build-log.md.
Pre-existing .review-detached.pid remains untouched; logs are in ignored venv.

Final GREEN:
- `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py test api --noinput`
  — Ran 855 tests in 63.704s; OK (skipped=11): 844 passed, zero failures/errors.
  Log: venv/wp4-cell-payload-full-green-final.log. Existing missing-staticfiles
  warning remains. Synthetic shared-string probes: rejected peak RSS 120143872
  bytes (2051 events); accepted peak RSS 145260544 bytes. These are synthetic
  subprocess bounds only, not D38 real-workbook capacity evidence.
- `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py check`
  — System check identified no issues (0 silenced).
- `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py makemigrations --check --dry-run`
  — No changes detected.
- Documentation-inclusive `git diff --check` — passed.
- AST comparison against 364848e — all 13 released MAX_* expressions unchanged.

## WP4 backend stage, review fixes round 3 (type-dependent payloads)

Baseline 9fbc0ed on feat/wp4a-budgets-backend; publisher supplied from main
480dc00. Read CLAUDE.md, existing finance build-log pipeline entries, plan 5.2,
and decisions D29-D31, D38, D40, D41. Consumer inspected directly:
venv/lib/python3.13/site-packages/openpyxl/worksheet/_reader.py, parse_cell.

RED before scanner edits:
`DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py test api.tests_finance_cell_payloads.CellTypePayloadUploadTests --noinput`
— Ran 48 tests in 3.896s; FAILED (failures=20), zero skips.
Log: venv/wp4-type-red.log. Names are
CellTypePayloadUploadTests.test_{budgets,funders}_{shape}_{refused,control}.
Refused shapes: inline_v, numeric_is, shared_is, shared_index_outside_table,
shared_negative_index, shared_noninteger_index, unknown_type, inline_is_and_v,
default_is, boolean_is, date_is, error_is, string_is.
Control shapes: numeric, default_numeric, formula_cache, inline, shared,
boolean, date, error, string, empty_styled, empty_shared.
The 18 failures for newly covered incompatible/unknown types demonstrate admission
past preflight; existing shared-index and shared-is refusals pass. Two additional
failures show empty shared cells were refused although the consumer returns None.
Every refusal asserts HTTP 400/XML_INVALID, no producer call and unchanged
FinanceRun identity set. Raw authenticated controls wrap the real producer,
inspect its input in read-only data-only and formula modes (value and Python type),
and require HTTP 201/candidate. Malformed cases append ordered F8, matching the
review reproduction; controls use unused H1 (budget) or Z1 (Funder Budgets).

Implementation: _Payload captures and allowlists the enclosing c type at its
start event; incompatible direct children refuse immediately as XML_INVALID.
The grammar excludes even empty incompatible v/is children, retaining a canonical
payload shape. Shared-string indices retain the existing integer conversion and
0 <= index < admitted table length check; absent/empty v now bypasses lookup,
matching parse_cell's `findtext(VALUE_TAG, None) or None`.

Consumer-checked per-type table (openpyxl 3.1.5 parse_cell):

| Cell t | Data-only child read and conversion | Formula-mode child | Refused child |
| --- | --- | --- | --- |
| absent | v; numeric, with style date conversion | f if present, otherwise v | is |
| n | v; numeric, with style date conversion | f if present, otherwise v | is |
| b | v; bool(int(value)) | f if present, otherwise v | is |
| d | v; from_ISO8601 | f if present, otherwise v | is |
| e | v; error text retained under D41 | f if present, otherwise v | is |
| s | v; int index into admitted shared strings | f if present, otherwise v | is |
| str | v; string, output type s | f if present, otherwise v | is |
| inlineStr | is; Text.content (plain plus runs) | f if present, otherwise is | v |
| unknown, including empty t | XML_INVALID at cell start | XML_INVALID | all |

f/v/is remain singletons; legitimate f plus cached v remains admitted on every
supported non-inline type. Empty styled cells and empty shared cells return None.
Only selection/shape is newly enforced; semantic conversion remains with the
consumer and producer. Existing D40/D41 logic and funders services are untouched.
No models, migrations, schedules, environment variables or one-off operations
required. AST comparison against 9fbc0ed: all 13 MAX_* expressions unchanged.

Focused GREEN: `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py test api.tests_finance_cell_payloads --noinput`
— Ran 83 tests in 6.003s; OK, zero skips.
Log: venv/wp4-type-focused-green.log.

PENDING supervisor: PostgreSQL full API gate and migration/constraint validation.
Ten PostgreSQL-only tests retain the named reasons:
- Requires PostgreSQL advisory locks, row locks and separate connections; SQLite is functional evidence only.
- Requires PostgreSQL advisory locks and separate connections.
- Requires PostgreSQL conditional unique constraint release evidence.
The other existing skip is: real payroll ledger not on this machine.
PENDING supervisor D38 real-workbook re-check: budget export acceptance, released
funders retention, and capacity/RSS evidence. Local synthetic SQLite is not
PostgreSQL, real-workbook, deployed or live-data proof.

Git: uncommitted; session filesystem policy makes .git read-only. No metadata
write or workaround attempted. Files: api/parsers/finance_workbook.py,
api/tests_finance_cell_payloads.py, documentation/build-log.md.
Pre-existing .review-detached.pid untouched. Logs stay in ignored venv.
No network, production access or writes outside this clone.

Final GREEN:
- `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py test api --noinput`
  — Ran 903 tests in 68.867s; OK (skipped=11): 892 passed, zero failures/errors.
  Log: venv/wp4-type-full-green.log. Existing missing-staticfiles warning remains.
- `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py check`
  — System check identified no issues (0 silenced).
- `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py makemigrations --check --dry-run`
  — No changes detected.
- Documentation-inclusive `git diff --check` — passed.

Supervisor verification, 2026-09-07 (Codex handoff continuation):
- Reviewed the three-file fix-pass-6 diff against 9fbc0ed. Full local PostgreSQL
  API gate: Ran 903 tests in 97.085s; OK (skipped=1), PostgreSQL 17.10 on the
  verified masi-wp2-pg container, localhost:5544, test_masi_test. The remaining skip
  is the unavailable real payroll ledger; SQLite is not used for this evidence.
- manage.py check: System check identified no issues (0 silenced).
- manage.py makemigrations --check --dry-run: No changes detected.
- git diff --check: passed on the three changed files.
- D38 actual local files through preflight plus scan_workbook: funders ACCEPTED
  (12,132,538 bytes, source SHA prefix 9784baa1, 21.88 s); current budget export
  ACCEPTED (1,460,069 bytes, source SHA prefix 3e6b78d0, 6.03 s). Budget bytes differ
  from the handoff snapshot; these timings describe the files read in this check.
  No money, labels, or row content is included in this log. These are scanner
  acceptance results, not successful budget production or full-path capacity proof.
- Pending: independent round-4 review, exact-commit independent-clone reproduction,
  worker RSS/concurrent-reader capacity, hosted deployment and role probes.

## 2026-09-07 — WP4 backend fix pass 7: formula definition fidelity and names

Independent review round 4 found two admission gaps at base 3c8996c on
feat/wp4a-budgets-backend. The high reproduction uses G6 shared master (half
lookup) and G7 shared follower with explicit full lookup text: openpyxl silently
ignores the follower's definition and translates the master. The medium uses a
workbook defined name containing an external reference, or a direct external
name token without `!`, to admit a cached budget assertion. Synthetic probes:
/private/tmp/masi-review4-probes.py, tightened adjacent cases lines 64–87.
Read CLAUDE.md, existing build log, canonical WP4 plan sections 5–8 and binding
D29–D41. No publisher/package source change in this pass.

Consumer inspection: installed openpyxl 3.1.5 WorkSheetParser.parse_formula
retains normal formula text, translates later shared formula instances from the
first instance (ignoring any later text/ref), retains array text/ref in
ArrayFormula, and discards dataTable text while retaining its input/orientation
attributes in DataTableFormula. Unknown t falls through as normal; shared si and
data-table inputs on other types are ignored. Calculation hints remain admitted.

Implementation:
- Per-sheet shared registry contains only index strings of at most 10 digits and
  two coordinate pairs per master, capped by existing MAX_SHEET_RETAINED_NODES.
  It retains no formula text, tokens or XML trees. It resets per sheet. Masters
  need a bounded ref and text; followers need an earlier master, no text/ref and
  coordinates inside that master ref. Duplicate explicit definitions refuse even
  if their text happens to agree: there must be only one authored definition.
- Unknown formula types, incompatible si/ref/data-table metadata, and dataTable
  text refuse as XML_INVALID before either producer and before FinanceRun insert.
  Empty shared followers, canonical array/dataTable formulas and ordinary formula
  calculation hints remain admitted. Existing sheet limits and all 13 released
  MAX_* expressions are unchanged (AST comparison against 3c8996c).
- Budget external-reference token checks include external names without `!` and
  every workbook definedName definition, including unused names. Definitions are
  checked for external dependencies only; internal name interpretation, built-in
  names, constants and structured refs stay with the consumer/producer. No name
  evaluation, recursion or dependency graph is introduced. The workbook metadata
  part remains covered by its existing byte limit. D40 hyperlinks and D41 error
  cells retain their existing behavior.

Named RED:
- `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py test api.tests_finance_formula_payloads --noinput`
  — Ran 41 tests in 4.158s; FAILED (failures=24), zero errors/skips.
  Log: venv/wp4-formula-red.log. New admission cases returned 201 instead of 400.
  Named groups: test_budget_adjacent_explicit_shared_follower_refused;
  test_budget_external_{bare_name,defined_external_name,defined_formula,
  defined_sheet,unused_defined_external}_refused; both-kind explicit follower,
  missing shared si/master/ref, outside/redefined ref, unknown type, normal si,
  and ignored dataTable text refusals. Direct external sheet rejection already
  passed. Ordinary adjacent half/full control reached the real producer and
  failed BUDGET_BC_BINDING_INVALID; valid empty follower candidate approved.
- Same command after adding incompatible data-table attribute cases and two
  internal controls — Ran 49 tests in 4.260s; FAILED (failures=6).
  Log: venv/wp4-formula-attributes-red.log. The six named new failures are
  test_{budgets,funders}_{normal,array,shared}_datatable_inputs_refused.

Final focused GREEN:
- `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py test api.tests_finance_formula_payloads api.tests_finance_cell_payloads api.tests_finance_budget_safety api.tests_finance_upload_safety --noinput`
  — Ran 201 tests in 30.776s; OK, zero skips. Log:
  venv/wp4-formula-focused-green.log. Includes all 49 new tests and existing
  D40/D41/payload/bounded-upload regressions. Every new malformed test posts an
  authenticated raw XLSX and asserts fixed-code HTTP 400, no producer call and
  unchanged FinanceRun identity set. Valid controls wrap the real producer and
  require candidate plus successful explicit approval, for both kinds.
- `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py check`
  — System check identified no issues (0 silenced).
- `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py makemigrations --check --dry-run`
  — No changes detected.

No migrations, schema/version/dependency changes, environment variables, schedules
or one-off operations required. No network, production, .env or Git metadata
writes. Only api/parsers/finance_workbook.py,
api/tests_finance_formula_payloads.py and documentation/build-log.md changed;
pre-existing .review-detached.pid remains untouched. Changes stay uncommitted.
Logs remain in ignored venv.

PENDING supervisor: PostgreSQL full API and migration/constraint gate on final
source; D38 real funders and budget export scan re-check; successful-path worker
RSS/concurrency/capacity evidence. Synthetic local SQLite tests do not establish
PostgreSQL, real-file, hosted, deployment or field evidence. The existing SQLite
skip reasons remain PostgreSQL advisory/row locks and separate connections,
PostgreSQL conditional unique constraint release evidence, and unavailable real
payroll ledger. Existing missing-staticfiles warning remains.

Final full GREEN:
- `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py test api --noinput`
  — Ran 952 tests in 80.532s; OK (skipped=11): 941 passed, zero failures/errors.
  Log: venv/wp4-formula-full-green.log. The skip boundary above is unchanged.
- Documentation-inclusive `git diff --check` — passed.
- Final scope preflight: branch feat/wp4a-budgets-backend, HEAD 3c8996c;
  the three listed source/log files changed and .review-detached.pid untouched.

Supervisor gates, 2026-09-08, final fix-pass-7 code tree:
- PostgreSQL 17.10, verified local masi-wp2-pg on localhost:5544, guarded
  test_masi_test: Ran 952 tests in 96.883s; OK (skipped=1). The one skip is the
  unavailable real payroll ledger. System check no issues; no migration changes.
- D38 actual funders preflight+scan ACCEPTED (12,132,538 bytes, source SHA prefix
  9784baa1, 19.81s); revised budget export ACCEPTED (1,459,890 bytes, source SHA
  prefix 639caabc, 3.27s). Jim confirmed removing the intentionally zero-variance
  budget line on 2026-09-08. This is scanner acceptance, not production approval
  or full-path capacity evidence. Real files remain private and unmodified.
- Pending independent review, exact-commit independent PostgreSQL reproduction,
  successful-path RSS/concurrency, deployment and live role probes. Backend main
  remains untouched because merging it would deploy.

## 2026-09-08 — WP4 producer canonical-input refusal history

The assembled backend at `0a6e4ce179491cf306e5a558f5a2149d27a23748` did not
recognize the publisher's fixed `WORKBOOK_NOT_CANONICAL` domain code. An upload
that passed backend admission but was refused by the publisher therefore
returned HTTP 500 without failed-run history. The funder fixed-code allowlist
and budget exact-argument handler now recognize that single code. Known typed
producer refusals return HTTP 201 with an immutable failed run, in accordance
with the existing safe producer-domain failure policy. No generic exception
handling, parser admission rules, publisher behavior or schema pins changed.

Tests use the real installed publisher 0.2.0 wheel built from `c88565798f1f`,
as identified by its local distribution `direct_url.json`: wheel SHA-256
`1da019d71a129c7e186d7ed26b82f6e1812a0da96b1dbba58123ba392f6f0da1`.
Synthetic authenticated raw XLSX requests exercise both funders and budgets,
with inline and shared strings mixing plain text and rich runs. The backend
scanner accepts the header interpretation; the publisher intentionally refuses
the noncanonical source representation. Each refusal retains only the fixed
producer-phase failure metadata, with null payload and hashes, zero fact counts
and unchanged ledger/allocation identity sets. Approval returns HTTP 409
`INVALID_TRANSITION`. Same-byte replay returns the existing failed run without
calling the producer again.

Unknown producer codes, arbitrary text, decode failures, a code with trailing
private text, multiple exception arguments, and the same exact spelling in an
unexpected RuntimeError remain HTTP 500 with no run or fact history. The older
rich-header test retains its direct scanner and both openpyxl reader-mode
assertions; its candidate expectation was replaced by the explicit producer
refusal tests rather than weakening publisher admission.

Named TDD evidence (logs in ignored `venv/`):

- Funder `test_funders_noncanonical_producer_refusal_is_failed_history`:
  RED ran 1 test in 0.080s, 2 failing inline/shared subtests, HTTP 500
  `UPLOAD_INTERNAL_ERROR` instead of HTTP 201. GREEN ran 1 test in 0.096s, OK.
  Logs: `wp4-domain-funders-red.log`, `wp4-domain-funders-green.log`.
- Budget `test_budgets_noncanonical_producer_refusal_is_failed_history`:
  RED ran 1 test in 0.103s, 2 failing inline/shared subtests, HTTP 500
  `WORKBOOK_DECODE_FAILURE` instead of HTTP 201. GREEN ran 1 test in 0.136s, OK.
  Logs: `wp4-domain-budgets-red.log`, `wp4-domain-budgets-green.log`.
- The former rich-header candidate control reproduced 2 failures in 0.264s
  after domain admission was corrected: actual status was failed, with the
  fixed producer code. Log: `wp4-domain-rich-control-red.log`.
- Both new refusal tests, the preserved scanner/openpyxl parity test, and
  `test_untrusted_producer_diagnostics_remain_internal_without_history`:
  ran 4 tests in 0.538s, OK. Log: `wp4-domain-boundary-green.log`.

Final validation:

- `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py test api.tests_finance_cell_payloads api.tests_finance_formula_payloads api.tests_finance_runs_upload api.tests_finance_budgets api.tests_finance_budget_safety api.tests_finance_upload_safety --noinput`
  — Ran 249 tests in 51.497s; OK, zero skips. Log:
  `venv/wp4-domain-focused-green.log`.
- `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py test api --noinput`
  — Ran 955 tests in 74.445s; OK (skipped=11): 944 passed, zero failures/errors.
  Log: `venv/wp4-domain-full-green.log`. Existing skips require PostgreSQL
  advisory/row locks and separate connections, PostgreSQL conditional unique
  constraint release evidence, or the unavailable real payroll ledger.
- `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py check`
  — System check identified no issues (0 silenced).
- `DATABASE_URL=sqlite:///:memory: venv/bin/python manage.py makemigrations --check --dry-run`
  — No changes detected.

No migrations, dependency changes, environment variables, schedules or one-off
operations are required. This work writes only `api/services/finance_runs.py`,
`api/tests_finance_cell_payloads.py` and this build log; the pre-existing
`.review-detached.pid` is untouched. Source changes remain uncommitted. No Git,
PostgreSQL, network, real workbook, production or environment-file writes were
performed. The existing missing-staticfiles warning remains. Independent review
and final PostgreSQL evidence remain with the supervisor; local SQLite tests do
not establish PostgreSQL, real-file, hosted, deployment or capacity evidence.

## 2026-09-08 — WP4B operator-triggered Google budget refresh

Status: isolated implementation on `feat/wp4b-budget-pull`, based on reviewed
WP4A `ada4414`; not merged or deployed. Implements approved WP4 plan section 5.3.

- Adds publisher-only `POST /api/finance/runs/pull-budget/`. Only JSON `year` and
  `ledger_run_id` are accepted; actual request bytes are capped at 4 KiB, duplicate
  fields and unknown inputs refuse before acquisition. Dependency admission also
  precedes Google access and is repeated under the ordinary transaction locks.
- Both transports enter the same candidate service, scanner, producer, identity
  lookup, and approval policy. Acquisition method is provenance, not identity:
  upload/pull replays retain the first immutable run and original acquisition.
  Pull measurements include the network phase. No migration or new run state.
- The server uses `GOOGLE_CREDENTIALS`, `GOOGLE_SERVICE_ACCOUNT_EMAIL`, and
  `MASI_BUDGET_<year>_URL`. Only the configured docs.google.com sheet is selected;
  OAuth audience and Drive origins are fixed, readonly scope, no delegated subject,
  redirects, automatic approval, polling, or retries. Secrets remain server-side.
- Drive modifiedTime/version are checked before and after the XLSX export. UTC
  source modification date forms the basename. Actual bytes are hashed; equal
  modification metadata does not imply byte-identical Google exports.
- Acquisition uses one cancellable 60-second deadline over async DNS, TLS, headers,
  token, metadata, and export bodies. Explicit `aiohttp==3.14.3` and
  `aiodns==4.0.4` dependencies avoid the Requests inactivity-timeout gap and default
  threaded DNS cleanup. Token/metadata cap 16 KiB; export cap 10 MiB. Identity
  encoding, bounded streams, resolver/session closure, and value-free failures
  apply throughout. Downstream service exceptions retain their own classification.
- TDD: HTTP authorization 404→403; real-producer candidate 503→201; duplicate JSON
  503→400; oversized token response 201→400. A live compressed-token response
  exposed an encoding gap; explicit identity negotiation regression is green.
  Independent review found the overall-deadline and context-yield exception gaps;
  regressions cover DNS cancellation, real localhost HTTP dripping headers/body,
  no remaining tasks, and downstream exception propagation/stream cleanup.
- Full guarded local PostgreSQL 17.10 suite: 969 tests, 1 existing skip, PASS in
  95.723 seconds. Django checks pass; no missing migrations. Focused pull suite
  includes 14 tests. Installed publisher is the exact reviewed `11fba0e` wheel,
  retaining version 0.2.0; no publisher/schema bytes changed in this slice.
- Live readonly Google export + real preflight using the new transport: PASS,
  1,090,534 bytes in 5.441 seconds, zero scanner diagnostics. This is acquisition
  evidence, not production candidate/approval, financial reconciliation, or hosted
  worker capacity proof. Full real-source local HTTP acceptance, frontend build,
  independent revised-source review, exact release pins and deployment remain
  separate gates while this entry is being completed.

API references verified for this implementation:
[Drive export](https://developers.google.com/workspace/drive/api/reference/rest/v3/files/export),
[Drive metadata](https://developers.google.com/workspace/drive/api/reference/rest/v3/files/get),
[aiohttp timeouts](https://docs.aiohttp.org/en/stable/client_reference.html),
[async DNS resolver](https://docs.aiohttp.org/en/stable/client_advanced.html),
[public JWT signing](https://google-auth.readthedocs.io/en/latest/reference/google.auth.jwt.html).

Final local gate update:
- Revised independent code review: APPROVED, zero findings. Independent focused
  backend 13/13 (loopback bind blocked in its sandbox); root executed all 14 pull
  tests including real HTTP header/body deadline cancellation. Independent frontend
  full suite 106/106. `pip check` found no broken requirements.
- Disposable local PostgreSQL real-source HTTP acceptance: PASS in 136.524 seconds.
  Management Accounts candidate: 77.868 seconds, 23,914 facts; budget pull candidate:
  31.494 seconds end-to-end, including live export, 283 findings/13 in-scope errors
  retained. Explicit approval, compatible current metadata and contributor reads
  passed. Process RSS upper observation 367,214,592 bytes; not hosted concurrency
  proof. Test database destroyed normally. No production data changed.
- GitHub metadata confirms the website repositories are public. The originating
  finance repository forbids public pushes; source stays local pending Jim's
  explicit destination decision. No merge, deployment, or publisher release tag.


## 2026-09-08 — WP4 producer 0.3.0 and authorized release

- Pin the reviewed private finance v0.3.0 release and require actual installed
  version 0.3.0 at build. Both upload kinds now produce 0.3.0; cumulative registries
  retain historical 0.2.0 support. Immutable old records and fixture bytes remain
  unchanged. Shared candidate test fixtures take metadata from their artifact.
- New HTTP regressions verify old/new artifact readability, distinct new-version
  candidate identity, replay, dependency compatibility, anti-rollback refusal and
  explicit restoration, and Finance Manager reads with publish/candidate denial.
- Independent review approved with zero findings. Publisher 0.3.0 at
  `0a6d918cee5ac1f3ae043c8b1ac560ba58bc0361`: full suite 3213 passed, 12 skipped,
  1 xfailed; exact wheel and sdist installation/contract gates pass.
- Exact 0.3.0 real-source HTTP acceptance on disposable local PostgreSQL: PASS,
  90.379 seconds overall. Management Accounts candidate 49.823 seconds, 23,914
  facts; live Google budget candidate 22.848 seconds, 283 findings/13 in-scope
  errors retained. Explicit approval, compatible current and contributor reads
  pass. Observed process RSS 330,104,832 bytes. Test DB destroyed; no production
  financial writes. This is not hosted concurrency/browser proof.
- Jim authorized public website source publication and exact Render configuration
  plus both website deployments. Render email/URL keys and installed contract
  verification before migrations were applied and read back. Existing Google
  credentials, three-worker start command and permission grants are preserved.
- Release order: private v0.3.0 tag, backend merge/live deployment, frontend merge.
  Hosted migration/deploy identity and authenticated browser workflow remain
  separate gates. Admin plus Finance Manager are readers; publish remains a
  distinct capability. Old 0.2-only backend is not safe after approving 0.3 runs.

- Final exact-interpreter PostgreSQL gate: 971 tests in 66.770 seconds,
  OK (1 existing skip); Django checks pass, no migration drift. The installed
  0.3.0 version was asserted before database access. Historical helper correction
  independently approved; focused 7/7 passed. An intermediate copied-venv activation
  selected an older interpreter and was discarded; this final gate uses the
  explicit named-clone interpreter.

## 2026-09-09 — WP5 exact organisation totals and annual spending composition

Budget run-detail GET now adds a versioned `budget_insights` sibling after the
existing integrity validation and pinned-dependency authorization. Stored payloads,
producer schemas and facts are unchanged. The report reconstructs retained exact
budget assertions, BC totals and shares under retained precision, reusing producer
projection helpers. It exposes organisation budget/actual/projection/variance totals,
metric completeness, known leaf subtotals and signed rounding residuals. The response
requires only the existing detail request and one calculation-validation replay.

Annual spending composition partitions root departments and unmapped expenditure.
Money is serialized at cents; percentages are computed from exact operands with six
decimal places for chart geometry. Missing, negative or zero-total partitions retain
amounts and reasons without claiming a valid pie. Budget-line projections explicitly
exclude spending outside mapped lines. No new database state, migration, environment
variable, dependency or producer release is required.

Verification on the final source:
- Focused RED: 8 tests with missing-implementation errors; focused SQLite GREEN:
  11/11. Tests cover half cents, scale-1000 retained precision, nested incomplete
  totals, WF/Calc B, orphan and signed composition, one replay, unchanged records,
  denied access and dependency, rehashed arithmetic tamper, and changed facts.
- Full local PostgreSQL 14.17 API suite: 982 tests in 79.669 seconds, PASS with one
  existing skip. Django checks pass; no migration drift.
- Independent source review and 8/8 pure-math tests: no remaining findings.
- Real-source HTTP acceptance with publisher 0.3.0 on a disposable local PostgreSQL
  database: PASS in 140.593 seconds. Imported 23,914 facts, exported the budget
  read-only from Google, reviewed/approved locally, checked the new report identity,
  preserved payload, compatible current and contributor read. Test DB destroyed.
  Budget findings remain 283 total / 13 in-scope errors. Current real-source report
  correctly marks organisation metrics incomplete and the pie unavailable due to
  incomplete actuals, retaining seven composition buckets. No production data write.

Jim authorized live deployment while he arranges a preview subdomain. This entry
records verified local source; exact production commit/deploy evidence is recorded
in the private finance supervision log after release. Hosted authenticated browser
acceptance and concurrent-worker capacity remain separate evidence boundaries.
