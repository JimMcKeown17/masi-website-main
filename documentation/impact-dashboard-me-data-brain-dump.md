# Impact Dashboard and M&E/Data Page Brain Dump

This is a pre-plan research and idea dump for building a curated donor-facing impact dashboard and a separate "world class" M&E/Data page on the Masinyusane website.

Primary audience: an institutional donor visiting the website and deciding whether Masinyusane is credible, effective, scalable, and worth funding.

This is not an implementation plan. It is a strategy sourcebook to pull together the best source material from:

- Current website: `/Users/jimmckeown/Development/Masi_Website_2026/backend/Masi Web Main`
- Masi Data Site: `/Users/jimmckeown/Development/Masi_Data_Site`
- ZZ Data Site: `/Users/jimmckeown/Development/ZZ Data Site`

## Core Thesis

The website should not become another data portal. The public data portals are powerful, but they are built for exploration, operations, and internal/programmatic learning. A donor-facing dashboard should be a curated evidence layer:

- Show the few numbers that make a funder stop and pay attention.
- Explain why those numbers matter in South African education.
- Show that Masinyusane beats benchmarks or control/comparison groups where possible.
- Show that Masinyusane has the data infrastructure to know what is working, catch quality issues, and improve.
- Give donors a confident path into deeper evidence without burying them in sessions pages, cohort tabs, and operational detail.

The M&E/Data page should be the credibility engine behind the dashboard. It should say, in a polished way: "We do not just collect stories. We run a serious measurement system with daily implementation data, formal assessments, mentor observations, privacy controls, quality flags, and live dashboards."

## Current Website Context

The public website already has the right raw positioning:

- `templates/pages/home.html`
  - Hero line: "Local Communities Implementing Data-Driven Literacy & Numeracy Programmes."
  - Home stats currently include `2x`, `400%`, `43%`, `18756`, `316`, `454`, plus youth and graduate stats.
  - The site links users to the data portal but does not curate the strongest results into the website itself.
- `templates/pages/children.html`
  - Strong education narrative: data-driven, Teaching at the Right Level, customized lessons, "dozens of statistics on thousands of children."
  - Existing impact stats: `18,276` children benefiting, `364` community jobs in 2024, `124%` improvement vs control group, `154` schools.
- `templates/pages/impact.html`
  - Currently mostly a report archive.
  - This page can become either:
    - the curated impact dashboard, or
    - a report archive after a new dashboard page is added.
- `templates/pages/data.html`
  - Currently embeds `https://data.masinyusane.org` in an iframe.
  - This is useful for deep exploration, but not ideal as the first donor-facing evidence experience.
- `CLAUDE.md`
  - Backend-first rule: aggregate data server-side rather than shipping raw records to the frontend. This matters for the eventual plan.

Strategic gap: the website says Masinyusane is data-driven, but the donor has to leave the polished website experience and enter the data portal to see proof.

## Source Map

### Masi Data Site

Main navigation source:

- `/Users/jimmckeown/Development/Masi_Data_Site/masi_data_streamlit/main.py`

Public groups include:

- Home
- 2025 Masi Literacy
- 2025 Numeracy
- 2025 Zazi iZandi
- 2024 Zazi iZandi
- 2024 Masi Literacy
- 2023 Zazi iZandi
- Multi-Year

Funder-scoped UTS pages include:

- `side_pages_uts/uts_2026_summary.py`
- `side_pages_uts/uts_summary.py`
- `side_pages_uts/uts_site_level.py`
- `side_pages_uts/uts_youth.py`
- `side_pages_uts/uts_children.py`
- `side_pages_uts/uts_zazi_izandi.py`
- `side_pages_uts/uts_1000_stories.py`
- `side_pages_uts/uts_me_benchmarks.py`

High-value source files:

- `masi_data_streamlit/home.py`
- `masi_data_streamlit/side_pages_uts/uts_summary.py`
- `masi_data_streamlit/side_pages_uts/uts_me_benchmarks.py`
- `masi_data_streamlit/side_pages_25/numeracy_assessments_25.py`
- `masi_data_streamlit/side_pages_25/numeracy_children_25.py`
- `masi_data_streamlit/side_pages_25/numeracy_benchmarks.py`
- `masi_data_streamlit/side_pages_25/site_level_25.py`
- `masi_data_streamlit/side_pages_25/children_25.py`
- `masi_data_streamlit/side_pages_25/zz_2025_midline.py`
- `masi_data_streamlit/data_processing/literacy_data_processing.py`
- `masi_data_streamlit/data_processing/numeracy_data_processing.py`
- `masi_data_streamlit/data_processing/data_privacy.py`
- `masi_data_streamlit/data_processing/data_loader.py`

### ZZ Data Site

Main navigation source:

- `/Users/jimmckeown/Development/ZZ Data Site/main.py`

Public groups include:

- Home
- 2026 Results
- 2025 Results
- 2024 Results
- 2023 Results
- Research & Benchmarks

Internal/login-gated groups include project management, sessions, mentor visits, QA flag pages, letter progress, and AI tools.

High-value source files:

- `new_pages/home_page.py`
- `new_pages/table_of_contents.py`
- `new_pages/Research & Benchmarks.py`
- `new_pages/data_sources.py`
- `docs/DATA_SOURCES_DOCUMENTATION.md`
- `docs/TEAMPACT_API_ASSESSMENT_MAPPING_2026.md`
- `data_privacy.py`
- `new_pages/2023/6_2023 Results.py`
- `new_pages/2024/letter_knowledge_2024.py`
- `new_pages/2024/word_reading_2024.py`
- `new_pages/2025/midline_2025.py`
- `new_pages/2025/ecd_2025.py`
- `new_pages/2025/nmb_endline_cohort_analysis.py`
- `new_pages/2026/baseline_2026.py`
- `new_pages/2026/midline_primary_2026.py`
- `new_pages/2026/ecd_baseline_2026.py`
- `new_pages/2026/ecd_midline_2026.py`

## Donor Narrative

A good institutional donor page needs to answer these questions quickly:

1. Are you reaching enough children and schools to matter?
2. Are children learning?
3. How do results compare to benchmarks or control/comparison groups?
4. Is the implementation model scalable?
5. Can we trust the data?
6. Are you learning and improving, or only reporting?

Suggested narrative spine:

1. "We reach children at scale through local community jobs."
2. "We measure the foundational skills that determine whether a child becomes a reader or numerate learner."
3. "Children on our programmes make measurable gains, and in key cases outperform benchmarks or comparison/control groups."
4. "Our data systems tell us not only whether children improved, but which programmes, schools, coaches, and implementation patterns are driving results."
5. "We use that evidence in real time to improve quality."

## Dashboard Scope Principles

Keep:

- Letters correct per minute.
- Percent of learners hitting grade-level benchmarks.
- Percent or count of zero-letter-knowledge children.
- Matched baseline-to-endline or baseline-to-midline gains.
- Treatment/control or programme/non-programme comparisons.
- Numeracy skill gains and threshold metrics.
- Scale/reach stats.
- A short "how we know" credibility section.
- One or two human-scale child/coach/site examples, anonymized.

Avoid or push deep:

- Sessions analysis as a main-page feature.
- Detailed cohort tabs.
- TA/EA ranking tables.
- Raw export tables.
- Quality flag detail pages.
- Overly granular school-by-school operational comparisons.
- Too many filters.

Donor-facing rule: each section should either prove impact, explain credibility, or invite deeper due diligence.

## Impact Dashboard Concept

### Working Page Title Ideas

- Impact Dashboard
- Our Impact in Data
- Evidence of Impact
- Learning Outcomes Dashboard
- Results That Matter
- Data-Driven Impact

Best recommendation: "Impact Dashboard" or "Our Impact in Data". Keep the title plain and credible.

### First View

First viewport should answer:

- What is Masinyusane?
- What scale has it reached?
- What proof point should a donor remember?

Potential hero line:

> Local communities delivering measurable literacy and numeracy gains.

Potential support copy:

> We combine community job creation with rigorous learning measurement: daily session data, formal EGRA assessments, mentor observations, and live dashboards that help us improve instruction child by child, school by school.

Potential headline stats:

- Children reached/on programme:
  - Current website: `18,276` or `18,756` children in 2024, depending page.
  - Masi Data Site `home.py`: `19,444` children on programme.
  - ZZ Data Site `home_page.py`: `25,000+` children taught.
  - Need reconcile before publishing.
- Schools:
  - Current children page: `154` schools.
  - Masi Data Site home: `231` schools.
  - ZZ Data Site home: `250+` schools reached.
  - Need reconcile before publishing.
- Youth/community jobs:
  - Current home: `316` community jobs.
  - Current children page: `364` community jobs in 2024.
  - Masi Data Site home: `515` youth employed.
  - ZZ Data Site home: `500+` youth jobs.
  - Need decide whether to use current active jobs, annual jobs, or cumulative jobs.
- University graduates:
  - Current home: `454` university graduates.
  - Could stay elsewhere; not central to children's literacy/numeracy dashboard unless the dashboard covers all Masi impact.

Important: the current site and portals disagree slightly on headline scale stats. This is normal because they likely use different scopes and dates, but the public dashboard must choose one definition per stat.

### Suggested Dashboard Sections

1. Outcome Snapshot
2. Literacy Results
3. Numeracy Results
4. Scale and Reach
5. How We Know
6. Explore More

Alternative section order:

1. At a Glance
2. Children Learn Faster
3. More Children Reach Grade Level
4. Zero-Letter Knowledge Falls
5. Numeracy Foundations Improve
6. The Data System Behind the Results
7. Reports and Data Portals

## Candidate Impact Widgets

### 1. At-a-Glance KPI Strip

Purpose: scale and seriousness.

Potential cards:

- Children taught/reached.
- Schools/ECD centers reached.
- Community youth employed.
- Children in small customized literacy/numeracy sessions.
- Assessment records collected.
- Daily sessions logged.
- Mentor visits completed.

Source candidates:

- Website `templates/pages/home.html`
- Website `templates/pages/children.html`
- Masi `home.py`
- ZZ `new_pages/home_page.py`
- UTS `uts_summary.py`
- ZZ `docs/DATA_SOURCES_DOCUMENTATION.md`

Suggestions:

- Use at most 4 headline cards.
- Put source definitions in a small "How this is counted" disclosure or footnote.
- Avoid mixing annual, current-active, and cumulative stats without labels.

### 2. Grade 1 Benchmark Movement

Purpose: strongest literacy proof point.

Core benchmark:

- Grade 1 letter knowledge benchmark: `40 letters per minute`.
- This appears in:
  - Masi `side_pages_uts/uts_me_benchmarks.py`
  - ZZ `new_pages/Research & Benchmarks.py`

Candidate evidence:

- Masi UTS benchmark chart:
  - Masi ZZ isiXhosa: `74%`
  - Masi Core English: `54%`
  - Control Group English: `30%`
  - Control Group isiXhosa: `27%`
  - Source: `masi_data_streamlit/side_pages_uts/uts_me_benchmarks.py`
- 2025 Zazi midline:
  - Grade 1 on-grade-level letter knowledge increased from `13%` to `53%`.
  - Source: `masi_data_streamlit/side_pages_25/zz_2025_midline.py`
- ZZ 2023 pilot:
  - Grade 1 on-grade-level movement from `22%` to `74%`.
  - Source: `ZZ Data Site/new_pages/2023/6_2023 Results.py`
- ZZ 2024:
  - Grade 1 benchmark movement from `13%` to `53%`.
  - Source: `ZZ Data Site/new_pages/2024/letter_knowledge_2024.py`

Suggested display:

- Big two-bar chart: baseline vs endline/midline.
- Add a horizontal benchmark/reference line if showing percent benchmark.
- Add short caption: "Grade 1 benchmark = 40 letter sounds per minute."
- Consider a second bar group for comparison/control if using the UTS hardcoded rates.

Potential donor headline:

> More children cross the Grade 1 reading-readiness benchmark.

### 3. Letters Correct Per Minute

Purpose: show an objective, assessment-based literacy metric.

Source candidates:

- ZZ 2025 midline letter EGRA improvement: `zz_2025_midline.py`
- ZZ 2024 letter knowledge page: `new_pages/2024/letter_knowledge_2024.py`
- ZZ 2026 midline primary page: `new_pages/2026/midline_primary_2026.py`
- Masi/UTS Zazi page: `side_pages_uts/uts_zazi_izandi.py`

Chart ideas:

- Baseline vs midline/endline average letters correct per minute by grade.
- Distribution chart showing movement from low scores to higher scores.
- Small multiple by grade/language.
- A "what this means" explainer: one-minute EGRA letter task is a fast early reading indicator.

Avoid:

- Showing every school and every grade in the first pass.
- Showing too many language splits unless the story needs it.

### 4. Zero-Letter Knowledge

Purpose: highly intuitive poverty/learning-gap and progress metric.

National context:

- Wordworks context in Masi and ZZ research pages:
  - `51%` of Eastern Cape Grade 1 children knew zero letter sounds at the start of the year.
  - Only `27%` hit the Grade 1 benchmark of 40 letters per minute.

Portal source candidates:

- ZZ 2024: `new_pages/2024/letter_knowledge_2024.py`
- ZZ 2025 ECD: `new_pages/2025/ecd_2025.py`
- ZZ 2026 baseline: `new_pages/2026/baseline_2026.py`
- ZZ 2026 midline primary: `new_pages/2026/midline_primary_2026.py`

Suggested display:

- Baseline vs midline/endline: count and percent of children with zero known letters.
- Title: "Fewer children left with zero letter knowledge."
- Could combine with a positive counterpart: "% who know all/some letters."

This is one of the most donor-friendly metrics because it is understandable without assessment jargon.

### 5. Treatment vs Control / Programme vs Non-Programme

Purpose: credibility. Institutional donors want more than before/after charts.

Strong source candidates:

- Masi `site_level_25.py`
  - Programme Impact Analysis compares children on programme vs not on programme.
  - Supports raw score improvement, standardized improvement, learning gain, percentage of maximum possible, and simple percent change.
  - Has November score comparisons and skill-category comparisons by programme status.
- Masi `uts_me_benchmarks.py`
  - Hardcoded benchmark comparison: Masi ZZ/Masi Core vs control groups.
- ZZ `new_pages/2026/midline_primary_2026.py`
  - Treatment/control section via `render_treatment_vs_control_section()`.
  - Uses matched learners and baseline-school anchoring.
  - Includes matched counts, average letter gain by grade, word gain, benchmark movement, and gain distributions.

Suggested display:

- One clean "Programme vs comparison" bar chart.
- One compact stat: "Children on programme improved X more than comparison children."
- If using 2026 treatment/control, note matched learners and baseline-to-midline design.

Caution:

- Do not overclaim causal proof if the comparison is not randomized.
- Label as "control", "comparison", or "not on programme" according to actual source.
- Make cohort/school matching methodology explicit in the M&E/Data page or a tooltip.

### 6. Literacy Skills Radar / Child Profile

Purpose: show Teaching at the Right Level and individualized diagnosis.

Source candidates:

- Masi `home.py`
  - Radar chart of child-level November skill scores.
- Masi `children_25.py`
  - Child impact profile with Jan/Nov radar, raw gain, weighted gain, sessions, and skills snapshot.

Suggested display:

- Use one anonymized child story or interactive example:
  - "Child A: from X to Y across letter sounds, reading, writing."
  - Radar chart or compact skill table.
- Keep as a secondary section, not the main proof.

Why this matters:

- It demonstrates that Masinyusane does not only track aggregate impact; it can diagnose child-level needs.

### 7. Literacy System Improvement / Correlation Proof

Purpose: show data sophistication without overwhelming.

Source candidates:

- Masi `home.py`
  - Correlation heatmap of November scores across literacy metrics.
- ZZ `Research & Benchmarks.py`
  - Strong correlation between Letters Known and EGRA improvement, Spearman coefficient `0.933`.

Suggested display:

- A small "Why we trust the measures" panel:
  - "Two independent assessment methods move together."
  - Mention correlation as evidence of measurement validity.
- Do not put a giant heatmap in the primary donor dashboard unless the page has an "Evidence methods" section.

### 8. Numeracy Outcome Snapshot

Purpose: user likes numeracy stats and wants "all the stats", but dashboard still needs to be digestible.

Primary source:

- Masi `side_pages_25/numeracy_assessments_25.py`

What exists:

- Yazi Amanani baseline vs endline results.
- Scores standardized so each question is worth 10 points; total max is 90.
- Match stats:
  - Total learners.
  - Both assessments.
  - Baseline only.
  - Endline only.
  - Match rate.
- Overall improvement:
  - Learners tracked.
  - Average baseline score out of 90.
  - Average endline score out of 90.
  - Average improvement.
- Skill-level chart:
  - Baseline vs endline by component, standardized to `/10`.
  - Average improvement by component.
- Threshold stories:
  - Children who can count to `20+`.
  - Children who can identify numbers to `100`.
  - Children who can write numbers `1-10`.
- Disaggregations:
  - Improvement by gender.
  - Improvement by school.
  - Improvement per numeracy coach.
  - Detailed component analysis by school.

Assessment components from `numeracy_data_processing.py`:

- Counting Aloud.
- Number Recognition.
- Counting and Matching.
- Write Numbers.
- More Than / Less Than.
- Missing Numbers.
- Sums to 10.
- Word Problems.
- Addition/Subtraction.

Suggested dashboard display:

- Put a "Numeracy at a glance" mini-dashboard with:
  - Average score gain out of 90.
  - One grouped bar chart: baseline vs endline across the nine components.
  - Three threshold cards:
    - Count to 20+.
    - Identify numbers to 100.
    - Write numbers 1-10.
  - Optional school/coach drill-down only behind an expander or a separate "explore" link.

Donor headline ideas:

- "Foundational numeracy improves across every core skill."
- "Children gain measurable number sense, not just test points."
- "We track concrete numeracy milestones donors can understand."

Caution:

- Numeracy evidence came from Masi Data Site, not ZZ Data Site. The ZZ Data Site does not have substantive numeracy dashboards.

### 9. Numeracy Context

Source:

- Masi `side_pages_25/numeracy_benchmarks.py`

Possible context points:

- More than `50%` of South African Grade 1 learners cannot add or subtract single-digit numbers.
- TIMSS 2019:
  - `61%` of Grade 5 learners could not perform a basic multiplication problem.
  - `75%` failed a Grade 3-level subtraction problem.
- Learners are estimated to have lost about `80%` of a year of learning post-COVID, with early-grade mathematics hit hardest.
- Language matters; Masinyusane teaches numeracy in isiXhosa or home language where appropriate.

Suggested use:

- Include as a short "Why numeracy matters" context panel.
- Do not lead with national crisis stats before showing Masi's own results.

### 10. 1000 Stories / Reading Activity

Purpose: broaden the child-development story without turning dashboard into everything.

Source:

- Masi `side_pages_uts/uts_summary.py`
- Masi `side_pages_uts/uts_1000_stories.py`

Existing UTS summary includes:

- Total stories read, recorded.
- Reading sessions, recorded.
- Reach estimates.

Suggested display:

- One supporting card or sidebar:
  - "Stories heard/read" and "reading sessions".
  - Position as early language exposure, not the primary learning-outcome proof.

### 11. Youth Jobs and Local Implementation

Purpose: show model distinction. Masinyusane is not only an education intervention; it hires and trains local youth to deliver it.

Current website stats:

- Home: `316` community jobs.
- Youth page narrative: over `350` local youth running one-on-two literacy sessions across four primary schools.
- About page: `95%` employees female.
- Donate page partner logos.

Portal stats:

- Masi Data Site `home.py`: `515` youth employed.
- ZZ Data Site `home_page.py`: `500+` youth jobs.
- UTS `uts_summary.py`: youth currently employed and total youth jobs created at UTS sites over past 5 years.

Suggested display:

- "Local youth delivering measurable learning gains."
- Cards:
  - Youth employed.
  - Percent women if verified/current.
  - Training/mentor support model.
  - Children reached per youth coach or session model.

Caution:

- Reconcile active/current/cumulative job counts before publishing.

### 12. Scale Timeline

Purpose: show momentum and learning.

Source:

- ZZ `new_pages/table_of_contents.py`

Existing program evolution:

- 2023 pilot launch:
  - 12 schools.
  - 52 youth.
  - 1,897 children.
- 2024 expansion:
  - Cohort 1: 16 schools, 82 youth, 3,490 children.
  - Cohort 2: 6 schools, 28 youth, 1,134 children.
  - Introduced ZZ 2.0 blending/word reading and first ECD center pilot.
- 2025 scale and diversification:
  - SEF youth: 42 schools, 73 part-time TAs.
  - Government TAs NMB: 460 trained, 30-40% uptake.
  - East London: 50 schools, one-month foundation.
  - ECD year-long: 16 centers, 353 children.
  - Three languages, SurveyCTO and TeamPact tools, full-time vs part-time models.

Suggested display:

- Horizontal timeline or compact "how the model scaled" section.
- Keep it simple:
  - Pilot.
  - Expansion.
  - Government partnership.
  - Live data system.

## M&E/Data Page Concept

### Working Page Title Ideas

- Monitoring, Evaluation & Data
- Our Data System
- How We Measure Impact
- Evidence & Learning
- Data-Driven Programmes
- Measuring What Matters

Best recommendation: "How We Measure Impact" for public readability, with "Monitoring, Evaluation & Data" as the subtitle or nav label.

### Page Purpose

The M&E/Data page should make Masinyusane feel unusually rigorous for the nonprofit sector. It should not look like a technical database manual, but it should make technical competence obvious.

Primary messages:

- We collect multiple kinds of evidence.
- We triangulate implementation and outcome data.
- We run formal assessments at baseline/midline/endline.
- We monitor quality through mentor visits and data flags.
- We protect child privacy.
- We use data to improve programmes, not only report to donors.
- Our data infrastructure has matured from manual files to API/database-backed systems.

### Suggested M&E/Data Page Structure

1. Hero
   - Headline: "We measure learning, not just activity."
   - Support: "Daily sessions, formal assessments, mentor observations, and live dashboards help us know what children are learning and where our programmes need to improve."
2. Three Evidence Streams
   - Daily sessions.
   - EGRA assessments.
   - Mentor visits.
3. Triangulation
   - How sources validate one another.
4. From Collection to Action
   - Data cycle: collect, clean, assess, analyze, coach, adapt, report.
5. Assessment Framework
   - Literacy and numeracy skills measured.
   - Benchmark definitions.
6. Data Infrastructure
   - Streamlit portals, database tables, nightly syncs, API integration, Parquet optimization.
7. Quality and Privacy
   - Masking, public vs internal views, QA flags.
8. Learning Agenda
   - What Masi tests each year and how pilots improve.
9. Explore
   - Links to Data Portal, Zazi Data Portal, annual reports.

### Three Evidence Streams

This language already exists in both portals and should become central website copy.

Evidence stream table:

| Stream | What it captures | Why it matters |
| --- | --- | --- |
| Daily sessions | Letters/skills taught, groups, attendance, session duration | Shows implementation dosage and whether children are receiving instruction |
| EGRA assessments | Baseline, midline, endline literacy outcomes, including letters correct per minute and word/nonword fluency | Shows whether children are actually learning |
| Mentor visits | Implementation quality, coach performance, school context, qualitative feedback, action items | Explains why results are high or low and drives support |

Source:

- Masi `side_pages_uts/uts_me_benchmarks.py`
- ZZ `new_pages/table_of_contents.py`

Possible donor copy:

> We triangulate daily session logs, formal learning assessments, and mentor observations. If session activity is high but learning gains are low, mentor visit data helps us diagnose the implementation issue behind the number.

### Assessment Framework

Literacy:

- EGRA letter sounds correct per minute.
- Letter knowledge.
- Word reading.
- Nonword reading.
- Passage reading where relevant.
- Writing and comprehension in Masi Core literacy.

Masi literacy skills tracked in 2025 processing:

- Letter Sounds.
- Story Comprehension.
- Listen First Sound.
- Listen Words.
- Writing Letters.
- Read Words.
- Read Sentences.
- Read Story.
- Write CVCs.
- Write Sentences.
- Write Story.

Masi improvement metric families:

- Raw Points Gained.
- Standardized Gain (0-10).
- Percent Change.
- Learning Gain Percent.

Source:

- `masi_data_streamlit/data_processing/NEW_METRICS_SUMMARY.md`
- `masi_data_streamlit/data_processing/literacy_data_processing.py`

Numeracy:

- Counting Aloud.
- Number Recognition.
- Counting and Matching.
- Write Numbers.
- More Than / Less Than.
- Missing Numbers.
- Sums to 10.
- Word Problems.
- Addition/Subtraction.

Source:

- `masi_data_streamlit/data_processing/numeracy_data_processing.py`

### Benchmark Context

Use benchmarks to explain why "40 letters per minute" matters.

Literacy benchmarks:

- isiXhosa Grade 1 letter knowledge: 40 letters per minute.
- isiXhosa Grade 2 passage reading: 20 words per minute.
- isiXhosa Grade 3 passage reading: 35 words per minute.
- English Grade 2 passage reading: 30 words per minute.
- English Grade 3 passage reading: 50 words per minute.
- English Grade 4 passage reading: 70 words per minute.

Research context:

- Only 27% of Eastern Cape Grade 1 children hit the 40 letters per minute benchmark by end of year.
- 51% of Eastern Cape Grade 1 children knew zero letter sounds at the start of the year.
- Fewer than 50% of South African learners in no-fee schools know all letters by end Grade 1.
- Alphabetic illiteracy in Grade 1 can put children years behind.

Source:

- Masi `side_pages_uts/uts_me_benchmarks.py`
- ZZ `new_pages/Research & Benchmarks.py`

### Data Infrastructure Story

Strong M&E page content from ZZ `docs/DATA_SOURCES_DOCUMENTATION.md`:

Evolution:

- Phase 1: manual CSV/Excel exports.
- Phase 2: TeamPact API integration.
- Phase 3: database integration.
- Phase 4: performance optimization with Parquet.

Current best practices:

- 2026 assessment data uses database tables `assessments_2026` and `assessment_cells_2026`.
- 2026 session data uses `sessions_2026`.
- 2026 mentor visits use `mentor_visits_2026`.
- 2025 session data uses `teampact_sessions_complete`.
- Historical 2023/2024 data uses Parquet with Excel fallback.

Summary stats from docs:

- 9 database tables used.
- 15+ data loading functions.
- 13+ pages using database.
- 11 pages using CSV/Excel.
- Nightly auto-updates for key current data sources.

Suggested public copy:

> Our data systems have evolved from manual exports to automated API and database pipelines. Current-year assessment, session, and mentor-visit data are synced into production tables and power live dashboards for programme management.

### TeamPact 2026 Sync Complexity

This is not donor-front-page material, but it is excellent for a technical credibility subsection or due-diligence note.

From ZZ docs:

- 2026 assessments are synced from TeamPact API.
- Primary surveys require a two-step process:
  - Survey response provides `group_id`.
  - `GET /groups/{id}` resolves `class_name` and `program_name`.
  - Grade is derived from `class_name`.
  - Primary midline rows can fall back to learner baseline grade when group name is a letter-group label.
- ECD baseline has caveats:
  - Baseline survey had no participant IDs.
  - ECD midline comparison is cross-sectional, not matched learner analysis.

Source:

- `ZZ Data Site/docs/TEAMPACT_API_ASSESSMENT_MAPPING_2026.md`
- `ZZ Data Site/docs/DATA_SOURCES_DOCUMENTATION.md`

Suggestion:

- Put this level of detail behind "Technical note" or "Data methodology".
- It helps with institutional donors who ask hard questions, but should not dominate the public page.

### Data Quality and QA Flags

Sources:

- ZZ `docs/DATA_SOURCES_DOCUMENTATION.md`
- ZZ 2026 project management pages.
- Masi and ZZ quality flag analysis in 2025/2026 pages.

Existing QA flags:

- Moving Too Fast:
  - More than 70% of session-to-session transitions introduce only new letters with zero overlap/review.
  - Indicates an EA may be advancing learners too quickly.
- Same Letter Groups:
  - 3+ groups under the same EA are at the exact same letter progress index.
  - Indicates lack of differentiation or possible data entry/implementation issue.

Suggested public framing:

> We do not only track whether sessions happened. We flag implementation patterns that may reduce learning quality, such as moving through letters too quickly or failing to differentiate groups by ability.

Use this carefully:

- Donors like quality systems.
- Avoid making it sound like failures are widespread.
- Frame as active quality assurance.

### Privacy and Public/Internal Views

Sources:

- Masi `data_processing/data_privacy.py`
- ZZ `data_privacy.py`
- Masi `main.py`
- ZZ `main.py`

Existing behavior:

- Public/logged-out views mask child, staff, mentor, school, class, group, and high-risk free-text fields.
- Logged-in/internal users can access detailed names and operational views.
- Some feeds are explicitly internal-only unless masking is added.

Suggested public copy:

> Public dashboards show aggregate and anonymized results. Names and sensitive fields are masked in unauthenticated views, while internal teams use secure detailed views for programme management and child support.

Important for implementation:

- Website dashboard should use aggregate data only.
- Avoid raw child or staff records.
- If school-level data is public, confirm masking/permissions and donor strategy.

### AI/Data Analysis Capability

Existing tools:

- MasiAnalyze in Masi Data Site `agent2/agent_w_tools_v2.py`.
- Zazi Bot / coach assistant in ZZ Data Site.
- Literacy coach mentor agent in ZZ Data Site.

Suggested positioning:

- Do not lead with "AI" unless it serves the credibility story.
- Better framing:
  - "Internal analysis tools help staff ask questions of the data."
  - "Mentor dashboards and analysis assistants help identify where support is needed."
- Avoid donor-facing hype.

## Page and Design Suggestions

### General Design Direction

The audience is institutional donors, so the page should feel:

- Credible.
- Calm.
- Evidence-rich.
- Polished.
- Easy to scan.
- Not gimmicky.

Avoid:

- Dense data portal UI.
- Too many tabs.
- Repeating every chart from Streamlit.
- Huge interactive filter panels.
- Internal operational language.
- Overclaiming causality.

Use:

- Strong typography.
- Tight chart captions.
- Source/method footnotes.
- Clean cards for headline stats.
- A few high-quality charts.
- Links to deeper portals/reports.
- "Methodology" disclosures near claims.

### Suggested Visual Components

- KPI cards for scale.
- Horizontal benchmark bars.
- Baseline vs endline grouped bars.
- Small multiples by grade.
- Threshold cards for numeracy.
- Before/after distribution for letters known.
- One "data system" process diagram.
- One source triad graphic: sessions, assessments, mentor visits.
- One methodology accordion for technical details.
- One CTA row:
  - View Data Portal.
  - View Zazi iZandi Portal.
  - Download Annual Report.
  - Contact us for due diligence pack.

### Dashboard Should Have Two Depth Levels

Level 1: public skim view

- 4 headline stats.
- 3 charts.
- 3 short proof statements.
- M&E credibility teaser.

Level 2: donor due diligence view

- Methodology notes.
- Data-source table.
- Benchmark context.
- More charts from portals.
- Links to full portals and reports.

## Recommended "Most Impressive" Shortlist

If the dashboard only had 6 proof modules, use these:

1. Scale
   - Children taught/reached, schools, youth jobs.
2. Grade 1 benchmark achievement
   - Baseline vs endline/midline, 40 letters/minute benchmark.
3. Control/comparison proof
   - Masi ZZ/Masi Core vs control groups, or 2026 treatment/control matched gains.
4. Zero-letter knowledge reduction
   - Show children moving from zero letter knowledge to measurable skill.
5. Numeracy foundations
   - Average score gain out of 90 plus count-to-20, identify-to-100, write-1-to-10 thresholds.
6. Measurement system
   - Daily sessions + EGRA + mentor visits + privacy + QA flags.

## Possible Copy Blocks

### Dashboard Intro

Masinyusane combines community-led implementation with rigorous learning measurement. Our youth coaches deliver literacy and numeracy support in schools and ECD centers, while our data systems track whether children are actually learning: daily sessions, formal assessments, mentor observations, and benchmark comparisons.

### Literacy Benchmark

In early-grade literacy, one of the clearest indicators is whether Grade 1 learners can correctly sound 40 letters per minute. This benchmark is strongly linked to whether a child is on track to become a reader. Our dashboards track how many children cross that threshold, how many begin with zero letter knowledge, and how programme learners compare with peers not receiving the same support.

### Numeracy

Foundational numeracy is measured through concrete skills: counting aloud, recognizing numbers, writing numbers, solving missing-number problems, and basic addition/subtraction. We standardize each skill area so progress can be compared fairly across the assessment.

### M&E

Our monitoring and evaluation system combines three sources: daily session logs, formal learning assessments, and mentor observations. Together, they show not only whether children improved, but what kind of instruction they received and where implementation quality needs support.

### Data Credibility

Public dashboards show aggregate and anonymized results. Internal teams use more detailed protected views to manage programmes, coach staff, and identify children or sites needing additional support.

## Data and Claim Cautions

Before publishing any exact number:

- Reconcile child reach stats across website, Masi Data Site, and ZZ Data Site.
- Decide whether "children reached" means annual unique children, current active children, cumulative children, or programme-specific children.
- Reconcile youth jobs:
  - active now,
  - current year,
  - cumulative jobs created,
  - UTS-site-only jobs.
- Reconcile schools:
  - active schools,
  - schools reached historically,
  - schools by programme,
  - ECD centers vs primary schools.
- Confirm whether 2026 midline treatment/control results are ready for public use.
- Confirm whether school names should be public on the website.
- Confirm exact benchmark definitions by language and grade.
- Avoid using "control group" if the design is actually a comparison group or non-programme group.
- Label ECD 2026 midline as cross-sectional if used; do not imply matched learner gains.
- Do not surface internal QA flags by EA or school on a public donor page.

## Implementation Notes for a Future Plan

Likely best implementation pattern:

- Do not embed the entire Streamlit pages into the dashboard.
- Do not scrape Streamlit HTML.
- Create curated aggregate data sources:
  - static JSON snapshots exported from portal processing code, or
  - Django API endpoints that aggregate from the website backend database, or
  - a scheduled data build that writes donor-safe aggregates.
- Keep frontend payloads aggregate-only.
- Include source/methodology metadata with each stat.
- Use chart components that match the website style, not Streamlit defaults.

Potential output data model:

- `impact_headline_stats`
- `literacy_benchmark_results`
- `literacy_zero_letter_results`
- `literacy_comparison_results`
- `numeracy_overall_results`
- `numeracy_threshold_results`
- `me_data_sources`
- `me_quality_controls`

Potential chart metadata fields:

- title
- subtitle
- source_portal
- source_file
- data_updated_at
- population
- comparison_type
- caveat
- public_safe

## Suggested Donor-Facing Navigation

Option A:

- `/impact/` becomes curated impact dashboard.
- `/data/` becomes M&E/Data page with portal links.
- Existing report archive moves lower on `/impact/` or to `/reports/`.

Option B:

- `/impact/` remains reports plus high-level stats.
- Add `/impact-dashboard/` for charts.
- Add `/data/` as M&E/Data page, with portal iframe moved to "Explore the portal."

Option C:

- Add one combined `/evidence/` page:
  - top: dashboard.
  - bottom: M&E/data methodology.
  - links to portals.

Recommendation for planning:

- Use two pages:
  - Impact Dashboard: results.
  - How We Measure Impact: M&E/data credibility.

This keeps the donor journey clean: first proof, then trust.

## Questions for the End

1. What should the canonical headline numbers be for children reached, schools reached, and youth jobs: current active, annual, or cumulative?
2. Should the dashboard cover all Masinyusane impact, or focus specifically on children's literacy/numeracy?
3. Are school names allowed on the public website, or should all school-level data be anonymized/aggregated?
4. Are 2026 treatment/control results ready for public donor use, or should the first version use 2024/2025 results only?
5. Should "control group" be the public wording, or should we use "comparison group" unless a true control design exists?
6. Should numeracy be a compact section on the impact dashboard or a richer subpage?
7. Should the current `/data/` iframe remain, move lower, or be replaced by a polished M&E/Data page with links out to the portals?
8. Do institutional donors need downloadable CSV/PDF evidence packs, or is linking to annual reports and data portals enough?
9. Should the donor dashboard use live data, periodically exported snapshots, or hand-approved published numbers?
10. Who owns final sign-off on public claims: data team, programme team, leadership, or donor reporting?

