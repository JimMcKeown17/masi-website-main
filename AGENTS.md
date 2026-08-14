# Working in this repository

Read `CLAUDE.md`, `documentation/build-log.md`, and the relevant pipeline documentation before making material changes.

## Active handoff — raise this with Jim

Before continuing the unfinished Youth Sessions sync/freshness work, read `../../frontend/masi-website/documentation/handoffs/2026-08-10-youth-sessions-sync-finalization.md` and explicitly bring it up with Jim so the two repositories can be reviewed and finalized. The implementation is currently uncommitted and its production rollout is unverified; do not silently treat it as complete.

## Build log is part of the change

Update `documentation/build-log.md` in the same change whenever you add or materially alter a model, migration, endpoint, sync command, data contract, schedule, or release state. Record:

- what changed and why;
- exact tests and checks with outcomes;
- migrations, environment variables, Render schedules, or one-off operations still required;
- whether the result is only local, built, migrated, deployed, or verified against live data.

Never describe SQLite, local PostgreSQL, CI, or source inspection as production proof. Keep detailed chronology in the build log and keep this file short and stable.

## Repository rules

- Use the repository virtual environment for Python and Django commands.
- Develop and test against local databases. Do not access or mutate production unless the user explicitly authorizes the specific operation.
- Prefer idempotent imports, explicit source identifiers, transactional control-state advancement, and fail-closed freshness semantics.
- Add migrations for model changes and run focused tests plus `makemigrations --check --dry-run`.
- Diagnose root cause before implementing a fix.
- Do not add an agent as a commit co-author.
