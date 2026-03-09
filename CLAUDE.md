# Backend - Django REST Framework API

Django REST Framework backend for Masinyusane (MASI). Serves the Next.js frontend at `https://github.com/JimMcKeown17/masi-web-nextjs`.

**Local path:** `/Users/jimmckeown/Development/Masi_Website_2026/backend/Masi Web Main/`

# Coding Standards

1. Keep it simple — no over-engineering, no unnecessary defensive programming
2. Backend-first: aggregate data server-side, never make the frontend fetch 100+ records to process
3. Be concise. No emojis ever.
4. When hitting issues, identify root cause before fixing. Prove with evidence.

## Development

```bash
source venv/bin/activate
python manage.py runserver        # http://localhost:8000
python manage.py makemigrations
python manage.py migrate
python manage.py test api         # run tests
```

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
│   ├── recent_visits.py
│   ├── info.py
│   └── lookups.py
├── urls.py          # API routing
├── authentication.py # Clerk JWT auth
└── tests.py         # Tests live here (or tests/ folder)
core/                # Core utilities
dashboards/          # Dashboard logic
pages/               # Public pages
```

## Authentication

Clerk JWT — all protected endpoints require:
```
Authorization: Bearer <clerk_jwt_token>
```

The `ClerkAuthentication` class validates tokens via Clerk JWKS, then creates/updates the Django user automatically.

Public endpoints use `AllowAny`. Protected endpoints use `IsAuthenticated`.

## Key Models

| Model | Description |
|---|---|
| `School` | Sites where programs operate (lat/lon, type, active status) |
| `Youth` | Literacy coaches / youth employees |
| `Children` | Child learners at schools |
| `MentorVisit` | Mentor visits to youth at schools |
| `YeboVisit` | Yebo program visits |
| `NumeracyVisit` | Numeracy program visits |
| `ThousandStoriesVisit` | 1000 Stories program visits |
| `Session` | Program sessions |

## Adding a New Endpoint

1. Add view in `api/views/<relevant_file>.py`
2. Register URL in `api/urls.py`
3. Add test in `api/tests.py` (or `api/tests/`)

**Pattern — aggregated endpoint (preferred over raw list):**
```python
# api/views/dashboard.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count

class VisitFrequencyView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = (
            MentorVisit.objects
            .values('visit_date__month')
            .annotate(count=Count('id'))
            .order_by('visit_date__month')
        )
        return Response(list(data))
```

```python
# api/urls.py
path('visit-frequency/', VisitFrequencyView.as_view()),
```

## Testing

Tests live in `api/tests.py` (or split into `api/tests/` as it grows).

```bash
python manage.py test api          # run all api tests
python manage.py test api.tests.TestVisitStats  # specific test
```

Keep tests focused and minimal — test the endpoint contract, not Django internals.

```python
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient

class VisitFrequencyTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user('test', password='test')
        self.client.force_authenticate(user=self.user)

    def test_returns_aggregated_data(self):
        response = self.client.get('/api/visit-frequency/')
        self.assertEqual(response.status_code, 200)
```

## Backend-First Rule

- Aggregate on the backend, return summaries to the frontend
- Frontend fetches pre-computed data, not raw records

```
❌ Frontend fetches 1000 visit records and counts them
✅ Backend returns { "total_visits": 1000, "this_month": 87 }
```

## Environment Variables

```
SECRET_KEY=
DEBUG=
DATABASE_URL=           # PostgreSQL connection string (prod)
CLERK_SECRET_KEY=
ALLOWED_HOSTS=
CORS_ALLOWED_ORIGINS=   # Next.js frontend origin
GCS_BUCKET_NAME=        # Google Cloud Storage
```
