# School Programme Grid — Health/Flags Panel

Goal: a staff-facing expander at the bottom of the grid page that presents the
nightly refresh's integrity flags in plain language, grouped by severity, so "79
scary rows" reads as "75 expected-Zazi / 4 watch / 1 info".

## Key facts (decided 2026-06-22)
- Integrity flags are computed in `refresh_school_programme_grid` and printed to
  stdout only — ephemeral. Decision (Jim): **persist the full report nightly**.
- `reach_without_identities` is dominated by Zazi iZandi schools because Zazi
  sessions live in a SEPARATE backend (`Zazi_iZandi_Website_2025`); the grid only
  sees Zazi identities via the nightly export. So most of that flag is EXPECTED,
  not a data error. The panel must classify, not lump.
- Persist on `AirtableSyncLog` (already logs this sync) via a new JSON field;
  `build_grid` serves the latest report; the view is a thin passthrough.

## Backend (repo: Masi Web Main, branch main) — DONE, 152 tests green
- [x] `AirtableSyncLog`: add `details = JSONField(null=True, blank=True)` + migration `0036`.
- [x] `school_programme.py`: enrich `integrity["reach_without_identities"]` to a
      list of `{school, school_uid, programmes}` (no test asserts its shape).
- [x] `school_programme.py`: `build_grid_health(result, rollup, now)` — classifies reach
      into `zazi_sourced` / `masi_staffing` / `manual_count` + a `by_programme_set` summary.
- [x] `school_programme.py`: `latest_grid_health()` + `"health"` on `build_grid`.
- [x] `refresh_school_programme_grid` command: stores `build_grid_health(...)` into
      `sync_log.details`; `_report` prints reach as a count.
- [x] Tests: `api/tests_grid_health.py` (9) — classification + serve path.

## Frontend (worktree: agentic-fundraising, branch feature/agentic-fundraising) — DONE, lint+tsc clean
- [x] `types/school-programme.ts`: `GridHealth` + `health` on `SchoolProgrammeGrid`.
- [x] `components/school-programme/GridHealthPanel.tsx`: collapsible `<details>`,
      severity sections (Needs attention / Known Zazi gap / Reach by programme / Info).
- [x] `<GridHealthPanel>` added to the bottom of the youth page (shows whenever data loads).
- [x] Lint clean (0 errors), `tsc --noEmit` clean.

## Remaining (deploy)
- [ ] Commit + push backend (main) — run migration `0036` on Render.
- [ ] Commit frontend (feature/agentic-fundraising).
- [ ] Re-run `refresh_school_programme_grid` on Render (new command) — panel is null until then.
