# Impact Dashboard & How We Measure Impact — Design Spec

**Date:** 2026-06-12
**Status:** Approved design, pending implementation plan
**Source material:** `impact-dashboard-me-data-brain-dump.md` (strategy sourcebook)
**Visual reference:** `impact-dashboard-mockup-v5.html` (approved high-fidelity mockup; open in a browser and scroll)
**Audience for the pages:** institutional donors deciding whether Masinyusane is credible, effective, scalable, and worth funding.

---

## 1. Summary

Two new donor-facing pages on the public website:

1. **`/impact/` — Impact Dashboard.** The existing impact page is rebuilt as a curated, editorial evidence experience: "Evidence Brief" style with one cinematic scroll-driven centerpiece (the "classroom lights" sequence). Proves impact.
2. **`/impact/measurement` — How We Measure Impact.** New page. The credibility engine: evidence streams, assessment framework, data infrastructure, quality and privacy. Proves the impact claims can be trusted.

Donor journey: **proof → trust → explore.** `/impact/reports` and `/impact/data-portal` remain unchanged as the deeper layers.

Every number on either page is served from a **published-numbers store** in the Django backend — a hand-approved record with full provenance metadata. Nothing unvetted can reach a donor.

## 2. Decisions made (with rationale)

| Decision | Choice | Rationale |
| --- | --- | --- |
| Page architecture | Rebuild `/impact/` + add `/impact/measurement` | One nav section, clean proof-then-trust journey; reports/portal untouched |
| Coverage | Literacy/numeracy core + context ring | Strongest measured story leads; youth jobs woven in as delivery model; graduates as finale, not co-headline |
| Data strategy | Published-numbers store (hand-approved) | Evidence lives in external systems (portals, TeamPact); sources currently disagree on headline stats; donor claims need editorial sign-off, not pipelines |
| Design direction | Editorial spine + one cinematic moment ("Direction D") | Institutional donors penalize gimmicks but reward memorability; motion is concentrated where the strongest evidence lives |
| Cinematic visualization | Icon-array classrooms (42 children), not bar charts | Count is read pre-attentively, proportion analytically; children-as-units carries the emotional register |
| Headline claims | Hero = "years ahead" (magnitude); cinematic payoff = "doubles in every classroom" (replicability) | The two strongest claims answer different donor questions; each gets the right stage |
| Stories | Braided into evidence pages, not a separate stories page | Standalone story pages go unvisited; one deep story per page at the emotional midpoint, where the story is itself evidence |
| Charts library | Custom SVG/CSS components, **not** Plotly, on these pages | Plotly's bundle (~3 MB) is unjustifiable for a marketing page of simple bars/arrays/radar; custom SVG matches the design language exactly |

## 3. Page 1: `/impact/` — Impact Dashboard

Twelve sections, in scroll order. The approved mockup is authoritative for layout, tone, and copy direction; copy below is the approved working draft, with `[verify]` marking claims that must clear the published-numbers store before launch.

### 3.1 Hero — the magnitude claim
- Kicker: "Our Impact in Data". H1: "Children years ahead, **measured every day**" (gradient on the second clause).
- Subcopy: programmes perform up to two grade levels ahead of comparison groups; measurement system tracks every child, session, skill.
- Four KPI stats `[verify]`: children on programme; schools & ECD centres; local youth employed; assessment & session records.
- "Figures verified <month year>" stamp with link to methodology ("How we count").
- Right side: faint icon-array of children, some lit (foreshadows the cinematic motif). Caption: "every figure is a child we measure."
- Motion: KPI count-up on first view; foreshadow figures flicker subtly.

### 3.2 The Argument — Jim's pitch, on a page
Three-column causal chain on a light band:
1. **81%** of South African 10-year-olds cannot read for meaning (PIRLS 2021) — 10-figure icon array, 8 shaded.
2. **Why?** 73% never learn letter sounds by end of Grade 1 `[verify source]`; letter-sound fluency is the strongest single predictor of becoming a reader (internal correlation ρ = 0.93).
3. **2×** — we double the number of children reaching the letter-sound benchmark in every classroom we enter. "See it happen below ↓"
- Closing line: "So we start at the foundation — **letter sounds, from age four**."

### 3.3 The Cinematic Moment — classroom lights (sticky scroll)
- Dark full-bleed band, ~320vh scroll length, sticky stage.
- Two icon-array classrooms of 42 children (average EC Grade 1 class size `[verify]`). "Reader" = child at the 40 letter-sounds/min Grade 1 benchmark.
- Four beats driven by scroll progress, with step narration on the left:
  1. January: Masi classroom shows **5 of 42** lit.
  2. June: lights up to **22 of 42** (53% midline, 2025) — staggered one-by-one ignition.
  3. Comparison classroom fades in, finishing the full year at **11 of 42** (27%).
  4. Masi room surges to **31 of 42** (74%, 2023 endline) + payoff card: "In every classroom we enter, the number of readers roughly **doubles**."
- Implementation: framer-motion `useScroll` + transforms; **`prefers-reduced-motion` renders the final beat as a static graphic with all four captions visible.**
- Numbers grounded in: 13%→53% (2025 midline), 22%→74% (2023 endline), 27–30% comparison (UTS benchmarks page) `[verify all via store]`.

### 3.4 Chapter: Two Years Ahead (ECD)
- Stat: "2 years ahead". H2: "Our four- and five-year-olds read at Grade 1 level."
- Chart: two horizontal bars, deliberately near-equal — Masi ECD (ages 4–5) **14.9 lcpm** vs Grade 1 comparison (ages 6–7, no programme) **15.4 lcpm** (2026 live data, confirmed by Jim 2026-06-12).
- Gradient chip prevents misreading parity: "**Same fluency — two school years earlier**."
- Claim language is parity ("read at Grade 1 level"), not superiority — 14.9 < 15.4.

### 3.5 Chapter: One Child (Amahle)
- Three-column: consented photo (left), story (middle), radar chart (right).
- Radar: 11 literacy skills (8 in mockup), January polygon in gray, November overlaid in brand gradient.
- Story arc: child's data reveals the gap → coach rebuilds sessions → child reads sentences by November.
- Depth line: "We can draw this chart for any of [N] children — eleven skills, tracked across the year."
- **Hard constraints:** guardian consent workflow for photo + name change (POPIA); face-data pairing reviewed before publication; fallback is an illustrative profile labeled as such.

### 3.6 Chapter: Numeracy
- Stat: average gain out of 90 (Yazi Amanani, matched learners) `[verify]`.
- Grouped baseline-vs-endline bars across the nine components (standardized /10).
- Three threshold cards: count to 20+; identify numbers to 100; write numbers 1–10 `[verify]`.

### 3.7 Chapter: Scale & Model (2008–2026)
- Dark band. H2: "Eighteen years in the same communities."
- Left: **interactive MapLibre map** of all sites (primary schools / ECD centres color-coded), Gqeberha and East London labeled. Aggregate site dots only — school name policy decided pre-launch (see §7).
- Right: vertical timeline, exactly five milestones: 2008 founding → ~2015 jobs model `[Jim to supply real milestone]` → 2023 Zazi iZandi + data system → 2025 scale (100+ schools, 3 languages, government TAs) → 2026 provincial partner.

### 3.8 ECDoE Partnership strip
- Slim, quiet, official: seal mark, "Feature partner to the Eastern Cape Department of Education," MOU signed · weekly sessions with provincial leadership · co-designing province-wide early-grade uplift `[verify wording with Jim/leadership]`.

### 3.9 Chapter: The Long Game (graduates)
- Dark band. H2: "Literacy at six becomes a graduation at twenty-two."
- Copy bridge: hundreds of university graduates from the same communities; **many now lead the programmes measured on this page.**
- Stats: university graduates count; % staff women `[verify both]`. Portrait wall with one featured graduate caption. CTA: "Meet the graduates →" (links to existing scholarship/team content).

### 3.10 How We Know (credibility teaser)
- Three evidence-stream cards: Daily sessions / Formal assessments / Mentor visits, each with a one-line "why it matters."
- CTA button → `/impact/measurement`.

### 3.11 More Results strip
- Four compact cards (demoted, not deleted): zero-letter-knowledge collapse (51%→[N]%); letter-fluency growth multiple vs comparison `[verify]`; 1000 Stories reach `[verify]`; 0.93 correlation between independent assessment methods.

### 3.12 Go Deeper
- Four CTA cards: Live data portal; Zazi iZandi portal; Annual reports; Due-diligence pack (contact/request).
- Page footer: methodology footnote convention (see §5.3).

## 4. Page 2: `/impact/measurement` — How We Measure Impact

Calmer, more structured sibling. Same design system; no cinematic moment. Nav label: "How We Measure Impact"; subtitle "Monitoring, Evaluation & Data". Sections:

1. **Hero.** "We measure learning, not just activity." Support copy: daily sessions, formal assessments, mentor observations, live dashboards.
2. **Three Evidence Streams.** Expanded treatment of the dashboard teaser: what each stream captures, why it matters (table from brain dump). Copy anchor: "If session activity is high but learning gains are low, mentor visit data helps us diagnose the implementation issue behind the number."
3. **Triangulation.** Diagram: three sources validating one another; the 0.93 correlation as measurement-validity evidence.
4. **From Collection to Action.** Horizontal data-cycle diagram: collect → clean → assess → analyze → coach → adapt → report.
5. **Assessment Framework.** Literacy: EGRA letter sounds/min + the 11 tracked skills; improvement metric families (raw, standardized 0–10, % change, learning gain %). Numeracy: the nine Yazi Amanani components. Benchmark definitions by language and grade (40 letters/min Grade 1 isiXhosa, passage-reading benchmarks, etc.).
6. **Benchmark & Research Context.** Eastern Cape starting conditions (zero-letter rates, % reaching benchmark); numeracy crisis context (TIMSS, COVID learning loss). Context follows our results pages, never leads.
7. **Data Infrastructure.** Evolution story: manual exports → API integration → database tables → nightly syncs. Current-year data in production tables powering live dashboards. **"Technical note" accordion** holds the deep detail (TeamPact two-step group resolution, ECD baseline caveats, cross-sectional vs matched analysis) for due-diligence readers.
8. **Quality & Privacy.** QA flag framing ("we flag implementation patterns that may reduce learning quality — moving too fast, undifferentiated groups") positioned as active quality assurance; never per-EA/per-school detail. Privacy: public views are aggregate and anonymized; masking of names/sensitive fields; POPIA compliance.
9. **Learning Agenda.** What Masi tests each year; how pilots (ECD, languages, full-time vs part-time models) feed programme design.
10. **Explore.** Same CTA row as dashboard §3.12.

## 5. Technical architecture

### 5.1 Backend: published-numbers store (Django)

New model in `api/models.py` (single table; keep it simple):

```
PublishedStat
- key              slug, unique (e.g. "children_on_programme", "g1_benchmark_midline_2025")
- value            string as displayed (e.g. "19,444", "53%", "14.9")
- numeric_value    float, nullable (for charts)
- label            short display label
- description      optional longer caption
- source_system    e.g. "ZZ Data Site / midline_primary_2026.py", "PIRLS 2021"
- population       definition of who is counted
- comparison_type  none | comparison_group | control_group | benchmark
- as_of            date the figure was verified
- methodology_note text shown in "How we count" disclosures
- group            grouping key for chart series (e.g. "numeracy_components")
- sort_order       int
- is_published     bool — only published rows are served
```

- **Endpoint:** `GET /api/impact/published-stats/` (`AllowAny`), returns all published rows grouped by `group`. Cached server-side; this data changes rarely and deliberately.
- **Workflow:** stats entered/updated via Django admin. Updating a number is an editorial act with an audit trail (admin history), not a pipeline side effect.
- **Tests:** endpoint contract test in `api/tests.py` (published rows served, unpublished rows excluded, grouping shape).
- Chart series (e.g., nine numeracy components × baseline/endline) are rows sharing a `group`, ordered by `sort_order`. No separate chart model unless this proves insufficient.

### 5.2 Frontend (Next.js)

- **Routes:** rebuild `src/app/impact/page.tsx`; add `src/app/impact/measurement/page.tsx`. Update navbar (Impact section) and any internal links. `/impact/reports`, `/impact/data-portal`, `/impact/annual-report/[year]` unchanged.
- **Rendering model:** **server components fetch published stats at request time with ISR** (`revalidate: 3600`). No client-side data fetching, no loading spinners, no Clerk involvement — these are public pages. Motion sections are client components receiving stats as props.
- **Component structure** (`src/components/impact/dashboard/` and `/measurement/`): one component per section (Hero, ArgumentChain, ClassroomLights, EcdParity, ChildProfile, NumeracySnapshot, ScaleMap, GovPartner, Graduates, HowWeKnow, MoreResults, GoDeeper). Shared primitives: `IconArray`, `KidFigure`, `HBarChart`, `RadarChart` (SVG), `StatChip`, `MethodologyFootnote`.
- **Charts:** custom SVG/CSS (as in mockup). No Plotly import anywhere on these routes.
- **Motion:** framer-motion. ClassroomLights uses `useScroll` against a tall scroll container with a sticky stage; all other sections use the site's existing fade-up pattern. Every animated component has a `prefers-reduced-motion` static fallback showing final state.
- **Map:** existing react-map-gl/MapLibre setup; site coordinates served aggregate-only from the backend (source for coordinates is an open item — see §7).
- **Images:** GCS via `getImageUrl()`; child/graduate photos only after consent clearance.

### 5.3 Claims governance (design feature, not afterthought)

- Every stat rendered on either page **must** come from the published-numbers store and renders with an accessible disclosure (footnote or tooltip) exposing source, population, as-of date, methodology note.
- Wording rule: "comparison group" everywhere unless a randomized design is verified for that specific claim.
- The page footer carries the verification stamp date = max(`as_of`) of displayed stats.

## 6. Error handling & resilience

- Backend endpoint down at revalidation: Next.js serves the last good ISR cache. Build-time fetch failure fails the build loudly (correct behavior — never ship a stats page with empty numbers).
- Missing stat key: component renders nothing rather than a placeholder (a missing section beats "—" on a donor page); logged in development.
- Reduced motion, no-JS, and slow connections all land on meaningful static content (server-rendered HTML carries full final-state markup).

## 7. Open items — pre-launch checklist (not blocking implementation start)

1. Reconcile and publish canonical headline stats: children, schools/ECD centres, youth employed, records count (decide annual vs current-active vs cumulative per stat).
2. Jim: real milestone(s) for the 2008–2022 stretch of the timeline.
3. Jim: confirm ECDoE partnership public wording (MOU, weekly sessions).
4. Verify "73% never learn letter sounds by end of Grade 1" source and exact phrasing (brain dump has 27% reach benchmark / 51% start at zero — related but distinct claims).
5. Confirm average EC Grade 1 class size (42 used in mockup).
6. Child story: select child, obtain guardian consent (photo + data pairing), name change, leadership sign-off.
7. School-name policy on the public map (names vs anonymous dots).
8. Decide whether 2026 treatment/control midline results are public-ready; if not, 2024/2025 results carry v1.
9. Site coordinates source for the map (schools table? geocoding pass?).
10. Final sign-off owner for public claims (suggest: Jim, with data-team verification pass).

## 8. Out of scope (explicitly)

- A separate "Success Stories" page (stories are braided into evidence pages instead).
- Citizen of the Year and other awards (belongs on About, not the evidence pages).
- Embedding or scraping Streamlit portals; raw-record APIs; per-school public rankings; QA-flag detail on public pages.
- Live/auto-syncing dashboard numbers (deliberately rejected in favor of the published-numbers store).

## 9. Implementation phasing (input to the implementation plan)

1. **Backend:** `PublishedStat` model + admin + public endpoint + tests; seed with the verified numbers from §3 (marked rows only).
2. **Dashboard page:** section components against the live endpoint, ClassroomLights last (it's the riskiest); reduced-motion fallbacks.
3. **Measurement page:** structurally simpler; reuses primitives.
4. **Navigation, redirects, SEO/meta, accessibility pass, launch checklist (§7) clearance.**
