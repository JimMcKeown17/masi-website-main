# How We Measure Impact (`/impact/measurement`) — Design Notes

**Date:** 2026-06-12
**Status:** Mockup v2 under review with Jim; not yet specced for implementation
**Parent spec:** `2026-06-12-impact-dashboard-and-measurement-design.md` (§4 defined this page structurally; these notes supersede §4's section list where they differ)
**Mockups:** `measurement-page-mockup/measurement-v1.html` (rejected), `measurement-page-mockup/measurement-v2.html` (current — open in a browser)
**Real dashboard screenshots used in v2:** `measurement-page-mockup/dash-ops.png`, `measurement-page-mockup/dash-ea-map.png`

## What this page is

The credibility engine behind the Impact Dashboard. The dashboard makes a donor feel something; this page makes a due-diligence analyst relax. Calmer register, same design language, exactly one dark band.

## The v1 → v2 lesson (worth remembering for every page)

Jim's reaction to v1: "too cookie cutter, looks AI created, immediately loses credibility — viewer will think this was vibe coded." The diagnosis: **five sections used the same three-equal-cards row**. That uniform card rhythm is the single biggest AI-design tell.

The v2 fix, as design rules:

1. **No two adjacent sections share a layout DNA.** v2 alternates: asymmetric copy+diagram, flowing-line pipeline, 2-col chips+sticky radar, table-led section, layered stack, phones, single feature card, full-bleed screenshots, prose+sidebar.
2. **Real artifacts beat styled cards.** The two actual Zazi dashboard screenshots (including a red "ACTION REQUIRED" state) are the most credible elements on the page — they prove the system exists and that we publish our own bad weeks.
3. **Equal-card rows only as quiet footers** (the Explore row), never as content.

## v2 page structure (11 sections)

1. **Hero** — "We measure learning, not just activity." One inline pulse line (no cards).
2. **Evidence triangle** — streams + triangulation merged. SVG: gradient-ringed nodes (Daily sessions / Formal assessments / Mentor visits), labeled edges (dosage × outcomes, quality × dosage, outcomes × quality), "Every child — one evidence record" center, ρ = 0.93 chip.
3. **The loop** — Collect → Clean → Analyze → **Coach** (highlighted) → Adapt → Report as a flowing line. Key line: "the point of measurement is the coaching conversation days after the data lands."
4. **What we measure** — literacy 11-skill + numeracy 9-component chip panels, with the child radar chart docked right ("what that looks like for one child"). The radar deliberately appears on BOTH pages — story on the dashboard, system here.
5. **Benchmarks** — national benchmarks table by language/grade, 40 letters/min row highlighted.
6. **The engine room** (dark band) — six-layer capability stack: Capture apps → Database backbone → Python quality/fidelity scripts → Advanced analytics → AI integrations → Live dashboards, each with monospace tech chips. Replaced v1's four-phase history timeline per Jim's direction.
7. **Mobile apps** (NEW per Jim) — phone frames showing session-log and EGRA-timer UIs. Currently placeholder UI.
8. **AI integrations** (NEW per Jim) — "AI that reads 60 sessions so a mentor doesn't have to": a pre-visit brief card (reads session history, flags un-reviewed letter, spots ability-band split, suggests visit focus). Framing rule: **"humans decide, AI prepares"** — never automated into a classroom.
9. **The dashboards** (NEW per Jim) — real screenshots in browser chrome on the dark band: live operations dashboard + EA performance map. Captions emphasize nightly refresh and coaching-target use.
10. **Kept honest** — QA flags + privacy as prose blocks with example callouts; learning agenda as numbered sidebar (Early start / Model intensity / Government scale).
11. **Explore** — footer link row.

## Open items (Jim)

- Real mobile-app screenshots for section 7 (placeholder UI until then).
- Confirm tech-stack labels in section 6 (TeamPact / SurveyCTO / PostgreSQL / agent tooling naming).
- Confirm the AI pre-visit-brief example is representative and publishable.
- Confirm the two dashboard screenshots are public-safe (no school/EA names visible) or supply donor-safe equivalents.
- Triangle concept approved in principle; design quality bar is "much better than v1" — v2 attempt awaiting Jim's verdict.

## Next steps

When Jim signs off on v2: fold this structure into the parent spec (replacing §4), then write the implementation plan (same pattern as `_plans/2026-06-12-impact-dashboard-implementation-plan.md` — reuse its design tokens, primitives, and taste rules; the radar and Section primitives built for the dashboard are shared components).
