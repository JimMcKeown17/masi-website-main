# Django Backend Refactoring Guide

**Last Updated:** January 2026
**Purpose:** Major architectural improvements and best practices before Next.js v2 launch

This document outlines prioritized refactoring opportunities for the Django backend. Focus is on major architectural changes, not minor style fixes.

---

## Table of Contents
- [Critical Priority](#critical-priority-security-performance-maintainability)
- [High Priority](#high-priority-architecture-scalability)
- [Medium Priority](#medium-priority-code-quality-best-practices)
- [Implementation Timeline](#implementation-timeline)

---

## CRITICAL PRIORITY (Security, Performance, Maintainability)

### 1. SECURITY: Exposed Secrets in .env File ⚠️

**Location:** `.env` file in project root

**Issue:** Production credentials are committed to version control:
- Database passwords (RDS_PASSWORD, AIRTABLE_API_KEY)
- API keys (CLERK_SECRET_KEY, GOOGLE_CLIENT_ID)
- Django SECRET_KEY
- Superuser credentials

**Impact:** Critical security vulnerability. Anyone with repo access has production credentials.

**Action Items:**
```bash
# 1. Add to .gitignore immediately
echo ".env" >> .gitignore
echo ".env.local" >> .gitignore

# 2. Create template file
cp .env .env.example
# Remove all actual secrets from .env.example

# 3. Rotate ALL exposed credentials:
# - New Django SECRET_KEY
# - New CLERK_SECRET_KEY
# - New database password
# - New Airtable API key
# - New Google OAuth credentials

# 4. Use environment-specific secrets
# Option A: Render's environment variables (recommended)
# Option B: AWS Secrets Manager
# Option C: HashiCorp Vault
```

---

### 2. ARCHITECTURE: Model Duplication Between Apps

**Location:**
- `api/models.py` (999 lines - all models defined here)
- `dashboards/models.py` (just re-exports from api)

**Issue:** Confusing model ownership pattern:
```python
# dashboards/models.py
from api.models import School, MentorVisit, Youth, Child, Mentor, Session, AirtableSyncLog
```

**Impact:** Unclear model ownership, risk of future duplication.

**Refactor Plan:**
```python
# Option 1: Create dedicated models app
# models/
#   __init__.py
#   schools.py
#   people.py (Youth, Child, Mentor)
#   visits.py (MentorVisit, YeboVisit, ThousandStoriesVisit, NumeracyVisit)
#   assessments.py (WELA_assessments, Assessment2025)
#   sessions.py (Session, LiteracySession, NumeracySessionChild)
#   sync.py (AirtableSyncLog)

# Option 2: Keep in api/ but split into submodules
# api/models/
#   __init__.py (re-export all)
#   [same structure as above]

# Then update all imports:
# from api.models import School  →  from models.schools import School
```

**Migration Strategy:**
1. Create new module structure
2. Move model definitions (copy, don't cut)
3. Update all imports across codebase
4. Create migration to ensure no table renames
5. Test thoroughly
6. Remove old model files

---

### 3. PERFORMANCE: N+1 Query Issues

**Location:** Throughout `dashboards/views.py` and API views

**Issue:** Missing `select_related` and `prefetch_related` on querysets that access related objects.

**Example Problem:**
```python
# dashboards/views.py:259
mentor_ids = set()
mentor_ids.update(MentorVisit.objects.values_list('mentor_id', flat=True))
# Later accessing mentor.first_name triggers N queries
mentors = User.objects.filter(id__in=mentor_ids).distinct()
for mentor in mentors:
    print(mentor.first_name)  # N+1 query here
```

**Fix Examples:**
```python
# API Views - add select_related for ForeignKey
class MentorVisitListCreateAPIView(generics.ListCreateAPIView):
    def get_queryset(self):
        return MentorVisit.objects.select_related(
            'mentor',
            'school'
        ).prefetch_related(
            'mentor__profile'
        ).all()

# Dashboard Views - prefetch related collections
mentors = User.objects.filter(
    id__in=mentor_ids
).select_related(
    'profile'
).prefetch_related(
    'mentorvisit_set',
    'yebovisit_set'
).distinct()

# Serializers - optimize nested serializers
class MentorVisitSerializer(serializers.ModelSerializer):
    mentor_name = serializers.CharField(source='mentor.get_full_name', read_only=True)
    school_name = serializers.CharField(source='school.name', read_only=True)

    class Meta:
        model = MentorVisit
        fields = '__all__'
```

**Testing:**
```python
# Use Django Debug Toolbar or:
from django.db import connection
from django.test.utils import override_settings

@override_settings(DEBUG=True)
def test_query_count():
    with connection.queries:
        queryset = MentorVisit.objects.select_related('mentor', 'school')
        list(queryset[:10])
    print(f"Query count: {len(connection.queries)}")
```

---

### 4. SECURITY: Missing Granular Permission Classes

**Location:** All `api/views/` files

**Issue:** All API views use generic `IsAuthenticated` permission:
```python
class MentorVisitListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]  # Too permissive
```

**Impact:** Any authenticated user can create/update/delete any visit record.

**Refactor:**
```python
# api/permissions.py (create this file)
from rest_framework import permissions

class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    """
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any authenticated user
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions only to the owner
        return obj.mentor == request.user

class IsMentorOrAdmin(permissions.BasePermission):
    """
    Only allow mentors to create visit records.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True

        # Check if user has mentor role in UserProfile
        return (
            request.user.is_staff or
            hasattr(request.user, 'profile') and
            request.user.profile.role == 'mentor'
        )

# Then apply to views
class MentorVisitListCreateAPIView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated, IsMentorOrAdmin]

    def get_queryset(self):
        # Mentors only see their own visits
        if self.request.user.is_staff:
            return MentorVisit.objects.all()
        return MentorVisit.objects.filter(mentor=self.request.user)

class MentorVisitDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]
    queryset = MentorVisit.objects.all()
    serializer_class = MentorVisitSerializer
```

---

## HIGH PRIORITY (Architecture, Scalability)

### 5. ARCHITECTURE: Monolithic api/models.py (999 Lines)

**Location:** `api/models.py`

**Issue:** Single massive file containing 14+ model classes across different domains:
- Core models: School, Youth, Child, Mentor
- Visit models: MentorVisit, YeboVisit, ThousandStoriesVisit, NumeracyVisit
- Assessment models: WELA_assessments, Assessment2025
- Session models: Session, LiteracySession, NumeracySessionChild
- Sync models: AirtableSyncLog

**Refactor Structure:**
```
api/models/
├── __init__.py           # Import and re-export all models
├── schools.py            # School model
├── people.py             # Youth, Child, Mentor models
├── visits.py             # All visit models
├── assessments.py        # Assessment models
├── sessions.py           # Session tracking models
└── sync.py               # AirtableSyncLog

# api/models/__init__.py
from .schools import School
from .people import Youth, Child, Mentor
from .visits import MentorVisit, YeboVisit, ThousandStoriesVisit, NumeracyVisit
from .assessments import WELA_assessments, Assessment2025
from .sessions import Session, LiteracySession, NumeracySessionChild
from .sync import AirtableSyncLog

__all__ = [
    'School', 'Youth', 'Child', 'Mentor',
    'MentorVisit', 'YeboVisit', 'ThousandStoriesVisit', 'NumeracyVisit',
    'WELA_assessments', 'Assessment2025',
    'Session', 'LiteracySession', 'NumeracySessionChild',
    'AirtableSyncLog',
]
```

**Benefits:**
- Easier navigation and maintenance
- Clear domain separation
- Better testability
- Faster file loading in IDE

---

### 6. ARCHITECTURE: Deprecate Template-Based Views

**Location:**
- `pages/views.py` (14 template views for public pages)
- `dashboards/views.py` (11 template views for authenticated dashboards)

**Issue:** Duplicate functionality with Next.js frontend. Once v2 launches, these are obsolete.

**Current Template Views:**
```python
# pages/views.py - Will be replaced by Next.js
def home(request)              # → Next.js: app/page.tsx
def about(request)             # → Next.js: app/about/page.tsx
def our_team(request)          # → Next.js: app/about/our-team/page.tsx
def where_we_work(request)     # → Next.js: app/about/where-we-work/page.tsx
def apply(request)             # → Next.js: app/about/apply/page.tsx
# ... 9 more

# dashboards/views.py - Will be replaced by Next.js
def mentor_dashboard(request)  # → Next.js: app/operations/mentors/page.tsx
# ... 10 more
```

**Migration Strategy:**

**Phase 1: Mark as Deprecated (Immediate)**
```python
# pages/views.py
import warnings

def home(request):
    warnings.warn(
        "Template-based views are deprecated. Use Next.js frontend.",
        DeprecationWarning,
        stacklevel=2
    )
    return render(request, 'pages/home.html')
```

**Phase 2: Convert Logic to API Endpoints (Weeks 2-4)**
```python
# api/views/dashboard.py
@extend_schema(
    description="Get mentor dashboard statistics",
    responses={200: DashboardStatsSerializer}
)
class MentorDashboardStatsAPIView(generics.RetrieveAPIView):
    """
    Replaces dashboards.views.mentor_dashboard template view.
    Returns JSON data for Next.js frontend.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Extract business logic from template view
        mentor = request.user
        visits = MentorVisit.objects.filter(mentor=mentor)

        stats = {
            'total_visits': visits.count(),
            'this_month_visits': visits.filter(
                visit_date__gte=timezone.now().replace(day=1)
            ).count(),
            # ... more stats
        }

        return Response(stats)
```

**Phase 3: Remove Template Apps (Post-Launch)**
```bash
# After Next.js v2 is live and stable
# 1. Remove URL routes
# 2. Delete template files
# 3. Remove from INSTALLED_APPS
# 4. Delete apps entirely

INSTALLED_APPS = [
    # 'pages',        # REMOVED
    # 'dashboards',   # REMOVED
    'api',
    'core',
]
```

---

### 7. ARCHITECTURE: Missing Serializer Coverage

**Location:** `api/serializers.py` (134 lines, only 6 serializers)

**Issue:** Only 6 serializers for 14+ models. Missing serializers for:
- Youth
- Child
- Mentor
- Session
- WELA_assessments
- Assessment2025
- LiteracySession
- NumeracySessionChild

**Impact:** Next.js frontend can't access critical data models via API.

**Required Serializers:**
```python
# api/serializers.py

class YouthSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(source='school.name', read_only=True)
    mentor_name = serializers.CharField(source='mentor.user.get_full_name', read_only=True)
    age = serializers.SerializerMethodField()

    class Meta:
        model = Youth
        fields = '__all__'
        read_only_fields = ('full_name', 'age')

    def get_age(self, obj):
        return obj.age if hasattr(obj, 'age') else None

class ChildSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(source='school.name', read_only=True)
    age = serializers.SerializerMethodField()

    class Meta:
        model = Child
        fields = '__all__'

    def get_age(self, obj):
        return obj.age if hasattr(obj, 'age') else None

class Assessment2025Serializer(serializers.ModelSerializer):
    child_name = serializers.CharField(source='child.full_name', read_only=True)
    school_name = serializers.CharField(source='school.name', read_only=True)

    # Computed fields
    jan_improvement = serializers.SerializerMethodField()
    year_improvement = serializers.SerializerMethodField()

    class Meta:
        model = Assessment2025
        fields = '__all__'

    def get_jan_improvement(self, obj):
        if obj.baseline_reading and obj.jan_reading:
            return obj.jan_reading - obj.baseline_reading
        return None

    def get_year_improvement(self, obj):
        if obj.baseline_reading and obj.nov_reading:
            return obj.nov_reading - obj.baseline_reading
        return None

class SessionSerializer(serializers.ModelSerializer):
    mentor_name = serializers.CharField(source='mentor.get_full_name', read_only=True)
    school_name = serializers.CharField(source='school.name', read_only=True)

    class Meta:
        model = Session
        fields = '__all__'
```

**Then Create Corresponding Views:**
```python
# api/views/youth.py
class YouthListAPIView(generics.ListAPIView):
    serializer_class = YouthSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Youth.objects.select_related('school', 'mentor__user').all()

class YouthDetailAPIView(generics.RetrieveAPIView):
    serializer_class = YouthSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Youth.objects.select_related('school', 'mentor__user').all()

# api/urls.py
urlpatterns = [
    # ... existing
    path('youth/', views.YouthListAPIView.as_view(), name='youth-list'),
    path('youth/<int:pk>/', views.YouthDetailAPIView.as_view(), name='youth-detail'),
]
```

---

### 8. ARCHITECTURE: Inconsistent Authentication Strategy

**Location:** `masi_website/settings.py:252`

**Issue:** Confusing authentication configuration:
```python
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "django.contrib.auth.backends.ModelBackend",  # ❌ Not a DRF auth class
        "rest_framework.authentication.SessionAuthentication",  # For templates
        "api.authentication.ClerkAuthentication",  # For Next.js
    ],
}

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',  # Duplicate?
]
```

**Refactor:**
```python
# For v2 (Next.js only), simplify to:
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "api.authentication.ClerkAuthentication",  # Primary for Next.js
        "rest_framework.authentication.TokenAuthentication",  # For API clients
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

# Keep this for Django admin
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]

# Phase out SessionAuthentication once templates are removed
```

---

### 9. PERFORMANCE: Massive Dashboard View Function

**Location:** `dashboards/views.py:190-349` (159 lines)

**Issue:** `mentor_dashboard` function is 159 lines of complex logic:
- Visit filtering
- School filtering
- Mentor filtering
- Chart generation
- Template rendering

**Refactor to Service Layer:**
```python
# api/services/dashboard_service.py
class DashboardService:
    """Service layer for dashboard data aggregation."""

    def __init__(self, user):
        self.user = user

    def get_visit_stats(self, time_filter='all'):
        """Get visit statistics for user."""
        visits = self._get_filtered_visits(time_filter)

        return {
            'total': visits.count(),
            'by_type': self._count_by_type(visits),
            'by_school': self._count_by_school(visits),
        }

    def _get_filtered_visits(self, time_filter):
        queryset = MentorVisit.objects.filter(mentor=self.user)

        if time_filter == '7days':
            return queryset.filter(visit_date__gte=timezone.now() - timedelta(days=7))
        elif time_filter == '30days':
            return queryset.filter(visit_date__gte=timezone.now() - timedelta(days=30))
        # ... more filters

        return queryset

# Then use in API view
class DashboardStatsAPIView(APIView):
    def get(self, request):
        service = DashboardService(request.user)
        time_filter = request.query_params.get('time_filter', 'all')
        stats = service.get_visit_stats(time_filter)
        return Response(stats)
```

---

## MEDIUM PRIORITY (Code Quality, Best Practices)

### 10. CODE QUALITY: Duplicate Visit View Pattern

**Location:**
- `api/views/mentor_visits.py`
- `api/views/yebo_visits.py`
- `api/views/thousand_stories_visits.py`
- `api/views/numeracy_visits.py`

**Issue:** Nearly identical code in all 4 files (72 lines each):
```python
# Repeated 4x with only model/serializer differences
class [Visit]ListCreateAPIView(generics.ListCreateAPIView):
    authentication_classes = [SessionAuthentication, ClerkAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = [VisitModel].objects.all()
        time_filter = self.request.query_params.get('time_filter', 'all')
        # ... same filtering logic
```

**Refactor with Base Class:**
```python
# api/views/base_visits.py
class BaseVisitListCreateAPIView(generics.ListCreateAPIView):
    """Base view for all visit types with common filtering logic."""
    authentication_classes = [SessionAuthentication, ClerkAuthentication]
    permission_classes = [permissions.IsAuthenticated, IsMentorOrAdmin]

    def get_queryset(self):
        queryset = self.model.objects.select_related('mentor', 'school').all()

        # Mentors only see their visits
        if not self.request.user.is_staff:
            queryset = queryset.filter(mentor=self.request.user)

        # Common filtering
        queryset = self._apply_time_filter(queryset)
        queryset = self._apply_school_filter(queryset)

        return queryset

    def _apply_time_filter(self, queryset):
        time_filter = self.request.query_params.get('time_filter', 'all')

        if time_filter == '7days':
            cutoff = timezone.now() - timedelta(days=7)
            return queryset.filter(visit_date__gte=cutoff)
        elif time_filter == '30days':
            cutoff = timezone.now() - timedelta(days=30)
            return queryset.filter(visit_date__gte=cutoff)
        # ... more cases

        return queryset

    def _apply_school_filter(self, queryset):
        school_id = self.request.query_params.get('school')
        if school_id:
            return queryset.filter(school_id=school_id)
        return queryset

    def perform_create(self, serializer):
        serializer.save(mentor=self.request.user)

# Then each visit view becomes:
class MentorVisitListCreateAPIView(BaseVisitListCreateAPIView):
    model = MentorVisit
    serializer_class = MentorVisitSerializer

class YeboVisitListCreateAPIView(BaseVisitListCreateAPIView):
    model = YeboVisit
    serializer_class = YeboVisitSerializer
```

**Reduction:** 288 lines → ~100 lines (63% reduction)

---

### 11. BEST PRACTICES: Missing API Versioning

**Location:** `api/urls.py`

**Issue:** No versioning strategy in URLs:
```python
urlpatterns = [
    path('info/', views.api_info, name='api_info'),
    path('mentor-visits/', views.MentorVisitListCreateAPIView.as_view()),
]
```

**Impact:** Breaking changes will affect all API clients.

**Refactor:**
```python
# api/urls.py
from django.urls import path, include

# V1 API
v1_patterns = [
    path('info/', views.api_info, name='api_info'),
    path('mentor-visits/', views.MentorVisitListCreateAPIView.as_view(), name='mentor-visits-list'),
    path('mentor-visits/<int:pk>/', views.MentorVisitDetailAPIView.as_view(), name='mentor-visits-detail'),
    path('schools/', views.SchoolListAPIView.as_view(), name='schools-list'),
    path('youth/', views.YouthListAPIView.as_view(), name='youth-list'),
    # ... more endpoints
]

urlpatterns = [
    path('v1/', include(v1_patterns)),
]

# In frontend, update NEXT_PUBLIC_API_URL
# From: https://example.com/api/mentor-visits/
# To:   https://example.com/api/v1/mentor-visits/
```

**Future Flexibility:**
```python
# Later, you can introduce v2 with breaking changes
v2_patterns = [
    # New response format, different field names, etc.
]

urlpatterns = [
    path('v1/', include(v1_patterns)),
    path('v2/', include(v2_patterns)),  # Opt-in for clients
]
```

---

### 12. CODE QUALITY: Inconsistent Model Relationships

**Location:** `api/models.py`

**Issue:** Confusing user/mentor relationship patterns:
```python
# MentorVisit uses User directly
class MentorVisit(models.Model):
    mentor = models.ForeignKey(User, on_delete=models.CASCADE)

# But Youth uses custom Mentor model
class Youth(models.Model):
    mentor = models.ForeignKey('Mentor', on_delete=models.SET_NULL)

# And Mentor has optional User
class Mentor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, blank=True, null=True)
    first_name = models.CharField(max_length=100)  # Duplicate of User.first_name
```

**Problems:**
- Can't query `user.mentorvisit_set` consistently
- `Mentor.user` can be null (when shouldn't be)
- Duplicate name fields
- Confusing for new developers

**Recommended Standardization:**

**Option 1: User + Profile (Preferred)**
```python
# core/models.py
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=[
        ('mentor', 'Mentor'),
        ('admin', 'Admin'),
        ('staff', 'Staff'),
    ])
    phone = models.CharField(max_length=20, blank=True)
    # ... mentor-specific fields

# Update all visit models
class MentorVisit(models.Model):
    mentor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mentor_visits')
    # Assumes User has profile.role == 'mentor'

# Update Youth
class Youth(models.Model):
    mentor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='mentored_youth')
```

**Migration Path:**
```python
# 1. Create UserProfile for all mentors
for mentor in Mentor.objects.all():
    if mentor.user:
        UserProfile.objects.get_or_create(
            user=mentor.user,
            defaults={'role': 'mentor', 'phone': mentor.phone}
        )

# 2. Update ForeignKeys (data migration)
# 3. Remove old Mentor model
```

---

### 13. BEST PRACTICES: Hardcoded URLs in Code

**Location:**
- `api/authentication.py:27` (JWKS URL)
- `lib/server/user.ts:10` (Frontend API URL)

**Issue:**
```python
# Hardcoded Clerk instance URL
jwks_response = requests.get(
    "https://fancy-walleye-25.clerk.accounts.dev/.well-known/jwks.json"
)
```

**Refactor:**
```python
# settings.py
CLERK_FRONTEND_API = os.environ.get(
    'CLERK_FRONTEND_API',
    'https://fancy-walleye-25.clerk.accounts.dev'
)

# api/authentication.py
from django.conf import settings

jwks_url = f"{settings.CLERK_FRONTEND_API}/.well-known/jwks.json"
jwks_response = requests.get(jwks_url)
```

---

### 14. CODE QUALITY: Debug Print Statements in Production

**Location:** `api/authentication.py` (20+ print statements)

**Issue:**
```python
print("🔍 ClerkAuthentication.authenticate called")
print(f"🔍 Authorization header: {auth[:50]}...")
print(f"🔍 Token extracted: {token[:20]}...")
# ... 17 more
```

**Problems:**
- No log levels (can't disable in production)
- Emoji decorators unprofessional
- Not structured for log aggregation
- No context about request

**Refactor:**
```python
# api/authentication.py
import logging

logger = logging.getLogger(__name__)

class ClerkAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        logger.debug("ClerkAuthentication.authenticate called")

        auth = request.headers.get("Authorization")
        if not auth:
            logger.debug("No Authorization header found")
            return None

        if not auth.startswith("Bearer "):
            logger.warning("Invalid Authorization header format")
            return None

        token = auth.split(" ")[1]
        logger.debug(f"Extracted token: {token[:10]}...")

        try:
            decoded = jwt.decode(token, public_key, algorithms=["RS256"])
            user_id = decoded.get("sub")
            logger.info(f"Successfully authenticated user: {user_id}")
            return (user, None)
        except jwt.ExpiredSignatureError:
            logger.warning("Expired token")
            raise exceptions.AuthenticationFailed("Token has expired")
        except Exception as e:
            logger.error(f"Authentication failed: {str(e)}", exc_info=True)
            raise exceptions.AuthenticationFailed("Token validation failed")

# settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'api.authentication': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'INFO',
        },
    },
}
```

---

### 15. DATA MODEL: Duplicate Assessment Models

**Location:** `api/models.py`

**Issue:** Two nearly identical assessment models:
- `WELA_assessments` (lines 395-506) - for historical data
- `Assessment2025` (lines 627-999) - for current year

Both have Jan/June/Nov baseline/midline/endline patterns.

**Refactor Options:**

**Option 1: Single Model with Year Field**
```python
class Assessment(models.Model):
    child = models.ForeignKey(Child, on_delete=models.CASCADE)
    school = models.ForeignKey(School, on_delete=models.CASCADE)
    year = models.IntegerField()  # 2024, 2025, etc.

    # Common fields
    baseline_reading = models.IntegerField(null=True, blank=True)
    baseline_writing = models.IntegerField(null=True, blank=True)
    midline_reading = models.IntegerField(null=True, blank=True)
    midline_writing = models.IntegerField(null=True, blank=True)
    endline_reading = models.IntegerField(null=True, blank=True)
    endline_writing = models.IntegerField(null=True, blank=True)

    class Meta:
        unique_together = [['child', 'year']]
        indexes = [
            models.Index(fields=['year']),
            models.Index(fields=['child', 'year']),
        ]
```

**Option 2: Abstract Base Class**
```python
class BaseAssessment(models.Model):
    child = models.ForeignKey(Child, on_delete=models.CASCADE)
    school = models.ForeignKey(School, on_delete=models.CASCADE)
    baseline_reading = models.IntegerField(null=True, blank=True)
    # ... common fields

    class Meta:
        abstract = True

class Assessment2024(BaseAssessment):
    # Legacy table
    class Meta:
        db_table = 'WELA_assessments'

class Assessment2025(BaseAssessment):
    # Current table
    pass
```

---

### 16. CONFIGURATION: Incomplete Environment Variable Validation

**Location:** `masi_website/settings.py`

**Issue:** Some env vars validated, others not:
```python
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    raise ImproperlyConfigured('DJANGO_SECRET_KEY required')

# But these aren't checked:
CLERK_SECRET_KEY = os.environ.get('CLERK_SECRET_KEY')  # Could be None!
```

**Refactor with django-environ:**
```python
# requirements.txt
django-environ==0.11.2

# settings.py
import environ

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
    CLERK_SECRET_KEY=(str, None),
)

# Read .env file
environ.Env.read_env(BASE_DIR / '.env')

# Required settings (will raise ImproperlyConfigured if missing)
SECRET_KEY = env('DJANGO_SECRET_KEY')
DATABASE_URL = env('DATABASE_URL')
CLERK_SECRET_KEY = env('CLERK_SECRET_KEY')

# Optional settings with defaults
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS')

# Type conversion
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
```

---

### 17. BEST PRACTICES: Minimal OpenAPI Documentation

**Location:** All API views, `settings.py:264`

**Issue:** DRF Spectacular installed but minimal usage:
```python
SPECTACULAR_SETTINGS = {
    'TITLE': 'MASI API',
    'DESCRIPTION': 'API for MASI mentor visits...',
    'VERSION': '1.0.0',
}
```

No schema decorators on views = poor auto-generated docs.

**Enhance with Decorators:**
```python
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample

@extend_schema(
    summary="List mentor visits",
    description="Returns a list of mentor visits filtered by time period and school.",
    parameters=[
        OpenApiParameter(
            name='time_filter',
            type=str,
            enum=['7days', '30days', '90days', 'thisyear', 'all'],
            description='Filter visits by time period',
            required=False,
        ),
        OpenApiParameter(
            name='school',
            type=int,
            description='Filter by school ID',
            required=False,
        ),
    ],
    responses={
        200: MentorVisitSerializer(many=True),
        401: OpenApiExample(
            'Unauthorized',
            value={'detail': 'Authentication credentials were not provided.'}
        ),
    },
    tags=['visits'],
)
class MentorVisitListCreateAPIView(generics.ListCreateAPIView):
    queryset = MentorVisit.objects.all()
    serializer_class = MentorVisitSerializer
```

**Improved Settings:**
```python
SPECTACULAR_SETTINGS = {
    'TITLE': 'MASI API',
    'DESCRIPTION': 'REST API for Masinyusane mentor visit tracking and program management.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'persistAuthorization': True,
        'displayOperationId': True,
        'filter': True,
    },
    'COMPONENT_SPLIT_REQUEST': True,
    'SCHEMA_PATH_PREFIX': '/api/v1',
}
```

---

### 18. CODE ORGANIZATION: Mixed Concerns in Dashboards App

**Location:** `dashboards/` directory

**Issue:** The dashboards app contains too many different concerns:
- Template views (mentor_dashboard, etc.)
- Services (Airtable sync in `services/airtable_integration.py`)
- Chart generation (`mentor_charts.py`)
- Management commands
- Forms

**Refactor Plan:**
```
# Move Airtable services to api/
api/services/
  airtable_sync.py  (from dashboards/services/)

# Convert charts to API endpoints
api/views/
  chart_data.py  (new - returns JSON instead of HTML)

# Deprecate template views
dashboards/
  views.py  (mark for deletion post-v2 launch)

# Keep only infrastructure
core/management/commands/  (consolidate here)
```

---

### 19. TESTING: No Test Coverage

**Location:** All apps

**Issue:** Empty test files:
```python
# api/tests.py
from django.test import TestCase
# Create your tests here.
```

**Impact:** No confidence in refactoring, high risk of breaking changes.

**Test Suite Structure:**
```
api/tests/
├── __init__.py
├── test_models.py          # Model validation, methods, relationships
├── test_serializers.py     # Serializer fields, validation
├── test_views.py           # API endpoint responses, permissions
├── test_authentication.py  # Clerk JWT validation
└── test_permissions.py     # Custom permission classes

# Example: api/tests/test_views.py
from rest_framework.test import APITestCase
from django.contrib.auth import get_User_model
from api.models import MentorVisit, School

User = get_User_model()

class MentorVisitAPITestCase(APITestCase):
    def setUp(self):
        self.mentor = User.objects.create_user(
            username='testmentor',
            email='mentor@test.com',
            password='testpass123'
        )
        self.school = School.objects.create(name='Test School')

    def test_list_visits_requires_auth(self):
        """Unauthenticated users cannot list visits."""
        response = self.client.get('/api/v1/mentor-visits/')
        self.assertEqual(response.status_code, 401)

    def test_create_visit(self):
        """Mentors can create visits."""
        self.client.force_authenticate(user=self.mentor)
        data = {
            'school': self.school.id,
            'visit_date': '2026-01-08',
            'visit_type': 'literacy',
        }
        response = self.client.post('/api/v1/mentor-visits/', data)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(MentorVisit.objects.count(), 1)
```

**Priority Tests:**
1. Authentication (Clerk JWT validation)
2. Permissions (IsOwnerOrReadOnly, IsMentorOrAdmin)
3. API endpoints (CRUD operations)
4. Model validation
5. Serializer fields

---

### 20. PERFORMANCE: Missing Database Indexes

**Location:** Model definitions across `api/models.py`

**Issue:** Limited use of `db_index=True` or composite indexes. Most foreign keys and filtered fields lack indexes.

**Impact:** Slow queries as data grows, especially on:
- `visit_date` (used in all time-based filters)
- `mentor` foreign keys (used in permissions)
- `school` foreign keys (used in filtering)

**Add Indexes:**
```python
class MentorVisit(models.Model):
    mentor = models.ForeignKey(User, on_delete=models.CASCADE)
    school = models.ForeignKey(School, on_delete=models.CASCADE)
    visit_date = models.DateField()
    visit_type = models.CharField(max_length=50)

    class Meta:
        indexes = [
            # Common query patterns
            models.Index(fields=['mentor', '-visit_date']),  # Mentor timeline
            models.Index(fields=['school', '-visit_date']),  # School timeline
            models.Index(fields=['-visit_date']),            # Recent visits
            models.Index(fields=['visit_type', '-visit_date']), # Type breakdown
        ]
        # Or use composite index
        index_together = [
            ['mentor', 'visit_date'],
            ['school', 'visit_date'],
        ]

class Assessment2025(models.Model):
    # ... fields

    class Meta:
        indexes = [
            models.Index(fields=['mcode']),  # ✅ Already exists
            models.Index(fields=['school']), # ✅ Already exists
            models.Index(fields=['child']),  # Add this
            models.Index(fields=['school', 'baseline_reading']),  # For aggregations
        ]
```

**Test Impact:**
```python
# Use Django Debug Toolbar or:
from django.db import connection
from django.test.utils import override_settings

@override_settings(DEBUG=True)
def analyze_query():
    from django.db import connection
    # Before adding index
    list(MentorVisit.objects.filter(mentor=user, visit_date__gte='2026-01-01'))
    print(f"Queries: {len(connection.queries)}")
    for query in connection.queries:
        print(query['sql'])
```

---

## Implementation Timeline

### Week 1: Critical Security & Performance
- [ ] Secure .env file, add to .gitignore, rotate credentials
- [ ] Add granular permission classes to API views
- [ ] Implement N+1 query optimizations (select_related/prefetch_related)
- [ ] Replace print statements with proper logging

**Deliverable:** Secure, performant API ready for v2 launch

---

### Weeks 2-3: Architecture Foundation
- [ ] Split monolithic `api/models.py` into domain modules
- [ ] Create base view class for visit endpoints (reduce duplication)
- [ ] Add API versioning (v1/ prefix)
- [ ] Create missing serializers (Youth, Child, Assessment2025, etc.)
- [ ] Add database indexes to frequently queried fields

**Deliverable:** Clean, maintainable codebase structure

---

### Weeks 4-5: API Expansion
- [ ] Mark template views as deprecated
- [ ] Convert dashboard logic to API endpoints (statistics, charts)
- [ ] Implement comprehensive OpenAPI documentation
- [ ] Standardize user/mentor relationship pattern
- [ ] Create service layer for business logic

**Deliverable:** Complete REST API replacing template functionality

---

### Weeks 6-8: Quality & Testing
- [ ] Create comprehensive test suite (models, views, auth)
- [ ] Achieve 80%+ code coverage
- [ ] Consolidate duplicate assessment models
- [ ] Implement environment variable validation (django-environ)
- [ ] Performance audit and optimization

**Deliverable:** Well-tested, production-ready backend

---

### Weeks 9-12: Deprecation & Cleanup
- [ ] Launch Next.js v2 frontend
- [ ] Monitor v2 for stability (2-4 weeks)
- [ ] Remove deprecated template apps (pages, dashboards)
- [ ] Clean up unused code and dependencies
- [ ] Final security audit
- [ ] Update documentation

**Deliverable:** Lean, modern Django REST API

---

## Success Metrics

### Code Quality
- [ ] Lines of code reduced by 30%+
- [ ] Test coverage >80%
- [ ] No security vulnerabilities (Bandit scan)
- [ ] No N+1 queries in critical paths

### Performance
- [ ] API response time <200ms (p95)
- [ ] Database query count reduced 50%+
- [ ] Successful load testing (100+ concurrent users)

### Maintainability
- [ ] Clear separation of concerns (models, views, services)
- [ ] Consistent patterns across codebase
- [ ] Comprehensive API documentation
- [ ] Developer onboarding time <1 day

---

## Notes

**Breaking Changes:** This refactoring includes breaking changes (API versioning, model consolidation). Plan migration carefully.

**Testing:** Test thoroughly in staging before production deployment.

**Documentation:** Update frontend integration docs after each phase.

**Team Coordination:** Coordinate with frontend team when changing API contracts.

---

**Last Updated:** January 8, 2026
**Contact:** Backend refactoring questions → Claude Code or team lead
