# Impact Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the donor-facing Impact Dashboard: a `PublishedStat` store + public API in the Django backend, and a rebuilt `/impact/` page in the Next.js frontend matching the approved v5 mockup exactly.

**Architecture:** Hand-approved stats live in one Django table served by one cached public endpoint. The Next.js page is a server component fetching with ISR (revalidate 3600); only motion-bearing sections are client components. All charts are custom SVG/CSS — Plotly is banned on this route.

**Tech Stack:** Django 5.1 + DRF (backend repo), Next.js 16 App Router + React 19 + Tailwind v4 + framer-motion 12 (frontend repo).

**Spec:** `documentation/2026-06-12-impact-dashboard-and-measurement-design.md` (backend repo)
**Visual source of truth:** `documentation/impact-dashboard-mockup-v5.html` — **open this file in a browser and scroll it before writing any frontend code.** When this plan and your instincts disagree, the mockup wins. The `/impact/measurement` page is OUT OF SCOPE (separate spec in progress).

---

## 0. Executor briefing — read first

**Two separate git repos.** Commit backend work in `/Users/jimmckeown/Development/Masi_Website_2026/backend/Masi Web Main/` and frontend work in `/Users/jimmckeown/Development/Masi_Website_2026/frontend/masi-website/`. The parent directory is a third repo — do not commit there. Always `cd` to the right repo before `git` commands.

**Backend commands** (always activate venv first):
```bash
cd "/Users/jimmckeown/Development/Masi_Website_2026/backend/Masi Web Main"
source venv/bin/activate
python manage.py test api          # tests
python manage.py runserver         # http://localhost:8000
```
`.env` points at local Postgres. Never run `prod_manage.sh` in this plan.

**Frontend commands:**
```bash
cd /Users/jimmckeown/Development/Masi_Website_2026/frontend/masi-website
pnpm dev      # http://localhost:3000
pnpm lint && pnpm build   # the frontend has no unit-test runner; lint+build is the gate
```
Check `.env.local` for `NEXT_PUBLIC_API_URL` (expected `http://localhost:8000/api`). The backend must be running for the page to show numbers in dev.

**Files to read before starting (orientation, ~10 min):**
- Backend: `api/models.py` (skim model style), `api/views/info.py`, `api/views/__init__.py`, `api/urls.py`, `api/admin.py` (first 60 lines), `api/tests.py`
- Frontend: `src/app/impact/page.tsx` (being replaced), `src/components/animations/FadeAnimations.tsx`, `src/app/globals.css`, `src/app/layout.tsx`, `src/components/layout/Footer.tsx` (import path only)

### Design taste rules (non-negotiable — this is why the plan is prescriptive)

1. **No emojis anywhere** (repo rule). The mockup's three emoji icons in "How We Know" are replaced by `lucide-react` icons named in Task 12.
2. **No Plotly imports** on this route. All charts are the SVG/CSS components defined in this plan.
3. **Exact colors only.** Dark band is `#0c0f1d` (not gray-900, not slate-950). Amber lights are `#fbbf24`. Gradient is always `from-blue-600 via-purple-600 to-rose-600`. Do not introduce any color not listed in §0.1.
4. **Do not center body text.** Headlines and copy are left-aligned except section 10 ("How We Know"), which is the page's single centered section.
5. **Do not add decoration.** No extra icons, badges, dividers, or cards beyond what each task specifies. Restraint is the aesthetic.
6. **Spacing rhythm is fixed:** every section uses the `Section` shell from Task 6. Never hand-roll section padding.
7. **Motion:** durations 0.5–1.0s, easing `cubic-bezier(0.2, 0.8, 0.2, 1)` (or framer spring defaults), `viewport={{ once: true }}` for fade-ups, and every animated component must render its final state when `prefers-reduced-motion` is set.
8. **Typography hierarchy** comes from §0.1 type scale. Never use a font size not in the scale.

### 0.1 Design tokens (Tailwind classes, used verbatim)

| Token | Value |
| --- | --- |
| Page container | `mx-auto max-w-[1180px] px-6 md:px-12 lg:px-20` |
| Section vertical | `py-20 md:py-24` |
| Dark band bg | `bg-[#0c0f1d] text-white` |
| Light band bg | `bg-slate-50 border-y border-slate-100` |
| Warm band bg (child story) | `bg-gradient-to-b from-white via-orange-50/40 to-white` |
| Gov band bg | `bg-[#f4f7fb] border-y border-[#e3eaf3]` |
| Ink / body / muted | `text-gray-900` / `text-gray-600` / `text-gray-400` |
| Dark-band body / muted | `text-gray-400` / `text-gray-500` |
| Kicker | `text-xs font-semibold uppercase tracking-[3px] text-gray-400` |
| Hero H1 | `text-5xl md:text-6xl lg:text-[66px] font-extrabold leading-[1.05] tracking-tight text-gray-900` |
| Section H2 (dark or light) | `text-3xl md:text-[38px] font-extrabold tracking-tight leading-[1.15]` |
| Chapter stat numeral | `text-6xl md:text-7xl font-extrabold tracking-tighter leading-none` |
| KPI numeral | `text-4xl font-extrabold tracking-tight` |
| Gradient text | `bg-gradient-to-r from-blue-600 via-purple-600 to-rose-600 bg-clip-text text-transparent` |
| Gradient rule | `my-5 h-[3px] w-[90px] bg-gradient-to-r from-blue-600 to-rose-600` |
| Panel | `rounded-2xl border border-gray-200 bg-white p-7 shadow-[0_8px_30px_rgba(17,24,39,0.05)]` |
| Dark panel | `rounded-2xl border border-white/10 bg-white/[0.04]` |
| Footnote text | `text-[12.5px] text-gray-400` |
| Amber (lit child) | `#fbbf24`, glow `drop-shadow(0 0 7px rgba(251,191,36,0.75))` |
| Unlit child (dark bands) | `#2a2f45` |
| Unlit child (light bands) | `#cbd5e1`; shaded variant `#334155` |

### 0.2 Component → stat-key contract

Every number rendered on the page comes from the published-stats payload by `key`. If a key is missing, the component renders that element as nothing (no dash, no zero). Keys are defined in the Task 4 seed and listed per component task.

---

## File structure

**Backend (create/modify):**
- Modify `api/models.py` — append `PublishedStat`
- Modify `api/admin.py` — register `PublishedStatAdmin`
- Create `api/views/impact.py` — `published_stats` view
- Modify `api/views/__init__.py`, `api/urls.py`
- Create `api/management/commands/seed_published_stats.py`
- Modify `api/tests.py` — `PublishedStatTests`

**Frontend (create unless noted):**
- `src/lib/types/impact.ts` — types
- `src/lib/api/impact/published-stats.ts` — server fetch + `pick` helper
- `src/components/impact/dashboard/Section.tsx` — section shell, kicker, gradient text/rule, methodology note
- `src/components/impact/dashboard/KidFigure.tsx` + `IconArray.tsx` — the child glyph system
- `src/components/impact/dashboard/HBar.tsx` — horizontal bar rows
- `src/components/impact/dashboard/HeroSection.tsx`
- `src/components/impact/dashboard/ArgumentChain.tsx`
- `src/components/impact/dashboard/ClassroomLights.tsx` (client)
- `src/components/impact/dashboard/EcdParity.tsx`
- `src/components/impact/dashboard/RadarChart.tsx` + `ChildProfile.tsx`
- `src/components/impact/dashboard/NumeracySnapshot.tsx`
- `src/components/impact/dashboard/ScaleStory.tsx`
- `src/components/impact/dashboard/GovPartner.tsx`
- `src/components/impact/dashboard/Graduates.tsx`
- `src/components/impact/dashboard/HowWeKnow.tsx`
- `src/components/impact/dashboard/MoreResults.tsx`
- `src/components/impact/dashboard/GoDeeper.tsx`
- Modify `src/app/impact/page.tsx` — rebuilt as server component (old `overview/` components stay on disk, just unimported)

---

### Task 1: Backend — `PublishedStat` model

**Files:** Modify `api/models.py` (append at end); Test `api/tests.py`

- [ ] **Step 1: Write the failing test** — append to `api/tests.py`:

```python
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient


class PublishedStatTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _make(self, **kw):
        from api.models import PublishedStat
        defaults = dict(
            key="test_stat", value="42%", numeric_value=42.0, label="Test stat",
            source_system="Test source", population="Test population",
            comparison_type="none", as_of="2026-06-01",
            methodology_note="Test note", group="test_group",
            sort_order=1, is_published=True,
        )
        defaults.update(kw)
        return PublishedStat.objects.create(**defaults)

    def test_model_str(self):
        stat = self._make()
        self.assertEqual(str(stat), "test_stat = 42%")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test api.tests.PublishedStatTests -v 2`
Expected: FAIL — `ImportError`/`cannot import name 'PublishedStat'`

- [ ] **Step 3: Implement the model** — append to `api/models.py`:

```python
class PublishedStat(models.Model):
    """Hand-approved public stat for the donor-facing impact pages.

    Every number rendered on /impact/ comes from a row here. Updating a row is
    an editorial act (Django admin, with history) — never a pipeline side effect.
    """
    COMPARISON_CHOICES = [
        ('none', 'None'),
        ('comparison_group', 'Comparison group'),
        ('control_group', 'Control group'),
        ('benchmark', 'Benchmark'),
    ]

    key = models.SlugField(max_length=80, unique=True)
    value = models.CharField(max_length=40, help_text="Display string, e.g. '19,444' or '53%'")
    numeric_value = models.FloatField(null=True, blank=True)
    numeric_value_secondary = models.FloatField(
        null=True, blank=True,
        help_text="Second number for baseline/endline pairs (numeric_value=endline, secondary=baseline)")
    label = models.CharField(max_length=120)
    description = models.TextField(blank=True, default="")
    source_system = models.CharField(max_length=200)
    population = models.CharField(max_length=200, blank=True, default="")
    comparison_type = models.CharField(max_length=20, choices=COMPARISON_CHOICES, default='none')
    as_of = models.DateField()
    methodology_note = models.TextField(blank=True, default="")
    group = models.CharField(max_length=60, blank=True, default="")
    sort_order = models.IntegerField(default=0)
    is_published = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['group', 'sort_order']

    def __str__(self):
        return f"{self.key} = {self.value}"
```

- [ ] **Step 4: Make and run the migration**

Run: `python manage.py makemigrations api && python manage.py migrate`
Expected: one new migration creating `api_publishedstat`.

- [ ] **Step 5: Run test to verify it passes**

Run: `python manage.py test api.tests.PublishedStatTests -v 2`
Expected: PASS (1 test)

- [ ] **Step 6: Commit** (backend repo)

```bash
git add api/models.py api/migrations api/tests.py
git commit -m "Add PublishedStat model for donor-facing impact stats"
```

### Task 2: Backend — admin registration

**Files:** Modify `api/admin.py`

- [ ] **Step 1: Register the model** — add `PublishedStat` to the imports at the top of `api/admin.py`, then append:

```python
@admin.register(PublishedStat)
class PublishedStatAdmin(admin.ModelAdmin):
    list_display = ('key', 'value', 'label', 'group', 'as_of', 'is_published')
    list_filter = ('is_published', 'group', 'comparison_type')
    search_fields = ('key', 'label', 'source_system')
    list_editable = ('is_published',)
    fieldsets = (
        ('Identity', {'fields': ('key', 'group', 'sort_order', 'is_published')}),
        ('Value', {'fields': ('value', 'numeric_value', 'numeric_value_secondary', 'label', 'description')}),
        ('Provenance', {'fields': ('source_system', 'population', 'comparison_type', 'as_of', 'methodology_note')}),
    )
```

- [ ] **Step 2: Verify admin loads**

Run: `python manage.py check`
Expected: `System check identified no issues`

- [ ] **Step 3: Commit**

```bash
git add api/admin.py
git commit -m "Register PublishedStat in admin"
```

### Task 3: Backend — public endpoint

**Files:** Create `api/views/impact.py`; modify `api/views/__init__.py`, `api/urls.py`; test in `api/tests.py`

- [ ] **Step 1: Write the failing tests** — add to `PublishedStatTests` in `api/tests.py`:

```python
    def test_endpoint_returns_published_only(self):
        self._make(key="pub", group="g1", sort_order=2)
        self._make(key="pub_first", group="g1", sort_order=1)
        self._make(key="hidden", is_published=False)
        res = self.client.get("/api/impact/published-stats/")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("pub", data["stats"])
        self.assertNotIn("hidden", data["stats"])
        self.assertEqual(data["groups"]["g1"], ["pub_first", "pub"])  # sort_order respected
        self.assertEqual(data["verified_through"], "2026-06-01")

    def test_endpoint_requires_no_auth(self):
        res = self.client.get("/api/impact/published-stats/")
        self.assertEqual(res.status_code, 200)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python manage.py test api.tests.PublishedStatTests -v 2`
Expected: FAIL with 404 (route not defined)

- [ ] **Step 3: Create `api/views/impact.py`:**

```python
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes, authentication_classes

from ..models import PublishedStat


@api_view(['GET'])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
def published_stats(request):
    """Public, aggregate-only stats for the donor-facing impact pages."""
    rows = PublishedStat.objects.filter(is_published=True).order_by('group', 'sort_order')
    stats, groups = {}, {}
    verified_through = None
    for r in rows:
        stats[r.key] = {
            'key': r.key, 'value': r.value,
            'numeric_value': r.numeric_value,
            'numeric_value_secondary': r.numeric_value_secondary,
            'label': r.label, 'description': r.description,
            'source_system': r.source_system, 'population': r.population,
            'comparison_type': r.comparison_type, 'as_of': r.as_of.isoformat(),
            'methodology_note': r.methodology_note,
            'group': r.group, 'sort_order': r.sort_order,
        }
        if r.group:
            groups.setdefault(r.group, []).append(r.key)
        if verified_through is None or r.as_of.isoformat() > verified_through:
            verified_through = r.as_of.isoformat()
    return Response({'stats': stats, 'groups': groups, 'verified_through': verified_through})
```

- [ ] **Step 4: Wire it up.** In `api/views/__init__.py` add `from .impact import published_stats` (and `'published_stats'` to `__all__` if present). In `api/urls.py` add under a new comment block:

```python
    # Public impact dashboard (no auth — aggregate, hand-approved stats only)
    path('impact/published-stats/', views.published_stats, name='published_stats'),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python manage.py test api.tests.PublishedStatTests -v 2`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add api/views/impact.py api/views/__init__.py api/urls.py api/tests.py
git commit -m "Add public published-stats endpoint for impact dashboard"
```

### Task 4: Backend — seed command

**Files:** Create `api/management/commands/seed_published_stats.py`

All seeds are `is_published=True` so development renders; rows whose `methodology_note` starts with `PROVISIONAL` must be verified before launch (spec §7 checklist — this is the editorial gate, the page does not go live until those notes are cleared by Jim).

- [ ] **Step 1: Create the command:**

```python
from django.core.management.base import BaseCommand
from api.models import PublishedStat

P = "PROVISIONAL — verify before launch. "

SEEDS = [
    # group: hero_kpis
    dict(key="hero_children", value="19,444", numeric_value=19444, label="children on programme",
         source_system="Masi Data Site home.py", population="Children on programme, 2026",
         as_of="2026-06-12", methodology_note=P + "Reconcile vs 18,276 (site) / 25,000+ (ZZ).",
         group="hero_kpis", sort_order=1),
    dict(key="hero_schools", value="231", numeric_value=231, label="schools & ECD centres",
         source_system="Masi Data Site home.py", population="Active sites, 2026",
         as_of="2026-06-12", methodology_note=P + "Reconcile vs 154 / 250+.", group="hero_kpis", sort_order=2),
    dict(key="hero_youth", value="515", numeric_value=515, label="local youth employed",
         source_system="Masi Data Site home.py", population="Youth employed, 2026",
         as_of="2026-06-12", methodology_note=P + "Decide active vs annual vs cumulative.",
         group="hero_kpis", sort_order=3),
    dict(key="hero_records", value="1.1M", numeric_value=1100000, label="assessment & session records",
         source_system="ZZ DATA_SOURCES_DOCUMENTATION.md", population="All-time records",
         as_of="2026-06-12", methodology_note=P + "Compute real count.", group="hero_kpis", sort_order=4),
    # group: argument
    dict(key="arg_pirls", value="81%", numeric_value=81, label="of South African 10-year-olds cannot read for meaning",
         source_system="PIRLS 2021", population="South African Grade 4 learners",
         as_of="2026-06-12", methodology_note="Published international study.", group="argument", sort_order=1),
    dict(key="arg_letter_sounds", value="73%", numeric_value=73, label="never learn their letter sounds by the end of Grade 1",
         source_system="Wordworks / Eastern Cape benchmark research", population="Eastern Cape Grade 1 learners",
         comparison_type="benchmark", as_of="2026-06-12",
         methodology_note=P + "Confirm exact phrasing vs 27%-reach-benchmark source.", group="argument", sort_order=2),
    dict(key="arg_correlation", value="0.93", numeric_value=0.93, label="correlation between our two independent assessment methods",
         source_system="ZZ Research & Benchmarks (Spearman)", population="Programme learners",
         as_of="2026-06-12", methodology_note="Letters Known vs EGRA improvement, rho=0.933.",
         group="argument", sort_order=3),
    # group: classroom (cinematic) — percentages of a 42-child classroom
    dict(key="class_size", value="42", numeric_value=42, label="average Eastern Cape Grade 1 class size",
         source_system="DBE class size data", as_of="2026-06-12",
         methodology_note=P + "Confirm average class size figure.", group="classroom", sort_order=1),
    dict(key="cine_jan", value="13%", numeric_value=13, label="at benchmark, January baseline",
         source_system="Masi Data Site zz_2025_midline.py", population="Grade 1 programme learners, 2025",
         comparison_type="benchmark", as_of="2026-06-12", methodology_note="2025 baseline.", group="classroom", sort_order=2),
    dict(key="cine_jun", value="53%", numeric_value=53, label="at benchmark, June midline",
         source_system="Masi Data Site zz_2025_midline.py", population="Grade 1 programme learners, 2025",
         comparison_type="benchmark", as_of="2026-06-12", methodology_note="2025 midline.", group="classroom", sort_order=3),
    dict(key="cine_comparison", value="27%", numeric_value=27, label="at benchmark, comparison schools full year",
         source_system="Masi uts_me_benchmarks.py", population="isiXhosa comparison-school Grade 1s",
         comparison_type="comparison_group", as_of="2026-06-12",
         methodology_note="Use 'comparison group' wording.", group="classroom", sort_order=4),
    dict(key="cine_endline_2023", value="74%", numeric_value=74, label="at benchmark, 2023 cohort endline",
         source_system="ZZ 2023 Results", population="Grade 1 programme learners, 2023",
         comparison_type="benchmark", as_of="2026-06-12", methodology_note="2023 pilot endline.", group="classroom", sort_order=5),
    # group: ecd
    dict(key="ecd_masi_lcpm", value="14.9", numeric_value=14.9, label="Masi ECD letters correct per minute (ages 4-5)",
         source_system="2026 live assessment data (ECD midline)", population="Masi ECD learners, 2026",
         as_of="2026-06-12", methodology_note="Confirmed by Jim 2026-06-12.", group="ecd", sort_order=1),
    dict(key="ecd_g1_lcpm", value="15.4", numeric_value=15.4, label="Grade 1 comparison letters correct per minute (ages 6-7)",
         source_system="2026 live assessment data (Grade 1 comparison)", population="Grade 1 comparison-group learners, 2026",
         comparison_type="comparison_group", as_of="2026-06-12",
         methodology_note="Confirmed by Jim 2026-06-12.", group="ecd", sort_order=2),
    # group: numeracy — numeric_value=endline, numeric_value_secondary=baseline (standardised /10)
    dict(key="num_avg_gain", value="+21", numeric_value=21, label="average score gain out of 90",
         source_system="Masi numeracy_assessments_25.py", population="Matched baseline-endline learners, 2025",
         as_of="2026-06-12", methodology_note=P + "Confirm exact average gain.", group="numeracy", sort_order=1),
    dict(key="num_counting", value="8.8", numeric_value=8.8, numeric_value_secondary=6.1, label="Counting aloud",
         source_system="Masi numeracy_assessments_25.py", as_of="2026-06-12",
         methodology_note=P, group="numeracy_components", sort_order=1),
    dict(key="num_recognition", value="7.4", numeric_value=7.4, numeric_value_secondary=4.8, label="Number recognition",
         source_system="Masi numeracy_assessments_25.py", as_of="2026-06-12",
         methodology_note=P, group="numeracy_components", sort_order=2),
    dict(key="num_sums", value="5.8", numeric_value=5.8, numeric_value_secondary=3.0, label="Sums to 10",
         source_system="Masi numeracy_assessments_25.py", as_of="2026-06-12",
         methodology_note=P, group="numeracy_components", sort_order=3),
    dict(key="num_th_count20", value="81%", numeric_value=81, label="can count to 20+",
         source_system="Masi numeracy_assessments_25.py", as_of="2026-06-12",
         methodology_note=P, group="numeracy_thresholds", sort_order=1),
    dict(key="num_th_id100", value="64%", numeric_value=64, label="identify numbers to 100",
         source_system="Masi numeracy_assessments_25.py", as_of="2026-06-12",
         methodology_note=P, group="numeracy_thresholds", sort_order=2),
    dict(key="num_th_write10", value="72%", numeric_value=72, label="write numbers 1-10",
         source_system="Masi numeracy_assessments_25.py", as_of="2026-06-12",
         methodology_note=P, group="numeracy_thresholds", sort_order=3),
    # group: graduates
    dict(key="grads_count", value="454", numeric_value=454, label="university graduates",
         source_system="Website home page", as_of="2026-06-12",
         methodology_note=P + "Confirm current count.", group="graduates", sort_order=1),
    dict(key="grads_women", value="95%", numeric_value=95, label="of staff are women",
         source_system="Website about page", as_of="2026-06-12",
         methodology_note=P + "Verify current figure.", group="graduates", sort_order=2),
    # group: more_results
    dict(key="more_zero_letters", value="51% → 12%", numeric_value=12, numeric_value_secondary=51,
         label="children with zero letter knowledge, January to November",
         source_system="ZZ letter_knowledge_2024.py", as_of="2026-06-12",
         methodology_note=P + "Confirm endline zero-letter percentage.", group="more_results", sort_order=1),
    dict(key="more_growth", value="3×", numeric_value=3, label="faster letter-fluency growth than comparison learners",
         source_system="ZZ midline_primary_2026.py", comparison_type="comparison_group",
         as_of="2026-06-12", methodology_note=P + "Confirm multiple.", group="more_results", sort_order=2),
    dict(key="more_stories", value="120k+", numeric_value=120000, label="stories read aloud to young children (1000 Stories)",
         source_system="Masi uts_1000_stories.py", as_of="2026-06-12",
         methodology_note=P + "Pull real total.", group="more_results", sort_order=3),
    dict(key="more_correlation", value="0.93", numeric_value=0.93, label="correlation between our two independent assessment methods",
         source_system="ZZ Research & Benchmarks (Spearman)", as_of="2026-06-12",
         methodology_note="rho=0.933.", group="more_results", sort_order=4),
]


class Command(BaseCommand):
    help = "Seed the published-stats store with the spec's launch set (idempotent upsert by key)."

    def handle(self, *args, **options):
        created = updated = 0
        for row in SEEDS:
            row.setdefault("is_published", True)
            obj, was_created = PublishedStat.objects.update_or_create(key=row["key"], defaults=row)
            created += was_created
            updated += (not was_created)
        self.stdout.write(self.style.SUCCESS(f"Seeded published stats: {created} created, {updated} updated"))
```

- [ ] **Step 2: Run it and verify**

Run: `python manage.py seed_published_stats` then `python manage.py shell -c "from api.models import PublishedStat; print(PublishedStat.objects.count())"`
Expected: `Seeded published stats: 25 created, 0 updated` then `25`. Run the command twice — second run must say `0 created, 25 updated` (idempotent).

- [ ] **Step 3: Smoke-test the endpoint**

Run: `python manage.py runserver` then `curl -s http://localhost:8000/api/impact/published-stats/ | head -c 400`
Expected: JSON starting with `{"stats": {"hero_children":` …

- [ ] **Step 4: Commit**

```bash
git add api/management/commands/seed_published_stats.py
git commit -m "Add seed command for published impact stats"
```

### Task 5: Frontend — types and server fetch

**Files:** Create `src/lib/types/impact.ts`, `src/lib/api/impact/published-stats.ts`

- [ ] **Step 1: Create `src/lib/types/impact.ts`:**

```typescript
export interface PublishedStat {
  key: string;
  value: string;
  numeric_value: number | null;
  numeric_value_secondary: number | null;
  label: string;
  description: string;
  source_system: string;
  population: string;
  comparison_type: 'none' | 'comparison_group' | 'control_group' | 'benchmark';
  as_of: string;
  methodology_note: string;
  group: string;
  sort_order: number;
}

export interface PublishedStatsPayload {
  stats: Record<string, PublishedStat>;
  groups: Record<string, string[]>;
  verified_through: string | null;
}
```

- [ ] **Step 2: Create `src/lib/api/impact/published-stats.ts`:**

```typescript
import 'server-only';
import { PublishedStat, PublishedStatsPayload } from '@/lib/types/impact';

export async function getPublishedStats(): Promise<PublishedStatsPayload | null> {
  try {
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/impact/published-stats/`, {
      next: { revalidate: 3600 },
    });
    if (!res.ok) return null;
    return (await res.json()) as PublishedStatsPayload;
  } catch {
    return null; // page renders with sections hiding their numbers (spec §6)
  }
}

export function pick(payload: PublishedStatsPayload | null, key: string): PublishedStat | null {
  return payload?.stats[key] ?? null;
}

export function group(payload: PublishedStatsPayload | null, name: string): PublishedStat[] {
  if (!payload?.groups[name]) return [];
  return payload.groups[name].map((k) => payload.stats[k]).filter(Boolean);
}
```

- [ ] **Step 3: Verify it compiles**

Run: `pnpm lint`
Expected: no new errors.

- [ ] **Step 4: Commit** (frontend repo)

```bash
git add src/lib/types/impact.ts src/lib/api/impact/published-stats.ts
git commit -m "Add published-stats types and server fetch for impact dashboard"
```

### Task 6: Frontend — design primitives

**Files:** Create `src/components/impact/dashboard/Section.tsx`, `KidFigure.tsx`, `IconArray.tsx`, `HBar.tsx`

- [ ] **Step 1: Create `Section.tsx`** (server component — no `'use client'`):

```tsx
import { ReactNode } from 'react';
import { PublishedStat } from '@/lib/types/impact';

export function Section({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <section className={className}>
      <div className="mx-auto max-w-[1180px] px-6 py-20 md:px-12 md:py-24 lg:px-20">{children}</div>
    </section>
  );
}

export function Kicker({ children }: { children: ReactNode }) {
  return <div className="mb-4 text-xs font-semibold uppercase tracking-[3px] text-gray-400">{children}</div>;
}

export function GradientText({ children }: { children: ReactNode }) {
  return (
    <span className="bg-gradient-to-r from-blue-600 via-purple-600 to-rose-600 bg-clip-text text-transparent">
      {children}
    </span>
  );
}

export function GradientRule() {
  return <div className="my-5 h-[3px] w-[90px] bg-gradient-to-r from-blue-600 to-rose-600" />;
}

/** Accessible provenance disclosure. Renders nothing when stat is null. */
export function MethodologyNote({ stat, dark = false }: { stat: PublishedStat | null; dark?: boolean }) {
  if (!stat) return null;
  return (
    <details className={`mt-4 text-[12.5px] ${dark ? 'text-gray-500' : 'text-gray-400'}`}>
      <summary className="cursor-pointer underline decoration-dotted underline-offset-2">
        Source: {stat.source_system}
      </summary>
      <div className="mt-1 max-w-md leading-relaxed">
        {stat.population && <div>Population: {stat.population}</div>}
        <div>Verified: {stat.as_of}</div>
        {stat.methodology_note && <div>{stat.methodology_note}</div>}
      </div>
    </details>
  );
}
```

- [ ] **Step 2: Create `KidFigure.tsx`** — the single most reused glyph; build it exactly like this:

```tsx
const PALETTE = {
  litHead: '#fbbf24',
  darkUnlit: '#2a2f45', // on #0c0f1d bands
  lightUnlit: '#cbd5e1', // on white/slate bands
  lightShaded: '#334155', // "crisis" filled variant on light bands
} as const;

export type KidVariant = 'dark-unlit' | 'light-unlit' | 'light-shaded' | 'lit';

/** A child figure: circle head + round-shouldered body. Pure SVG, no deps. */
export function KidFigure({
  variant,
  size = 18,
  delayMs = 0,
}: {
  variant: KidVariant;
  size?: number;
  delayMs?: number;
}) {
  const fill =
    variant === 'lit' ? PALETTE.litHead
    : variant === 'dark-unlit' ? PALETTE.darkUnlit
    : variant === 'light-shaded' ? PALETTE.lightShaded
    : PALETTE.lightUnlit;
  return (
    <svg
      width={size}
      height={size * 1.44}
      viewBox="0 0 18 26"
      aria-hidden="true"
      style={{
        filter: variant === 'lit' ? 'drop-shadow(0 0 7px rgba(251,191,36,0.75))' : 'none',
        transition: 'filter 0.6s ease',
        transitionDelay: `${delayMs}ms`,
      }}
    >
      <circle cx="9" cy="4.5" r="4.5" fill={fill} style={{ transition: 'fill 0.6s ease', transitionDelay: `${delayMs}ms` }} />
      <path
        d="M2 26 L2 17 Q2 11 9 11 Q16 11 16 17 L16 26 Z"
        fill={fill}
        style={{ transition: 'fill 0.6s ease', transitionDelay: `${delayMs}ms` }}
      />
    </svg>
  );
}
```

- [ ] **Step 3: Create `IconArray.tsx`:**

```tsx
import { KidFigure, KidVariant } from './KidFigure';

/** Row/grid of child figures with the first `filled` (by visual order) in the filled variant. */
export function IconArray({
  total,
  filled,
  filledVariant,
  emptyVariant,
  size = 17,
  className = '',
}: {
  total: number;
  filled: number;
  filledVariant: KidVariant;
  emptyVariant: KidVariant;
  size?: number;
  className?: string;
}) {
  return (
    <div className={`flex gap-[5px] ${className}`} role="img" aria-label={`${filled} of ${total}`}>
      {Array.from({ length: total }, (_, i) => (
        <KidFigure key={i} variant={i < filled ? filledVariant : emptyVariant} size={size} />
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Create `HBar.tsx`** — horizontal bar rows used by EcdParity and NumeracySnapshot:

```tsx
import { ReactNode } from 'react';

/**
 * One labelled horizontal bar. `pct` is the fill width 0-100 (caller computes
 * scale), `tone` picks brand gradient vs neutral. Label column fixed at 130px.
 */
export function HBar({
  label,
  sublabel,
  valueText,
  pct,
  tone,
  thin = false,
}: {
  label?: string;
  sublabel?: string;
  valueText: string;
  pct: number;
  tone: 'brand' | 'neutral';
  thin?: boolean;
}) {
  return (
    <div className={`flex items-center gap-3 ${thin ? '-mt-2 mb-3.5' : 'mb-3.5'}`}>
      <div className="w-[130px] text-right text-[13px] leading-tight text-gray-500">
        {label}
        {sublabel && <span className="block text-[11px] text-gray-400">{sublabel}</span>}
      </div>
      <div className={`flex-1 overflow-hidden rounded-md bg-gray-100 ${thin ? 'h-[18px]' : 'h-[30px]'}`}>
        <div
          className={`flex h-full items-center justify-end rounded-md pr-2 text-xs font-semibold text-white ${
            tone === 'brand' ? 'bg-gradient-to-r from-blue-600 to-purple-600' : 'bg-slate-400'
          }`}
          style={{ width: `${Math.max(0, Math.min(100, pct))}%` }}
        >
          {valueText}
        </div>
      </div>
    </div>
  );
}

export function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-7 shadow-[0_8px_30px_rgba(17,24,39,0.05)]">
      <div className="mb-4 text-[13px] font-semibold text-gray-700">{title}</div>
      {children}
    </div>
  );
}
```

- [ ] **Step 5: Verify + commit**

Run: `pnpm lint` — Expected: clean.

```bash
git add src/components/impact/dashboard
git commit -m "Add impact dashboard design primitives (section shell, kid figures, bars)"
```

### Task 7: Frontend — Hero section

**Files:** Create `src/components/impact/dashboard/HeroSection.tsx`
**Stat keys:** `hero_children`, `hero_schools`, `hero_youth`, `hero_records` (group `hero_kpis`), payload `verified_through`.

Design notes (match mockup section 1): left-aligned; H1 two lines with gradient on "measured every day."; KPI row `flex gap-14`; verified stamp with a small green dot; faint foreshadow icon-array grid absolutely positioned top-right at `opacity-50`, hidden below `lg`.

- [ ] **Step 1: Create the component:**

```tsx
import { PublishedStatsPayload } from '@/lib/types/impact';
import { group } from '@/lib/api/impact/published-stats';
import { Kicker, GradientText, Section } from './Section';
import { KidFigure } from './KidFigure';

const FORE_LIT = [0, 2, 4, 7, 9, 11, 12, 14, 15, 17, 19, 20, 22];

function formatMonthYear(iso: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso + 'T00:00:00');
  return d.toLocaleDateString('en-ZA', { month: 'long', year: 'numeric' });
}

export function HeroSection({ payload }: { payload: PublishedStatsPayload | null }) {
  const kpis = group(payload, 'hero_kpis');
  const verified = formatMonthYear(payload?.verified_through ?? null);
  return (
    <Section className="relative overflow-hidden bg-white">
      <div className="absolute right-14 top-24 hidden lg:grid grid-cols-6 gap-x-3 gap-y-4 opacity-50" aria-hidden="true">
        {Array.from({ length: 24 }, (_, i) => (
          <KidFigure key={i} variant={FORE_LIT.includes(i) ? 'lit' : 'light-unlit'} size={20} />
        ))}
        <div className="col-span-6 mt-1 text-center text-[11px] text-gray-400">
          every figure is a child we measure
        </div>
      </div>
      <Kicker>Our Impact in Data</Kicker>
      <h1 className="max-w-[880px] text-5xl font-extrabold leading-[1.05] tracking-tight text-gray-900 md:text-6xl lg:text-[66px]">
        Children years ahead, <GradientText>measured every day.</GradientText>
      </h1>
      <p className="mt-6 max-w-[660px] text-lg leading-relaxed text-gray-600 md:text-[19px]">
        Children on Masinyusane programmes perform as much as two grade levels ahead of comparison
        groups — and a serious measurement system tracks every child, every session, every skill.
      </p>
      {kpis.length > 0 && (
        <div className="mt-12 flex flex-wrap gap-x-14 gap-y-8">
          {kpis.map((k) => (
            <div key={k.key}>
              <div className="text-4xl font-extrabold tracking-tight text-gray-900">{k.value}</div>
              <div className="mt-1 text-[13px] text-gray-500">{k.label}</div>
            </div>
          ))}
        </div>
      )}
      {verified && (
        <div className="mt-9 flex items-center gap-2 text-[13px] text-gray-400">
          <span className="h-2 w-2 rounded-full bg-emerald-500" />
          Figures verified {verified} <span aria-hidden="true">·</span>
          <a href="#how-we-know" className="underline decoration-dotted underline-offset-2">How we count</a>
        </div>
      )}
    </Section>
  );
}
```

- [ ] **Step 2: Lint + commit**

```bash
pnpm lint
git add src/components/impact/dashboard/HeroSection.tsx
git commit -m "Add impact dashboard hero section"
```

### Task 8: Frontend — Argument chain

**Files:** Create `src/components/impact/dashboard/ArgumentChain.tsx`
**Stat keys:** `arg_pirls`, `arg_letter_sounds`, `arg_correlation`.

Design notes (mockup section 2): light band; three columns separated by `border-l border-slate-200`; column 1 has a 10-figure icon array with 8 in `light-shaded`; column 2's big element is the word "Why?" at numeral scale; column 3's `2×` uses gradient text; closing line bold with gradient on "letter sounds, from age four."

- [ ] **Step 1: Create the component:**

```tsx
import { PublishedStatsPayload } from '@/lib/types/impact';
import { pick } from '@/lib/api/impact/published-stats';
import { GradientText, Kicker, Section } from './Section';
import { IconArray } from './IconArray';

export function ArgumentChain({ payload }: { payload: PublishedStatsPayload | null }) {
  const pirls = pick(payload, 'arg_pirls');
  const letters = pick(payload, 'arg_letter_sounds');
  const corr = pick(payload, 'arg_correlation');
  return (
    <Section className="border-y border-slate-100 bg-slate-50">
      <Kicker>Why letter sounds</Kicker>
      <h2 className="max-w-[640px] text-3xl font-extrabold leading-[1.2] tracking-tight text-gray-900 md:text-[34px]">
        South Africa&apos;s reading crisis is decided before age eight.
      </h2>
      <div className="mt-12 flex flex-col gap-10 md:flex-row md:gap-0">
        <div className="md:flex-1 md:px-7 md:first:pl-0">
          <IconArray total={10} filled={8} filledVariant="light-shaded" emptyVariant="light-unlit" className="mb-4" />
          {pirls && (
            <>
              <div className="text-5xl font-extrabold tracking-tighter text-slate-700 md:text-[58px]">{pirls.value}</div>
              <p className="mt-2.5 max-w-[250px] text-[14.5px] leading-snug text-slate-600">{pirls.label}.</p>
              <div className="mt-2.5 text-[11.5px] text-slate-400">{pirls.source_system}</div>
            </>
          )}
        </div>
        <div className="md:flex-1 md:border-l md:border-slate-200 md:px-7">
          <div className="text-5xl font-extrabold tracking-tighter text-slate-700 md:text-[58px]">Why?</div>
          {letters && (
            <>
              <p className="mt-3.5 max-w-[250px] text-[14.5px] leading-snug text-slate-600">
                <strong>{letters.value} {letters.label}</strong> — and letter-sound fluency is the strongest
                single predictor of becoming a reader.
              </p>
              <div className="mt-2.5 text-[11.5px] text-slate-400">
                {letters.source_system}{corr ? `; internal correlation ρ = ${corr.value}` : ''}
              </div>
            </>
          )}
        </div>
        <div className="md:flex-1 md:border-l md:border-slate-200 md:px-7">
          <div className="text-5xl font-extrabold tracking-tighter md:text-[58px]"><GradientText>2&times;</GradientText></div>
          <p className="mt-2.5 max-w-[250px] text-[14.5px] leading-snug text-slate-600">
            We double the number of children reaching the letter-sound benchmark in every classroom we enter.
          </p>
          <div className="mt-2.5 text-[11.5px] text-slate-400">See it happen below &darr;</div>
        </div>
      </div>
      <p className="mt-11 text-[19px] font-bold text-gray-900">
        So we start at the foundation — <GradientText>letter sounds, from age four.</GradientText>
      </p>
    </Section>
  );
}
```

- [ ] **Step 2: Lint + commit**

```bash
pnpm lint
git add src/components/impact/dashboard/ArgumentChain.tsx
git commit -m "Add argument chain section (81 percent / why / 2x)"
```

### Task 9: Frontend — ClassroomLights (the cinematic centerpiece)

**Files:** Create `src/components/impact/dashboard/ClassroomLights.tsx` (client component)
**Stat keys:** `class_size`, `cine_jan`, `cine_jun`, `cine_comparison`, `cine_endline_2023`.

This is the page's signature moment. **Open the mockup, scroll the dark section slowly, and reproduce that choreography exactly.**

**Choreography contract:**
- Outer container `h-[320vh]` on `bg-[#0c0f1d]`; inner stage `sticky top-0 h-screen` (flex column, vertically centered). **No ancestor of the sticky element may have `overflow-hidden`** — this killed an earlier prototype.
- Scroll progress p over the container maps to beats: `p<0.20 → 0`, `<0.45 → 1`, `<0.70 → 2`, `else 3`.
- Two "classrooms": grids of `classSize` (42) KidFigures, 7 columns, `gap-x-2 gap-y-3.5`.
- Lit counts (computed as `Math.round(classSize * pct / 100)`): Masi room by beat `[5, 22, 22, 31]`; comparison room `0` until beat ≥ 2, then `11`. Comparison room sits at `opacity-[0.18]` until beat ≥ 2, then full opacity (`transition-opacity duration-700`).
- Light-up order is the fixed shuffles below (deterministic; never `Math.random()`). Newly lit figures stagger at 35ms per figure, capped at 900ms.
- Left column: 4 narration steps; active step gets `opacity-100 bg-white/10 text-gray-50 border-l-[3px] border-rose-600`; inactive `opacity-35 text-gray-500`. Step 4 is the payoff card: gradient-tinted background `bg-gradient-to-r from-blue-600/25 to-rose-600/25 border border-pink-400/35`, hidden (opacity-0, translate-y-2) until beat 3.
- Progress bar: 3px, top of stage, `bg-gradient-to-r from-blue-600 to-rose-600`, `scaleX` = p with `origin-left`.
- Reduced motion: render beat 3 statically (both rooms fully revealed at final counts, all four steps visible at full opacity, no transitions).

- [ ] **Step 1: Create the component:**

```tsx
'use client';

import { useRef, useState } from 'react';
import { motion, useScroll, useMotionValueEvent, useReducedMotion } from 'framer-motion';
import { PublishedStatsPayload } from '@/lib/types/impact';
import { pick } from '@/lib/api/impact/published-stats';
import { KidFigure } from './KidFigure';

const ORDER_MASI = [17,3,38,9,28,1,33,12,40,6,22,15,35,0,26,10,31,19,41,4,24,13,37,7,29,2,20,16,39,8,25,11,34,18,30,5,23,14,36,21,32,27];
const ORDER_COMP = [5,30,12,39,2,25,17,34,8,21,41,14,28,0,36,10,19,32,6,23,38,15,3,27,11,35,20,7,40,16,29,1,24,13,37,9,31,18,4,26,33,22];

function Room({
  title, caption, litCount, order, dimmed,
}: {
  title: string; caption: string; litCount: number; order: number[]; dimmed: boolean;
}) {
  return (
    <div
      className={`flex-1 rounded-2xl border border-white/10 bg-white/[0.04] px-6 pb-5 pt-6 transition-opacity duration-700 ${
        dimmed ? 'opacity-[0.18]' : 'opacity-100'
      }`}
    >
      <div className="text-[13px] font-semibold text-gray-300">{title}</div>
      <div className="mt-0.5 min-h-4 text-xs text-gray-500">
        {litCount > 0 && (
          <>
            <span className="text-sm font-bold text-amber-400">{litCount}</span> of {order.length} readers — {caption}
          </>
        )}
      </div>
      <div className="mt-4 grid grid-cols-7 justify-items-center gap-x-2 gap-y-3.5">
        {order.map((pos, i) => {
          const rank = order.indexOf(i); // rank of seat i in light-up order
          const lit = rank < litCount;
          return <KidFigure key={i} variant={lit ? 'lit' : 'dark-unlit'} size={18} delayMs={lit ? Math.min(rank * 35, 900) : 0} />;
        })}
      </div>
    </div>
  );
}

export function ClassroomLights({ payload }: { payload: PublishedStatsPayload | null }) {
  const ref = useRef<HTMLDivElement>(null);
  const reduced = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ['start start', 'end end'] });
  const [beat, setBeat] = useState(0);
  useMotionValueEvent(scrollYProgress, 'change', (p) => {
    setBeat(p < 0.2 ? 0 : p < 0.45 ? 1 : p < 0.7 ? 2 : 3);
  });

  const size = pick(payload, 'class_size')?.numeric_value ?? 42;
  const pctJan = pick(payload, 'cine_jan')?.numeric_value ?? 13;
  const pctJun = pick(payload, 'cine_jun')?.numeric_value ?? 53;
  const pctComp = pick(payload, 'cine_comparison')?.numeric_value ?? 27;
  const pctEnd = pick(payload, 'cine_endline_2023')?.numeric_value ?? 74;
  const n = (pct: number) => Math.round((size * pct) / 100);
  const b = reduced ? 3 : beat;
  const masiCount = [n(pctJan), n(pctJun), n(pctJun), n(pctEnd)][b];
  const masiCaption = b >= 3 ? '2023 endline' : b >= 1 ? 'June' : 'January';
  const compCount = b >= 2 ? n(pctComp) : 0;

  const steps = [
    <>A typical Eastern Cape Grade 1: <b className="text-white">{size} children</b>. In January, about{' '}
      <b className="text-white">{n(pctJan)}</b> are on track to read.</>,
    <>Six months with Masi coaches: <b className="text-white">{n(pctJun)} of {size}</b> cross the letter-sound benchmark.</>,
    <>A comparison classroom ends the whole year at <b className="text-white">{n(pctComp)} of {size}</b>.</>,
  ];

  return (
    <div ref={ref} className={reduced ? 'bg-[#0c0f1d]' : 'h-[320vh] bg-[#0c0f1d]'}>
      <div className={`${reduced ? '' : 'sticky top-0 h-screen'} flex flex-col justify-center px-6 py-16 text-white md:px-12 lg:px-[70px]`}>
        {!reduced && (
          <motion.div
            className="absolute left-0 top-0 h-[3px] w-full origin-left bg-gradient-to-r from-blue-600 to-rose-600"
            style={{ scaleX: scrollYProgress }}
          />
        )}
        <div className="mx-auto w-full max-w-[1180px]">
          <div className="mb-4 text-xs font-semibold uppercase tracking-[3px] text-gray-500">Chapter 01 · Literacy</div>
          <h2 className="text-3xl font-extrabold leading-[1.15] tracking-tight md:text-4xl">
            Watch the lights come on in one classroom.
          </h2>
          <div className="mt-8 flex flex-col gap-8 lg:flex-row lg:gap-10">
            <div className="flex w-full flex-col justify-center gap-3 lg:w-[300px] lg:shrink-0">
              {steps.map((content, i) => (
                <div
                  key={i}
                  className={`rounded-xl px-4 py-3.5 text-sm leading-relaxed transition-all duration-500 ${
                    b === i || (reduced && i < 3)
                      ? 'border-l-[3px] border-rose-600 bg-white/10 text-gray-50 opacity-100'
                      : 'bg-white/[0.04] text-gray-500 opacity-35'
                  }`}
                >
                  {content}
                </div>
              ))}
              <div
                className={`rounded-xl border border-pink-400/35 bg-gradient-to-r from-blue-600/25 to-rose-600/25 px-4 py-3.5 text-[14.5px] font-semibold leading-relaxed text-white transition-all duration-700 ${
                  b === 3 ? 'translate-y-0 opacity-100' : 'translate-y-2 opacity-0'
                }`}
              >
                In every classroom we enter, the number of readers roughly <b>doubles</b> — our 2023
                cohort finished at <b>{n(pctEnd)} of {size}</b>.
              </div>
            </div>
            <div className="flex flex-1 flex-col gap-5 sm:flex-row sm:gap-6">
              <Room title="Comparison classroom" caption="full year" litCount={compCount} order={ORDER_COMP} dimmed={b < 2} />
              <Room title="Masinyusane classroom" caption={masiCaption} litCount={masiCount} order={ORDER_MASI} dimmed={false} />
            </div>
          </div>
          <p className="mt-6 text-[12.5px] text-gray-500">
            <b className="text-gray-400">A reader</b> = a child at the Grade 1 benchmark of 40 letter sounds
            per minute. Class of {size} = average Eastern Cape Grade 1.
          </p>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Manual verification (do not skip).** With backend + `pnpm dev` running, view `http://localhost:3000/impact` after Task 18 page assembly — for now temporarily render `<ClassroomLights payload={null} />` from a scratch route if you want early validation, otherwise verify during Task 18. Checks: section pins while scrolling ~3 viewport heights; lights ignite one-by-one; comparison room fades in at beat 2; payoff card appears at beat 3; with macOS "Reduce Motion" enabled the section renders statically at final state with no tall scroll region.

- [ ] **Step 3: Lint + commit**

```bash
pnpm lint
git add src/components/impact/dashboard/ClassroomLights.tsx
git commit -m "Add scroll-driven classroom lights centerpiece"
```

### Task 10: Frontend — ECD parity chapter

**Files:** Create `src/components/impact/dashboard/EcdParity.tsx`
**Stat keys:** `ecd_masi_lcpm`, `ecd_g1_lcpm`.

Design notes (mockup section 4): white band, two columns (`flex gap-16 items-center`, stack below `lg`). Left: kicker "Chapter 02 · Early Childhood", stat "2 years ahead" (numeral `2` at chapter-stat scale, "years ahead" at `text-4xl`), gradient rule, H3, copy, methodology note. Right: Panel "Letters correct per minute, 2026" with two near-equal HBars — **bar widths use scale max 20 lcpm** (14.9 → 74.5%, 15.4 → 77%), Masi bar `brand`, comparison `neutral` — then the gradient-bordered chip "Same fluency — two school years earlier" (chip: `inline-flex rounded-full p-[1px] bg-gradient-to-r from-blue-600 via-purple-600 to-rose-600` wrapping `rounded-full bg-white px-4 py-2 text-[13px] font-bold text-gray-900`).

- [ ] **Step 1: Create the component:**

```tsx
import { PublishedStatsPayload } from '@/lib/types/impact';
import { pick } from '@/lib/api/impact/published-stats';
import { GradientRule, Kicker, MethodologyNote, Section } from './Section';
import { HBar, Panel } from './HBar';

export function EcdParity({ payload }: { payload: PublishedStatsPayload | null }) {
  const masi = pick(payload, 'ecd_masi_lcpm');
  const g1 = pick(payload, 'ecd_g1_lcpm');
  const SCALE_MAX = 20;
  return (
    <Section className="bg-white">
      <div className="flex flex-col items-center gap-12 lg:flex-row lg:gap-16">
        <div className="flex-1">
          <Kicker>Chapter 02 · Early Childhood</Kicker>
          <div className="text-6xl font-extrabold tracking-tighter leading-none text-gray-900 md:text-7xl">
            2 <span className="text-4xl">years ahead</span>
          </div>
          <GradientRule />
          <h3 className="mb-3 text-2xl font-bold tracking-tight text-gray-900 md:text-[26px]">
            Our four- and five-year-olds read at Grade 1 level.
          </h3>
          <p className="max-w-[440px] leading-relaxed text-gray-600">
            Children in Masinyusane ECD centres already sound letters as fast as Grade 1 learners two
            school years older in comparison schools. They arrive at school as readers — before the
            crisis can start.
          </p>
          <MethodologyNote stat={masi} />
        </div>
        <div className="w-full flex-1">
          {masi && g1 && (
            <Panel title="Letters correct per minute, 2026">
              <HBar label="Masi ECD" sublabel="ages 4–5" valueText={masi.value}
                    pct={((masi.numeric_value ?? 0) / SCALE_MAX) * 100} tone="brand" />
              <HBar label="Grade 1 comparison" sublabel="ages 6–7, no programme" valueText={g1.value}
                    pct={((g1.numeric_value ?? 0) / SCALE_MAX) * 100} tone="neutral" />
              <div className="mt-4 inline-flex rounded-full bg-gradient-to-r from-blue-600 via-purple-600 to-rose-600 p-[1px]">
                <span className="rounded-full bg-white px-4 py-2 text-[13px] font-bold text-gray-900">
                  Same fluency — two school years earlier
                </span>
              </div>
              <div className="mt-3 text-[12.5px] text-gray-400">
                Same one-minute EGRA letter task, 2026 live data. Ages 4–5 vs ages 6–7.
              </div>
            </Panel>
          )}
        </div>
      </div>
    </Section>
  );
}
```

- [ ] **Step 2: Lint + commit**

```bash
pnpm lint
git add src/components/impact/dashboard/EcdParity.tsx
git commit -m "Add ECD two-years-ahead parity chapter"
```

### Task 11: Frontend — Radar chart + child profile

**Files:** Create `src/components/impact/dashboard/RadarChart.tsx`, `ChildProfile.tsx`

**Governance:** the child story ships with ILLUSTRATIVE data and a silhouette portrait frame until the consent workflow (spec §7.6) delivers a real child. The "Illustrative profile" label is REQUIRED until then — removing it is an editorial decision, not a code change.

- [ ] **Step 1: Create `RadarChart.tsx`** — fixed 8-axis geometry copied from the approved mockup (center 140,140, radius 110, rings at 27.5/55/82.5/110). Series values are 0–1 fractions of the radius per axis, ordered clockwise from 12 o'clock:

```tsx
const CENTER = 140;
const R = 110;
const AXES = 8;

function point(axis: number, frac: number): string {
  const angle = (Math.PI * 2 * axis) / AXES - Math.PI / 2;
  const x = CENTER + R * frac * Math.cos(angle);
  const y = CENTER + R * frac * Math.sin(angle);
  return `${x.toFixed(1)},${y.toFixed(1)}`;
}

const LABELS: { text: string; x: number; y: number; anchor: 'start' | 'middle' | 'end' }[] = [
  { text: 'Letter Sounds', x: 140, y: 22, anchor: 'middle' },
  { text: 'Story Comp.', x: 228, y: 56, anchor: 'start' },
  { text: 'First Sounds', x: 258, y: 144, anchor: 'start' },
  { text: 'Read Words', x: 226, y: 232, anchor: 'start' },
  { text: 'Read Sentences', x: 140, y: 272, anchor: 'middle' },
  { text: 'Write Letters', x: 54, y: 232, anchor: 'end' },
  { text: 'Write CVCs', x: 22, y: 144, anchor: 'end' },
  { text: 'Listen Words', x: 54, y: 56, anchor: 'end' },
];

export function RadarChart({ baseline, endline }: { baseline: number[]; endline: number[] }) {
  const poly = (vals: number[]) => vals.map((v, i) => point(i, v)).join(' ');
  return (
    <svg viewBox="0 0 280 290" className="w-full" role="img" aria-label="Skill profile, January vs November">
      <defs>
        <linearGradient id="radar-grad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#2563eb" />
          <stop offset="50%" stopColor="#9333ea" />
          <stop offset="100%" stopColor="#e11d48" />
        </linearGradient>
      </defs>
      <g transform="translate(0,10)">
        {[1, 0.75, 0.5, 0.25].map((f) => (
          <circle key={f} cx={CENTER} cy={CENTER} r={R * f} fill="none" stroke="#eef0f4" />
        ))}
        {Array.from({ length: AXES }, (_, i) => {
          const [x, y] = point(i, 1).split(',').map(Number);
          return <line key={i} x1={CENTER} y1={CENTER} x2={x} y2={y} stroke="#eef0f4" />;
        })}
        <polygon points={poly(baseline)} fill="rgba(148,163,184,0.25)" stroke="#94a3b8" strokeWidth="1.5" />
        <polygon points={poly(endline)} fill="rgba(147,51,234,0.13)" stroke="url(#radar-grad)" strokeWidth="2.5" />
        {LABELS.map((l) => (
          <text key={l.text} x={l.x} y={l.y} textAnchor={l.anchor} className="fill-gray-400" fontSize="9.5">
            {l.text}
          </text>
        ))}
      </g>
    </svg>
  );
}
```

- [ ] **Step 2: Create `ChildProfile.tsx`:**

```tsx
import { Kicker, Section } from './Section';
import { RadarChart } from './RadarChart';

const ILLUSTRATIVE_JAN = [0.36, 0.23, 0.32, 0.14, 0.27, 0.09, 0.18, 0.25];
const ILLUSTRATIVE_NOV = [0.86, 0.73, 0.91, 0.64, 0.82, 0.55, 0.68, 0.77];

export function ChildProfile() {
  return (
    <Section className="bg-gradient-to-b from-white via-orange-50/40 to-white">
      <div className="flex flex-col items-center gap-12 lg:flex-row lg:gap-14">
        <div className="w-[280px] shrink-0">
          <div className="relative h-[340px] w-[280px] overflow-hidden rounded-2xl bg-gradient-to-br from-amber-400 via-amber-500 to-amber-700 shadow-[0_16px_44px_rgba(180,83,9,0.25)]">
            <div className="absolute left-1/2 top-[24%] h-[100px] w-[100px] -translate-x-1/2 rounded-full bg-white/35" />
            <div className="absolute left-1/2 top-[58%] h-[150px] w-[190px] -translate-x-1/2 rounded-t-full bg-white/35" />
            <div className="absolute inset-x-3.5 bottom-3.5 rounded-xl bg-[#0c0f1d]/65 px-3.5 py-2.5 text-[13px] leading-relaxed text-white">
              <b>Amahle*, Grade 1</b>
              <br />62 sessions · Kwazakhele Primary
            </div>
          </div>
          <p className="mt-3 text-[11.5px] leading-relaxed text-gray-400">
            *Illustrative profile. A real child&apos;s consented photo and data replace this before
            launch (guardian consent + name change, POPIA).
          </p>
        </div>
        <div className="flex-1">
          <Kicker>Chapter 03 · One Child</Kicker>
          <h3 className="max-w-[460px] text-3xl font-extrabold leading-[1.15] tracking-tight text-gray-900 md:text-[32px]">
            Behind every percentage is a child we know by name.
          </h3>
          <p className="mt-4 max-w-[450px] leading-relaxed text-gray-600">
            In January, Amahle could sound four letters and read no words. Her coach — a young woman
            from the same township — saw it in the data and rebuilt her group&apos;s sessions around
            letter sounds. By November, Amahle reads full sentences.
          </p>
          <div className="mt-5 max-w-[450px] rounded-xl border border-orange-100 border-l-[3px] border-l-amber-500 bg-white px-4 py-3.5 text-sm font-semibold leading-relaxed text-gray-900">
            We can draw this chart for any child on programme — eleven skills, tracked across the
            year, for every one of them. That is what &quot;data-driven&quot; means here.
          </div>
        </div>
        <div className="w-full max-w-[330px] shrink-0 rounded-2xl border border-gray-200 bg-white p-6 shadow-[0_8px_30px_rgba(17,24,39,0.06)]">
          <div className="text-[13px] font-semibold text-gray-700">Amahle* — skill profile</div>
          <div className="my-2.5 flex items-center gap-4 text-xs text-gray-500">
            <span className="flex items-center gap-1.5">
              <span className="h-[3px] w-[18px] rounded bg-slate-300" />January
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-[3px] w-[18px] rounded bg-gradient-to-r from-blue-600 to-rose-600" />November
            </span>
          </div>
          <RadarChart baseline={ILLUSTRATIVE_JAN} endline={ILLUSTRATIVE_NOV} />
          <div className="mt-2 text-[11px] text-gray-400">11 skills on the full profile; 8 shown here.</div>
        </div>
      </div>
    </Section>
  );
}
```

- [ ] **Step 3: Lint + commit**

```bash
pnpm lint
git add src/components/impact/dashboard/RadarChart.tsx src/components/impact/dashboard/ChildProfile.tsx
git commit -m "Add child profile section with Jan/Nov radar overlay"
```

### Task 12: Frontend — Numeracy, MoreResults, HowWeKnow, GoDeeper

**Files:** Create `NumeracySnapshot.tsx`, `MoreResults.tsx`, `HowWeKnow.tsx`, `GoDeeper.tsx`
**Stat keys:** `num_avg_gain` + groups `numeracy_components` (HBar pairs: endline `brand`, baseline `neutral thin`, scale max 10), `numeracy_thresholds` (3 cards), `more_results` (4 cards).

- [ ] **Step 1: Create `NumeracySnapshot.tsx`** (mirror of EcdParity layout, light `alt` band `bg-slate-50 border-y border-slate-100`; copy column left with stat `+21/90`, panel right):

```tsx
import { PublishedStatsPayload } from '@/lib/types/impact';
import { group, pick } from '@/lib/api/impact/published-stats';
import { GradientRule, Kicker, MethodologyNote, Section } from './Section';
import { HBar, Panel } from './HBar';

export function NumeracySnapshot({ payload }: { payload: PublishedStatsPayload | null }) {
  const gain = pick(payload, 'num_avg_gain');
  const components = group(payload, 'numeracy_components');
  const thresholds = group(payload, 'numeracy_thresholds');
  return (
    <Section className="border-y border-slate-100 bg-slate-50">
      <div className="flex flex-col items-center gap-12 lg:flex-row lg:gap-16">
        <div className="flex-1">
          <Kicker>Chapter 04 · Numeracy</Kicker>
          {gain && (
            <div className="text-6xl font-extrabold tracking-tighter leading-none text-gray-900 md:text-7xl">
              {gain.value}<span className="text-4xl text-gray-400">/90</span>
            </div>
          )}
          <GradientRule />
          <h3 className="mb-3 text-2xl font-bold tracking-tight text-gray-900 md:text-[26px]">
            Number sense improves across all nine skills.
          </h3>
          <p className="max-w-[440px] leading-relaxed text-gray-600">
            From counting aloud to word problems, children gain measurable ground in every component
            of the Yazi Amanani assessment — not just the easy ones.
          </p>
          <MethodologyNote stat={gain} />
        </div>
        <div className="w-full flex-1">
          <Panel title="Baseline vs endline by skill (standardised /10)">
            {components.map((c) => (
              <div key={c.key}>
                <HBar label={c.label} valueText={c.value} pct={((c.numeric_value ?? 0) / 10) * 100} tone="brand" />
                <HBar valueText={String(c.numeric_value_secondary ?? '')}
                      pct={((c.numeric_value_secondary ?? 0) / 10) * 100} tone="neutral" thin />
              </div>
            ))}
            <div className="text-[11.5px] text-gray-400">…all 9 components shown after data verification</div>
            {thresholds.length > 0 && (
              <div className="mt-5 flex gap-3.5">
                {thresholds.map((t) => (
                  <div key={t.key} className="flex-1 rounded-xl border border-slate-100 bg-slate-50 p-3.5">
                    <div className="text-[22px] font-extrabold text-gray-900">{t.value}</div>
                    <div className="mt-1 text-[11.5px] leading-snug text-gray-500">{t.label}</div>
                  </div>
                ))}
              </div>
            )}
          </Panel>
        </div>
      </div>
    </Section>
  );
}
```

- [ ] **Step 2: Create `HowWeKnow.tsx`** — the page's only centered section. Icons: `ClipboardList`, `BarChart3`, `Eye` from `lucide-react`, rendered at `size={22}` inside `h-11 w-11 rounded-xl bg-gradient-to-br from-blue-50 to-pink-50 flex items-center justify-center text-gray-700`:

```tsx
import { ClipboardList, BarChart3, Eye } from 'lucide-react';
import Link from 'next/link';
import { GradientText, Kicker, Section } from './Section';

const STREAMS = [
  { icon: ClipboardList, title: 'Daily sessions',
    body: 'Every lesson logged: letters taught, group composition, attendance, duration.',
    micro: 'Shows children receive instruction' },
  { icon: BarChart3, title: 'Formal assessments',
    body: 'EGRA letter fluency and nine numeracy skills, at baseline, midline and endline.',
    micro: 'Shows children actually learn' },
  { icon: Eye, title: 'Mentor visits',
    body: 'Trained mentors observe sessions, coach youth, and flag quality issues early.',
    micro: 'Explains the numbers — and improves them' },
];

export function HowWeKnow() {
  return (
    <Section className="bg-white">
      <div className="text-center" id="how-we-know">
        <Kicker>Chapter 07 · Credibility</Kicker>
        <h2 className="text-3xl font-extrabold tracking-tight text-gray-900 md:text-[38px]">How we know.</h2>
        <p className="mx-auto mt-3.5 max-w-[620px] text-[17px] leading-relaxed text-gray-600">
          We don&apos;t just collect stories. Three independent evidence streams are triangulated daily —
          so when a number is high, we know why, and when it&apos;s low, we can fix it.
        </p>
      </div>
      <div className="mt-12 flex flex-col gap-6 text-left md:flex-row">
        {STREAMS.map((s) => (
          <div key={s.title} className="flex-1 rounded-2xl border border-gray-200 bg-white p-7 shadow-[0_8px_30px_rgba(17,24,39,0.04)]">
            <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-blue-50 to-pink-50 text-gray-700">
              <s.icon size={22} />
            </div>
            <h3 className="mb-2 text-[17px] font-bold text-gray-900">{s.title}</h3>
            <p className="text-sm leading-relaxed text-gray-500">{s.body}</p>
            <div className="mt-3.5 text-[12.5px] text-gray-400">{s.micro}</div>
          </div>
        ))}
      </div>
      <div className="mt-11 text-center">
        <Link href="/impact/measurement"
              className="inline-block rounded-xl bg-gray-900 px-7 py-3.5 text-[15px] font-semibold text-white">
          Inside our measurement system <GradientText>&rarr;</GradientText>
        </Link>
      </div>
    </Section>
  );
}
```

(The `/impact/measurement` route does not exist yet — that is expected; it is being designed separately. Next.js will 404 until it ships, which is acceptable in dev.)

- [ ] **Step 3: Create `MoreResults.tsx`:**

```tsx
import { PublishedStatsPayload } from '@/lib/types/impact';
import { group } from '@/lib/api/impact/published-stats';
import { Section } from './Section';

export function MoreResults({ payload }: { payload: PublishedStatsPayload | null }) {
  const items = group(payload, 'more_results');
  if (items.length === 0) return null;
  return (
    <Section className="border-t border-slate-100 bg-white">
      <h3 className="mb-5 text-[15px] font-bold uppercase tracking-wider text-gray-500">More results</h3>
      <div className="flex flex-col gap-4 md:flex-row">
        {items.map((s) => (
          <div key={s.key} className="flex-1 rounded-xl border border-gray-200 p-4.5">
            <div className="text-[22px] font-extrabold text-gray-900">{s.value}</div>
            <div className="mt-1 text-[12.5px] leading-relaxed text-gray-500">{s.label}</div>
          </div>
        ))}
      </div>
    </Section>
  );
}
```

- [ ] **Step 4: Create `GoDeeper.tsx`:**

```tsx
import { Section } from './Section';

const LINKS = [
  { title: 'Live data portal', body: 'The full exploration environment our own team uses.',
    cta: 'data.masinyusane.org', href: 'https://data.masinyusane.org' },
  { title: 'Zazi iZandi portal', body: 'Programme-level literacy results, 2023–2026.',
    cta: 'Open portal', href: 'https://zazi.masinyusane.org' },
  { title: 'Annual reports', body: 'Audited results and financials, year by year.',
    cta: 'View reports', href: '/impact/reports' },
  { title: 'Due-diligence pack', body: 'Methodology notes, data dictionary, evaluation designs.',
    cta: 'Request pack', href: 'mailto:info@masinyusane.org' },
];

export function GoDeeper() {
  return (
    <Section className="border-t border-slate-100 bg-slate-50">
      <h2 className="text-2xl font-bold tracking-tight text-gray-900 md:text-[26px]">Go deeper.</h2>
      <div className="mt-7 flex flex-col gap-4 md:flex-row">
        {LINKS.map((l) => (
          <a key={l.title} href={l.href}
             className="flex-1 rounded-xl border border-gray-200 bg-white p-5 transition-shadow hover:shadow-md">
            <div className="mb-1.5 text-[15px] font-bold text-gray-900">{l.title}</div>
            <div className="text-[13px] leading-relaxed text-gray-500">{l.body}</div>
            <div className="mt-3.5 text-[13px] font-semibold text-blue-600">{l.cta} &rarr;</div>
          </a>
        ))}
      </div>
    </Section>
  );
}
```

(Verify the Zazi portal URL with Jim before launch; if unknown, point both portal cards at `https://data.masinyusane.org`.)

- [ ] **Step 5: Lint + commit**

```bash
pnpm lint
git add src/components/impact/dashboard
git commit -m "Add numeracy, how-we-know, more-results and go-deeper sections"
```

### Task 13: Frontend — ScaleStory, GovPartner, Graduates

**Files:** Create `ScaleStory.tsx`, `GovPartner.tsx`, `Graduates.tsx`
**Stat keys:** `grads_count`, `grads_women` (group `graduates`).

- [ ] **Step 1: Create `ScaleStory.tsx`.** Dark band. Left: stylized map panel (v1 = deterministic CSS dots; MapLibre upgrade blocked on coordinates audit, spec §7.9 — School model already has `latitude`/`longitude`, audit completeness later). Right: 5-milestone timeline. Timeline copy for 2008–2022 is provisional pending Jim (spec §7.2) — keep the `(milestone to be confirmed)` parenthetical:

```tsx
import { Kicker, Section } from './Section';

const DOTS: { top: number; left: number; rose?: boolean }[] = [
  { top: 38, left: 22 }, { top: 45, left: 28 }, { top: 52, left: 25, rose: true },
  { top: 42, left: 48 }, { top: 55, left: 52 }, { top: 48, left: 58, rose: true },
  { top: 36, left: 64 }, { top: 58, left: 70 }, { top: 50, left: 76 },
  { top: 60, left: 40, rose: true }, { top: 64, left: 60 }, { top: 44, left: 36 },
  { top: 40, left: 25 }, { top: 47, left: 31 }, { top: 53, left: 29 },
  { top: 57, left: 34 }, { top: 49, left: 38, rose: true }, { top: 43, left: 41 },
  { top: 51, left: 45 }, { top: 59, left: 47 }, { top: 46, left: 51, rose: true },
  { top: 52, left: 56 }, { top: 61, left: 55 }, { top: 39, left: 55 },
  { top: 45, left: 62 }, { top: 54, left: 64, rose: true }, { top: 61, left: 66 },
  { top: 42, left: 69 }, { top: 48, left: 72 }, { top: 55, left: 74 },
  { top: 44, left: 77, rose: true }, { top: 52, left: 80 }, { top: 47, left: 84 },
];

const MILESTONES = [
  { year: '2008 — Founded', body: 'Gqeberha (Port Elizabeth). University scholarships for township youth begin.' },
  { year: '2015 — The jobs model', body: 'Local youth become the workforce: education delivery and youth employment merge into one model. (milestone to be confirmed)' },
  { year: '2023 — Zazi iZandi & the data system', body: '12 schools, 52 youth, 1,897 children. Daily session logging and formal EGRA measurement begin.' },
  { year: '2025 — Scale', body: '100+ schools, 500+ youth, three languages. East London launch; 16 ECD centres; government TA partnership.' },
  { year: '2026 — Provincial partner', body: 'Feature partner to the Eastern Cape DoE, with live data across every session, assessment and mentor visit.' },
];

export function ScaleStory() {
  return (
    <Section className="bg-[#0c0f1d] text-white">
      <Kicker>Chapter 05 · The model</Kicker>
      <h2 className="text-3xl font-extrabold tracking-tight md:text-[38px]">
        Eighteen years in the same communities.
      </h2>
      <p className="mt-3.5 max-w-[560px] text-[17px] leading-relaxed text-gray-400">
        Masinyusane hires and trains unemployed young people from the same communities as the schools —
        turning an education programme into a jobs programme, and a jobs programme into measurable learning.
      </p>
      <div className="mt-12 flex flex-col gap-10 lg:flex-row">
        <div className="relative min-h-[340px] flex-[1.3] overflow-hidden rounded-2xl border border-white/10 bg-white/[0.04]"
             style={{ backgroundImage: 'radial-gradient(ellipse at 30% 70%, rgba(37,99,235,0.16), transparent 60%)' }}>
          <div className="absolute -bottom-8 -left-5 -right-5 h-[120px] rounded-t-[50%] bg-[#1a2036]" />
          {DOTS.map((d, i) => (
            <span key={i}
              className="absolute h-[7px] w-[7px] rounded-full"
              style={{
                top: `${d.top}%`, left: `${d.left}%`,
                background: d.rose ? '#fb7185' : '#60a5fa',
                boxShadow: `0 0 10px ${d.rose ? 'rgba(251,113,133,0.8)' : 'rgba(96,165,250,0.8)'}`,
              }} />
          ))}
          <div className="absolute left-[24%] top-[66%] text-[11px] font-semibold text-slate-300">Gqeberha</div>
          <div className="absolute left-[80%] top-[38%] text-[11px] font-semibold text-slate-300">East London</div>
          <div className="absolute bottom-3.5 left-4 text-xs text-gray-500">
            Sites across the Eastern Cape — interactive map ships once coordinates are audited
          </div>
        </div>
        <div className="flex-1">
          {MILESTONES.map((m, i) => (
            <div key={m.year} className="flex gap-4">
              <div className="flex flex-col items-center">
                <span className="mt-1 h-3 w-3 shrink-0 rounded-full bg-gradient-to-br from-blue-600 to-rose-600" />
                {i < MILESTONES.length - 1 && <span className="w-0.5 flex-1 bg-white/10" />}
              </div>
              <div className="pb-6">
                <div className="text-sm font-bold text-white">{m.year}</div>
                <p className="mt-1 max-w-[330px] text-[13.5px] leading-relaxed text-gray-400">{m.body}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </Section>
  );
}
```

- [ ] **Step 2: Create `GovPartner.tsx`** (slim official band; copy provisional pending spec §7.3):

```tsx
export function GovPartner() {
  return (
    <section className="border-y border-[#e3eaf3] bg-[#f4f7fb]">
      <div className="mx-auto flex max-w-[1180px] flex-col items-start gap-7 px-6 py-14 md:flex-row md:items-center md:px-12 lg:px-20">
        <div className="flex h-[84px] w-[84px] shrink-0 items-center justify-center rounded-full border-2 border-[#c7d6e8] bg-white text-[13px] font-extrabold tracking-wide text-[#33506b]">
          EC DoE
        </div>
        <div>
          <h2 className="text-[22px] font-bold tracking-tight text-slate-800">
            Feature partner to the Eastern Cape Department of Education
          </h2>
          <p className="mt-2 max-w-[640px] text-[14.5px] leading-relaxed text-slate-600">
            These results led the provincial government to make Masinyusane its featured literacy
            partner — with a signed MOU and standing weekly working sessions with senior officials to
            take what works to every district.
          </p>
          <div className="mt-3 flex flex-wrap gap-5 text-[12.5px] font-semibold text-slate-500">
            {['MOU signed', 'Weekly sessions with provincial leadership', 'Co-designing province-wide early-grade uplift'].map((m) => (
              <span key={m} className="flex items-center gap-1.5">
                <span className="text-emerald-500">&#10003;</span>{m}
              </span>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
```

- [ ] **Step 3: Create `Graduates.tsx`** (dark band; portrait wall uses gradient silhouette tiles until consented photos are supplied):

```tsx
import { PublishedStatsPayload } from '@/lib/types/impact';
import { group } from '@/lib/api/impact/published-stats';
import { Kicker, Section } from './Section';

const TILES = [
  'from-blue-500 to-blue-700', 'from-purple-500 to-purple-800', 'from-pink-500 to-pink-800',
  'from-amber-500 to-amber-800', 'from-emerald-500 to-emerald-800', 'from-indigo-500 to-indigo-800',
  'from-rose-500 to-rose-800', 'from-sky-500 to-sky-800', 'from-violet-500 to-violet-800',
];

function FaceTile({ gradient, big = false, caption }: { gradient: string; big?: boolean; caption?: string }) {
  return (
    <div className={`relative aspect-square overflow-hidden rounded-xl bg-gradient-to-br ${gradient} ${big ? 'col-span-2 row-span-2' : ''}`}>
      <div className="absolute left-1/2 top-[22%] h-[38%] w-[38%] -translate-x-1/2 rounded-full bg-white/30" />
      <div className="absolute left-1/2 top-[62%] h-1/2 w-[70%] -translate-x-1/2 rounded-t-full bg-white/30" />
      {caption && (
        <div className="absolute inset-x-2 bottom-2 rounded-md bg-[#0c0f1d]/60 px-2 py-1 text-[10px] leading-snug text-white">
          {caption}
        </div>
      )}
    </div>
  );
}

export function Graduates({ payload }: { payload: PublishedStatsPayload | null }) {
  const stats = group(payload, 'graduates');
  return (
    <Section className="bg-[#0c0f1d] text-white">
      <div className="flex flex-col items-center gap-12 lg:flex-row lg:gap-16">
        <div className="flex-1">
          <Kicker>Chapter 06 · The Long Game</Kicker>
          <h2 className="text-3xl font-extrabold leading-[1.15] tracking-tight md:text-[38px]">
            Literacy at six becomes a graduation at twenty-two.
          </h2>
          <p className="mt-4 max-w-[480px] text-[16.5px] leading-relaxed text-gray-400">
            The same model — local people, real investment, relentless follow-through — has put
            hundreds of young people from these communities through university.{' '}
            <b className="text-gray-200">Many now lead the programmes measured on this page.</b>
          </p>
          {stats.length > 0 && (
            <div className="mt-7 flex gap-12">
              {stats.map((s) => (
                <div key={s.key}>
                  <div className="bg-gradient-to-r from-blue-400 to-pink-400 bg-clip-text text-[44px] font-extrabold text-transparent">
                    {s.value}
                  </div>
                  <div className="mt-0.5 text-[13px] text-gray-500">{s.label}</div>
                </div>
              ))}
            </div>
          )}
          <a href="/programs/top-learners"
             className="mt-8 inline-block rounded-xl border border-white/25 px-6 py-3 text-[14.5px] font-semibold text-white">
            Meet the graduates &rarr;
          </a>
        </div>
        <div className="grid w-full flex-1 grid-cols-4 gap-2.5">
          <FaceTile gradient={TILES[0]} big caption="Sive M. — BCom 2024, now a Masi numeracy mentor" />
          {TILES.slice(1).map((g) => <FaceTile key={g} gradient={g} />)}
        </div>
      </div>
    </Section>
  );
}
```

- [ ] **Step 4: Lint + commit**

```bash
pnpm lint
git add src/components/impact/dashboard
git commit -m "Add scale story, government partner and graduates sections"
```

### Task 14: Frontend — page assembly

**Files:** Modify `src/app/impact/page.tsx` (full replacement)

Section order is the spec's §3 order — do not reorder: Hero → ArgumentChain → ClassroomLights → EcdParity → ChildProfile → NumeracySnapshot → ScaleStory → GovPartner → Graduates → HowWeKnow → MoreResults → GoDeeper → Footer. Light/dark rhythm: white, slate, **dark**, white, warm, slate, **dark**, gov-blue, **dark**, white, white, slate.

- [ ] **Step 1: Replace `src/app/impact/page.tsx`:**

```tsx
import type { Metadata } from 'next';
import Footer from '@/components/layout/Footer';
import { getPublishedStats } from '@/lib/api/impact/published-stats';
import { HeroSection } from '@/components/impact/dashboard/HeroSection';
import { ArgumentChain } from '@/components/impact/dashboard/ArgumentChain';
import { ClassroomLights } from '@/components/impact/dashboard/ClassroomLights';
import { EcdParity } from '@/components/impact/dashboard/EcdParity';
import { ChildProfile } from '@/components/impact/dashboard/ChildProfile';
import { NumeracySnapshot } from '@/components/impact/dashboard/NumeracySnapshot';
import { ScaleStory } from '@/components/impact/dashboard/ScaleStory';
import { GovPartner } from '@/components/impact/dashboard/GovPartner';
import { Graduates } from '@/components/impact/dashboard/Graduates';
import { HowWeKnow } from '@/components/impact/dashboard/HowWeKnow';
import { MoreResults } from '@/components/impact/dashboard/MoreResults';
import { GoDeeper } from '@/components/impact/dashboard/GoDeeper';

export const metadata: Metadata = {
  title: 'Our Impact in Data | Masinyusane',
  description:
    'Children on Masinyusane programmes perform as much as two grade levels ahead of comparison groups. Daily sessions, formal assessments and mentor visits measure every child.',
};

export default async function ImpactPage() {
  const payload = await getPublishedStats();
  return (
    <div className="min-h-screen bg-white">
      <HeroSection payload={payload} />
      <ArgumentChain payload={payload} />
      <ClassroomLights payload={payload} />
      <EcdParity payload={payload} />
      <ChildProfile />
      <NumeracySnapshot payload={payload} />
      <ScaleStory />
      <GovPartner />
      <Graduates payload={payload} />
      <HowWeKnow />
      <MoreResults payload={payload} />
      <GoDeeper />
      <Footer />
    </div>
  );
}
```

- [ ] **Step 2: Full verification.** Backend running (`python manage.py runserver`), then `pnpm dev`, open `http://localhost:3000/impact`:
  - All 12 sections render in order; numbers appear (seeded values).
  - Scroll the dark section slowly: pin + four beats + staggered lights + payoff.
  - Stop the backend, hard-refresh: page still renders (cached or number-less), never crashes.
  - macOS System Settings → Accessibility → Display → Reduce Motion ON → classroom section renders static final state.
  - Resize to 375px width: sections stack, no horizontal scrollbar, classrooms stack vertically.

- [ ] **Step 3: Build gate**

Run: `pnpm lint && pnpm build`
Expected: both pass.

- [ ] **Step 4: Commit**

```bash
git add src/app/impact/page.tsx
git commit -m "Rebuild /impact/ as donor-facing impact dashboard"
```

### Task 15: Visual QA against the mockup

- [ ] **Step 1:** Open `documentation/impact-dashboard-mockup-v5.html` (backend repo) and `http://localhost:3000/impact` side by side. Compare each section: spacing rhythm, type scale, gradient usage, dark-band colors, panel shadows. Fix discrepancies — the mockup wins.
- [ ] **Step 2:** Screenshot each section (any tool) and attach to the PR/handoff notes.
- [ ] **Step 3:** Final commit of any QA fixes:

```bash
git add -A src/components/impact/dashboard src/app/impact
git commit -m "Visual QA fixes against approved mockup"
```

---

## Self-review (done at plan-writing time)

- **Spec coverage:** §3.1–3.12 → Tasks 7–14 (all twelve sections); §5.1 → Tasks 1–4; §5.2 → Tasks 5–14; §5.3 → MethodologyNote + seed provenance; §6 → null-tolerant fetch + missing-key-renders-nothing. Measurement page intentionally excluded (separate spec). Map ships stylized (spec §7.9 unresolved); MapLibre upgrade is a follow-up task once coordinates are audited.
- **Placeholders:** none — all code complete; provisional *content* is flagged via `PROVISIONAL` methodology notes and visible "Illustrative profile" labels, which are deliberate governance features, not plan gaps.
- **Type consistency:** `PublishedStat`/`PublishedStatsPayload` shapes match between Django view (Task 3), seed (Task 4), and TS types (Task 5); `pick`/`group` helpers used consistently; `KidVariant` values consistent across KidFigure/IconArray/ClassroomLights.
