# Backend - Django REST Framework API

Django REST Framework backend for Masinyusane (MASI). Serves the Next.js frontend at `https://github.com/JimMcKeown17/masi-web-nextjs`.

**Local path:** `/Users/jimmckeown/Development/Masi_Website_2026/backend/Masi Web Main/`

# Coding Standards

1. Keep it simple — no over-engineering, no unnecessary defensive programming
2. Backend-first: aggregate data server-side, never make the frontend fetch 100+ records to process
3. Be concise. No emojis ever.
4. When hitting issues, identify root cause before fixing. Prove with evidence.

## Development

**Always activate the venv before running any `python` or `manage.py` command:**
```bash
source venv/bin/activate
```

**Start/stop the server:**
```bash
./scripts/start.sh               # activates venv + runs server
./scripts/stop.sh                # kills the running server
```

**Common commands (venv must be active):**
```bash
python manage.py runserver        # http://localhost:8000
python manage.py makemigrations
python manage.py migrate
python manage.py test api         # run tests
```

## Database: Local vs Production

`.env` points `DATABASE_URL` to local Postgres (`localhost:5432/masi_db`) by default. All `manage.py` commands hit the **local** database.

**To run against production (rare, be careful):**
```bash
./scripts/prod_manage.sh migrate              # prompts for confirmation
./scripts/prod_manage.sh sync_airtable_children
```

**Rule:** develop and test locally. Only use `prod_manage.sh` for deploying migrations or running syncs that must target prod.

## Tech Stack

- **Framework:** Django 5.1+ + Django REST Framework
- **Database:** PostgreSQL (production) / SQLite3 (development)
- **Auth:** Clerk JWT (`api/authentication.py`)
- **API Docs:** drf-spectacular (OpenAPI/Swagger at `/api/schema/swagger-ui/`)
- **CORS:** django-cors-headers
- **Static/Media:** WhiteNoise + Google Cloud Storage

## URLs

- **Dev:** `http://localhost:8000`
- **Prod:** `https://masi-website-main.onrender.com`
- **All API endpoints:** prefixed with `/api/`

## Directory Structure

```
masi_website/        # Django project config (settings, urls, wsgi)
api/
├── models.py        # All DB models
├── serializers.py   # DRF serializers
├── views/           # API views (split by domain)
│   ├── dashboard.py
│   ├── mentor_visits.py
│   ├── yebo_visits.py
│   ├── numeracy_visits.py
│   ├── thousand_stories_visits.py
│   ├── youth_sessions.py
│   ├── recent_visits.py
│   ├── etl_preview.py
│   ├── info.py
│   └── lookups.py
├── management/commands/  # Airtable sync & data import commands
├── urls.py          # API routing
├── authentication.py # Clerk JWT auth
└── tests.py         # Tests live here (or tests/ folder)
core/                # Core utilities
dashboards/          # Dashboard logic
pages/               # Public pages
scripts/             # Shell scripts (start.sh, stop.sh) & utilities
```

## Authentication

Clerk JWT — all protected endpoints require:
```
Authorization: Bearer <clerk_jwt_token>
```

The `ClerkAuthentication` class validates tokens via Clerk JWKS, then creates/updates the Django user automatically.

Public endpoints use `AllowAny`. Protected endpoints use `IsAuthenticated`.


## Testing

Tests live in `api/tests.py` (or split into `api/tests/` as it grows).

```bash
python manage.py test api          # run all api tests
python manage.py test api.tests.TestVisitStats  # specific test
```

Keep tests focused and minimal — test the endpoint contract, not Django internals.


## Airtable Sync (Management Commands)

Data flows from Airtable into the local database via management commands in `api/management/commands/`.

**Twice daily:**
```bash
python manage.py sync_airtable_literacy_sessions_2026
python manage.py sync_airtable_numeracy_sessions_2026
```

**Once daily (Render cron job):**
```bash
python manage.py sync_airtable_children
python manage.py sync_airtable_schools
python manage.py sync_airtable_youth
```

**Sync pattern:** All sync commands use `airtable_id` as the upsert key. Identity fields (`employee_id`, `youth_uid`) should not be in `bulk_update`'s `update_fields` — they are set on creation only. Orphan handling differs by table type:
- **Canonical dimension syncs** (children/schools/youth): records deleted from Airtable become orphans in the DB — auto-delete orphans before upserting, or orphans with unique-constrained fields (e.g. `employee_id`) will block new records.
- **2026 fact-table syncs** (literacy/numeracy assessments, on-the-programme roster): guarded soft-retirement instead — `is_active`/`last_seen_at`, never hard-delete, retire-delta guard with `--allow-retire`. Mirror `sync_airtable_literacy_assessments_2026.py`; the parquet export's freshness gates read the sync log's `retire_skipped`/`dup_uid_skipped` details keys and fail closed on them.

**Pipeline docs (read before adding/changing a sync, model, or export):**
- `documentation/etl_data_architecture_plan.md` — strategic roadmap: raw/canonical/reporting layers, canonical-key strategy, phased plan (assessments are Phase 4).
- `documentation/airtable_pipeline_sync.md` — operational companion: current sync convention, the as-verified Airtable/Postgres state (base/table IDs, join keys, known data-quality traps), outbound serving (DRF, internal export, parquet snapshot to the Streamlit portal), and the 2026 midline literacy assessments pipeline. Note the verified caveats there (e.g. `2026 On The Programme.All Sessions Count v2` is not a reliable session total; canonical entities are fragmented across Airtable bases).

## Backend-First Rule

- Aggregate on the backend, return summaries to the frontend
- Frontend fetches pre-computed data, not raw records

```
❌ Frontend fetches 1000 visit records and counts them
✅ Backend returns { "total_visits": 1000, "this_month": 87 }
```
