# MASI Web API Endpoint Documentation

## Base URL
All API endpoints are prefixed with `/api/`

## Authentication
All endpoints require authentication using **ClerkAuthentication** or **SessionAuthentication**.
- Each request must include valid authentication credentials
- Users must be authenticated to access any endpoint

---

## Table of Contents
1. [Information & User Endpoints](#information--user-endpoints)
2. [Mentor Visit Endpoints (MASI Literacy)](#mentor-visit-endpoints-masi-literacy)
3. [Yebo Visit Endpoints](#yebo-visit-endpoints)
4. [1000 Stories Visit Endpoints](#1000-stories-visit-endpoints)
5. [Numeracy Visit Endpoints](#numeracy-visit-endpoints)
6. [Lookup/Helper Endpoints](#lookuphelper-endpoints)
7. [Dashboard Endpoints](#dashboard-endpoints)
8. [Canonical Data Model](#canonical-data-model)
9. [ETL Status & Preview Endpoints](#etl-status--preview-endpoints)
10. [2026 Session Tables](#2026-session-tables)

---

## Information & User Endpoints

### 1. API Information
**Endpoint:** `GET /api/info/`  
**Authentication:** Required (ClerkAuthentication)

**Purpose:** Get basic API information and list of available endpoints.

**Response:**
```json
{
  "message": "MASI API v1.0",
  "endpoints": {
    "mentor_visits": "/api/mentor-visits/",
    "mentor_visit_detail": "/api/mentor-visits/{id}/",
    "yebo_visits": "/api/yebo-visits/",
    "yebo_visit_detail": "/api/yebo-visits/{id}/",
    "thousand_stories_visits": "/api/thousand-stories-visits/",
    "thousand_stories_visit_detail": "/api/thousand-stories-visits/{id}/",
    "numeracy_visits": "/api/numeracy-visits/",
    "numeracy_visit_detail": "/api/numeracy-visits/{id}/",
    "api_info": "/api/info/",
    "me": "/api/me/"
  }
}
```

**Use Cases:**
- API discovery for frontend developers
- Quick reference for available endpoints
- API version verification

---

### 2. Current User Information
**Endpoint:** `GET /api/me/`  
**Authentication:** Required (ClerkAuthentication)

**Purpose:** Get information about the currently authenticated user.

**Response:**
```json
{
  "email": "user@example.com",
  "role": "ADMIN",
  "first_name": "John",
  "last_name": "Doe",
  "username": "johndoe"
}
```

**Use Cases:**
- Display user profile information in the frontend
- Determine user permissions/role for conditional UI rendering
- Verify authentication status
- Personalize user experience

---

## Mentor Visit Endpoints (MASI Literacy)

### 3. List/Create Mentor Visits
**Endpoint:** `GET /api/mentor-visits/` | `POST /api/mentor-visits/`  
**Authentication:** Required (SessionAuthentication or ClerkAuthentication)

**GET - List all mentor visits**

**Query Parameters:**
- `time_filter` (optional): Filter by time period
  - `7days` - Last 7 days
  - `30days` - Last 30 days
  - `90days` - Last 90 days
  - `thisyear` - Current year
  - `all` (default) - All visits
- `school` (optional): Filter by school ID
- `mentor` (optional): Filter by mentor user ID

**Response:**
```json
[
  {
    "id": 1,
    "mentor": {
      "id": 5,
      "username": "johndoe",
      "first_name": "John",
      "last_name": "Doe",
      "email": "john@example.com"
    },
    "school": {
      "id": 10,
      "name": "Sunshine Primary School",
      "type": "Primary School",
      "city": "Cape Town",
      "address": "123 Main St",
      "contact_phone": "021-123-4567",
      "contact_email": "school@example.com"
    },
    "visit_date": "2024-11-15",
    "letter_trackers_correct": true,
    "reading_trackers_correct": true,
    "sessions_correct": true,
    "admin_correct": false,
    "quality_rating": 8,
    "supplies_needed": "More reading books needed",
    "commentary": "Great progress with letter recognition",
    "created_at": "2024-11-15T10:30:00Z",
    "updated_at": "2024-11-15T10:30:00Z"
  }
]
```

**POST - Create new mentor visit**

**Request Body:**
```json
{
  "school_id": 10,
  "visit_date": "2024-11-20",
  "letter_trackers_correct": true,
  "reading_trackers_correct": true,
  "sessions_correct": true,
  "admin_correct": true,
  "quality_rating": 9,
  "supplies_needed": "Pencils and erasers",
  "commentary": "Excellent session today"
}
```

**Note:** The `mentor` field is automatically set to the authenticated user.

**Use Cases:**
- **Frontend List View:** Display all mentor visits with filtering options
- **Visit Form:** Submit new mentor visit observations
- **Analytics Dashboard:** Show filtered visits by time period or school
- **Reporting:** Generate reports on mentor activities
- **School Tracking:** Monitor specific school visits

---

### 4. Retrieve/Update/Delete Specific Mentor Visit
**Endpoint:** `GET /api/mentor-visits/{id}/` | `PUT /api/mentor-visits/{id}/` | `PATCH /api/mentor-visits/{id}/` | `DELETE /api/mentor-visits/{id}/`  
**Authentication:** Required (SessionAuthentication or ClerkAuthentication)

**GET - Retrieve a specific visit**

**Response:** Same structure as single item in list response

**PUT/PATCH - Update a visit**

**Request Body:** Same as POST, but all fields optional for PATCH

**DELETE - Delete a visit**

**Response:** `204 No Content`

**Use Cases:**
- **View Details:** Display full details of a specific visit
- **Edit Visit:** Allow mentors to correct or update their submissions
- **Delete Visit:** Remove erroneous visits
- **Visit History:** Track changes to visit records

---

## Yebo Visit Endpoints

### 5. List/Create Yebo Visits
**Endpoint:** `GET /api/yebo-visits/` | `POST /api/yebo-visits/`  
**Authentication:** Required (SessionAuthentication or ClerkAuthentication)

**GET - List all Yebo visits**

**Query Parameters:**
- `time_filter` (optional): `7days`, `30days`, `90days`, `thisyear`, `all` (default)
- `school` (optional): Filter by school ID
- `mentor` (optional): Filter by mentor user ID

**Response:**
```json
[
  {
    "id": 1,
    "mentor": { /* User object */ },
    "school": { /* School object */ },
    "visit_date": "2024-11-15",
    "paired_reading_took_place": true,
    "paired_reading_tracking_updated": true,
    "afternoon_session_quality": 8,
    "commentary": "Students engaged well with paired reading",
    "created_at": "2024-11-15T14:30:00Z",
    "updated_at": "2024-11-15T14:30:00Z"
  }
]
```

**POST - Create new Yebo visit**

**Request Body:**
```json
{
  "school_id": 10,
  "visit_date": "2024-11-20",
  "paired_reading_took_place": true,
  "paired_reading_tracking_updated": true,
  "afternoon_session_quality": 9,
  "commentary": "Excellent paired reading session"
}
```

**Use Cases:**
- **Yebo Program Monitoring:** Track paired reading program activities
- **Quality Assessment:** Monitor afternoon session quality across schools
- **Compliance Tracking:** Ensure tracking sheets are kept up to date
- **Program Dashboard:** Display Yebo-specific metrics

---

### 6. Retrieve/Update/Delete Specific Yebo Visit
**Endpoint:** `GET /api/yebo-visits/{id}/` | `PUT /api/yebo-visits/{id}/` | `PATCH /api/yebo-visits/{id}/` | `DELETE /api/yebo-visits/{id}/`  
**Authentication:** Required (SessionAuthentication or ClerkAuthentication)

**Use Cases:**
- Same as Mentor Visits, but for Yebo program

---

## 1000 Stories Visit Endpoints

### 7. List/Create 1000 Stories Visits
**Endpoint:** `GET /api/thousand-stories-visits/` | `POST /api/thousand-stories-visits/`  
**Authentication:** Required (SessionAuthentication or ClerkAuthentication)

**GET - List all 1000 Stories visits**

**Query Parameters:**
- `time_filter` (optional): `7days`, `30days`, `90days`, `thisyear`, `all` (default)
- `school` (optional): Filter by school ID
- `mentor` (optional): Filter by mentor user ID

**Response:**
```json
[
  {
    "id": 1,
    "mentor": { /* User object */ },
    "school": { /* School object */ },
    "visit_date": "2024-11-15",
    "library_neat_and_tidy": true,
    "tracking_sheets_up_to_date": true,
    "book_boxes_and_borrowing": true,
    "daily_target_met": true,
    "story_time_quality": 9,
    "other_comments": "Library well organized, children enthusiastic",
    "created_at": "2024-11-15T11:00:00Z",
    "updated_at": "2024-11-15T11:00:00Z"
  }
]
```

**POST - Create new 1000 Stories visit**

**Request Body:**
```json
{
  "school_id": 10,
  "visit_date": "2024-11-20",
  "library_neat_and_tidy": true,
  "tracking_sheets_up_to_date": true,
  "book_boxes_and_borrowing": true,
  "daily_target_met": true,
  "story_time_quality": 8,
  "other_comments": "Great story time session"
}
```

**Use Cases:**
- **Library Management:** Monitor library organization and maintenance
- **Reading Program Tracking:** Track progress toward daily reading targets
- **Book Circulation:** Monitor book borrowing activities
- **Story Time Quality:** Assess quality of story time sessions
- **Program Compliance:** Ensure tracking sheets are maintained

---

### 8. Retrieve/Update/Delete Specific 1000 Stories Visit
**Endpoint:** `GET /api/thousand-stories-visits/{id}/` | `PUT /api/thousand-stories-visits/{id}/` | `PATCH /api/thousand-stories-visits/{id}/` | `DELETE /api/thousand-stories-visits/{id}/`  
**Authentication:** Required (SessionAuthentication or ClerkAuthentication)

**Use Cases:**
- Same as Mentor Visits, but for 1000 Stories program

---

## Numeracy Visit Endpoints

### 9. List/Create Numeracy Visits
**Endpoint:** `GET /api/numeracy-visits/` | `POST /api/numeracy-visits/`  
**Authentication:** Required (SessionAuthentication or ClerkAuthentication)

**GET - List all Numeracy visits**

**Query Parameters:**
- `time_filter` (optional): `7days`, `30days`, `90days`, `thisyear`, `all` (default)
- `school` (optional): Filter by school ID
- `mentor` (optional): Filter by mentor user ID

**Response:**
```json
[
  {
    "id": 1,
    "mentor": { /* User object */ },
    "school": { /* School object */ },
    "visit_date": "2024-11-15",
    "numeracy_tracker_correct": true,
    "teaching_counting": true,
    "teaching_number_concepts": true,
    "teaching_patterns": false,
    "teaching_addition_subtraction": true,
    "quality_rating": 8,
    "supplies_needed": "Number cards needed",
    "commentary": "Students showing good progress with counting",
    "created_at": "2024-11-15T13:00:00Z",
    "updated_at": "2024-11-15T13:00:00Z"
  }
]
```

**POST - Create new Numeracy visit**

**Request Body:**
```json
{
  "school_id": 10,
  "visit_date": "2024-11-20",
  "numeracy_tracker_correct": true,
  "teaching_counting": true,
  "teaching_number_concepts": true,
  "teaching_patterns": true,
  "teaching_addition_subtraction": true,
  "quality_rating": 9,
  "supplies_needed": "More counting blocks",
  "commentary": "Excellent numeracy session"
}
```

**Use Cases:**
- **Numeracy Program Monitoring:** Track numeracy teaching activities
- **Curriculum Compliance:** Ensure correct topics are being taught
- **Resource Management:** Track supply needs across schools
- **Quality Assessment:** Monitor teaching quality in numeracy sessions
- **Program Planning:** Identify which numeracy concepts need more focus

---

### 10. Retrieve/Update/Delete Specific Numeracy Visit
**Endpoint:** `GET /api/numeracy-visits/{id}/` | `PUT /api/numeracy-visits/{id}/` | `PATCH /api/numeracy-visits/{id}/` | `DELETE /api/numeracy-visits/{id}/`  
**Authentication:** Required (SessionAuthentication or ClerkAuthentication)

**Use Cases:**
- Same as Mentor Visits, but for Numeracy program

---

## Lookup/Helper Endpoints

### 11. List All Schools
**Endpoint:** `GET /api/schools/`  
**Authentication:** Required (SessionAuthentication or ClerkAuthentication)

**Purpose:** Get a list of all active schools in the system.

**Response:**
```json
[
  {
    "id": 1,
    "name": "Sunshine Primary School",
    "type": "Primary School",
    "city": "Cape Town",
    "address": "123 Main St",
    "contact_phone": "021-123-4567",
    "contact_email": "school@example.com"
  },
  {
    "id": 2,
    "name": "Rainbow ECDC",
    "type": "Early Childhood Development",
    "city": "Stellenbosch",
    "address": "456 Oak Ave",
    "contact_phone": "021-987-6543",
    "contact_email": "rainbow@example.com"
  }
]
```

**Use Cases:**
- **Dropdown Menus:** Populate school selection dropdowns in visit forms
- **School Directory:** Display complete list of schools
- **Filtering:** Provide school options for filtering visit lists
- **Autocomplete:** Power school search/autocomplete features
- **Validation:** Verify school IDs before creating visits

---

### 12. List All Mentors
**Endpoint:** `GET /api/mentors/`  
**Authentication:** Required (SessionAuthentication or ClerkAuthentication)

**Purpose:** Get a list of all users who have submitted at least one visit (any type).

**Response:**
```json
[
  {
    "id": 1,
    "username": "johndoe",
    "first_name": "John",
    "last_name": "Doe",
    "email": "john@example.com"
  },
  {
    "id": 2,
    "username": "janesmith",
    "first_name": "Jane",
    "last_name": "Smith",
    "email": "jane@example.com"
  }
]
```

**Use Cases:**
- **Mentor Directory:** Display list of active mentors
- **Filtering:** Filter visits by mentor
- **Performance Tracking:** Identify active mentors
- **Assignment:** Assign mentors to schools
- **Analytics:** Track mentor activity and engagement

---

## Dashboard Endpoints

### 13. Dashboard Summary Statistics
**Endpoint:** `GET /api/dashboard-summary/`  
**Authentication:** Required (SessionAuthentication or ClerkAuthentication)

**Purpose:** Get aggregated statistics for the dashboard with optional filtering.

**Query Parameters:**
- `time_filter` (optional): `7days`, `30days`, `90days`, `thisyear`, `all` (default)
- `school` (optional): Filter by school ID
- `mentor` (optional): Filter by mentor user ID

**Response:**
```json
{
  "total_visits": 156,
  "recent_visits": 42,
  "schools_visited": 15,
  "avg_quality": 7.8,
  "literacy_visits": 65,
  "literacy_recent_visits": 18,
  "yebo_visits": 34,
  "yebo_recent_visits": 10,
  "stories_visits": 28,
  "stories_recent_visits": 8,
  "numeracy_visits": 29,
  "numeracy_recent_visits": 6
}
```

**Field Descriptions:**
- `total_visits`: Total number of all visit types within filter
- `recent_visits`: Number of visits in last 30 days (within filter)
- `schools_visited`: Number of unique schools visited
- `avg_quality`: Average quality rating for literacy visits
- `literacy_visits`: Total MASI Literacy visits
- `literacy_recent_visits`: MASI Literacy visits in last 30 days
- `yebo_visits`: Total Yebo program visits
- `yebo_recent_visits`: Yebo visits in last 30 days
- `stories_visits`: Total 1000 Stories visits
- `stories_recent_visits`: 1000 Stories visits in last 30 days
- `numeracy_visits`: Total Numeracy visits
- `numeracy_recent_visits`: Numeracy visits in last 30 days

**Use Cases:**
- **Dashboard Homepage:** Display key metrics and KPIs
- **Executive Summary:** Quick overview of program activities
- **Performance Monitoring:** Track visit frequency and quality
- **Program Comparison:** Compare activity levels across different programs
- **Trend Analysis:** Monitor recent activity vs. historical data
- **School-Specific Dashboard:** Show metrics for a specific school
- **Mentor Performance:** View individual mentor statistics
- **Filtered Analytics:** Generate reports for specific time periods

---

## Canonical Data Model

The backend maintains a set of **canonical tables** synced from Airtable. These are the source-of-truth dimension tables for the organisation. All are read-only from the frontend's perspective -- data flows in via management commands (`python manage.py sync_airtable_*`).

### Entity Relationship

```
School (326 records)
  ├── school_uid: "SCH-00283" (unique join key)
  ├── name, suburb, type, city, ...
  │
Youth (1634 records) ──FK──> School
  ├── youth_uid: "YTH-1905" (unique join key)
  ├── employee_id, full_name, employment_status, job_title, ...
  │
CanonicalChild (10704 records)
  ├── child_uid: "CH-16023" (unique join key)
  ├── mcode: 16023 (stable integer ID)
  ├── full_name, gender, school_2025, grade_2025, ...
  │
Staff (HR records -- mentors, admin, finance, etc.)
  ├── employee_number (unique)
  ├── name, gender, email, ...
```

### Fact Tables (2026 Sessions)

Session tables store one row per session and link to canonical tables via **resolved FKs**. Each session row has both the raw UID string (`youth_uid`, `school_uid`) and a resolved FK (`youth_id`, `school_id`) pointing to the canonical record.

```
LiteracySession2026 (fact table)
  ├── youth_uid: "YTH-1905"   + youth_id ──FK──> Youth
  ├── school_uid: "SCH-00283" + school_id ──FK──> School
  ├── child_uid_1: "CH-16023" + child_1_id ──FK──> CanonicalChild
  ├── child_uid_2: "CH-16566" + child_2_id ──FK──> CanonicalChild
  ├── session_date, sounds_covered_clean, blending_level, ...
  │
NumeracySession2026 (fact table)
  ├── youth_uid + youth_id ──FK──> Youth
  ├── school_uid + school_id ──FK──> School
  ├── child_uids: ["CH-16023", "CH-16024", ...] (JSON array, 3-10 children per session)
  ├── session_date, group_count_level, group_number_recognition, ...
```

**Key design decisions:**
- UID string fields are kept alongside FKs for debugging and Airtable traceability
- FKs are nullable (`SET_NULL`) -- if a canonical record is missing, the session still exists
- Numeracy child UIDs remain a JSON array (no M2M) since numeracy analysis is group-level
- FKs are resolved during Airtable sync and can be backfilled with `python manage.py resolve_session_fks`

---

## ETL Status & Preview Endpoints

These endpoints provide visibility into sync health and data quality. They are internal tooling endpoints -- use them to build admin dashboards, data quality monitors, and preview pages.

### 14. ETL Sync Status
**Endpoint:** `GET /api/etl-status/`
**Authentication:** Required (SessionAuthentication or ClerkAuthentication)

**Purpose:** Returns sync health summary for all canonical and session tables.

**Response:**
```json
{
  "tables": [
    {
      "name": "schools",
      "record_count": 326,
      "last_sync": "2026-03-10T08:00:00+00:00",
      "last_sync_records": 326
    },
    {
      "name": "youth",
      "record_count": 1634,
      "last_sync": "2026-03-10T08:05:00+00:00",
      "last_sync_records": 1634
    },
    {
      "name": "children",
      "record_count": 10704,
      "last_sync": "2026-03-10T08:10:00+00:00",
      "last_sync_records": 10704
    },
    {
      "name": "staff",
      "record_count": 45,
      "last_sync": "2026-03-10T08:15:00+00:00",
      "last_sync_records": 45
    },
    {
      "name": "literacy-2026",
      "record_count": 4416,
      "last_sync": "2026-03-15T12:00:00+00:00",
      "last_sync_records": 4416
    },
    {
      "name": "numeracy-2026",
      "record_count": 341,
      "last_sync": "2026-03-15T12:05:00+00:00",
      "last_sync_records": 341
    }
  ]
}
```

**Field descriptions:**
- `name`: Table identifier (use as `table_name` param for the preview endpoint)
- `record_count`: Current row count in the database
- `last_sync`: ISO timestamp of the most recent successful sync (null if never synced)
- `last_sync_records`: Number of records processed in that sync

**Use Cases:**
- **Status Dashboard Cards:** Show record count + last sync time per table
- **Staleness Alerts:** Flag tables where `last_sync` is older than expected
- **Sync Monitoring:** Verify syncs are running and processing expected record counts

---

### 15. ETL Table Preview
**Endpoint:** `GET /api/etl-preview/<table_name>/`
**Authentication:** Required (SessionAuthentication or ClerkAuthentication)

**Path Parameter:**
- `table_name`: One of `schools`, `youth`, `children`, `staff`, `literacy-2026`, `numeracy-2026`

**Purpose:** Returns sample rows and FK resolution stats for one table. Useful for verifying data quality and building preview UIs.

**Response (session tables -- literacy-2026, numeracy-2026):**
```json
{
  "table_name": "literacy-2026",
  "record_count": 4416,
  "orphan_stats": {
    "youth_resolved": 4416,
    "youth_orphaned": 0,
    "school_resolved": 4416,
    "school_orphaned": 0,
    "child1_resolved": 4416,
    "child1_orphaned": 0,
    "child2_resolved": 3323,
    "child2_orphaned": 1093
  },
  "sample_rows": [
    {
      "id": 1,
      "session_uid": "SES-2026-03-10-YTH-1905-SCH-00283-CH-16023",
      "session_date": "2026-03-10",
      "youth_uid": "YTH-1905",
      "youth_name": "John Smith",
      "school_uid": "SCH-00283",
      "school_name": "Sunshine Primary",
      "child_uid_1": "CH-16023",
      "child_1_name": "Thando Mkhize",
      "child_uid_2": "CH-16566",
      "child_2_name": "Sipho Ndlovu",
      "sounds_covered_clean": "s a t p",
      "blending_level": "CVC",
      "duplicate_status": "Unique",
      "overall_session_status": "Clean"
    }
  ]
}
```

**Response (canonical tables -- schools, youth, children, staff):**
```json
{
  "table_name": "youth",
  "record_count": 1634,
  "sample_rows": [
    {
      "id": 42,
      "full_name": "John Smith",
      "youth_uid": "YTH-1905",
      "employee_id": 1905,
      "employment_status": "Active",
      "job_title": "Literacy Coach"
    }
  ]
}
```

**Sample row fields per table:**

| Table | Fields |
|-------|--------|
| `schools` | `id`, `name`, `school_uid`, `suburb`, `school_number` |
| `youth` | `id`, `full_name`, `youth_uid`, `employee_id`, `employment_status`, `job_title` |
| `children` | `id`, `full_name`, `child_uid`, `mcode`, `gender`, `school_2025`, `grade_2025` |
| `staff` | `id`, `name`, `employee_number`, `gender`, `email` |
| `literacy-2026` | `id`, `session_uid`, `session_date`, `youth_uid`, `youth_name`, `school_uid`, `school_name`, `child_uid_1`, `child_1_name`, `child_uid_2`, `child_2_name`, `sounds_covered_clean`, `blending_level`, `duplicate_status`, `overall_session_status` |
| `numeracy-2026` | `id`, `session_uid`, `session_date`, `youth_uid`, `youth_name`, `school_uid`, `school_name`, `child_uids`, `children_count`, `group_count_level`, `group_number_recognition`, `duplicate_status` |

**Orphan stats** (session tables only): Shows how many session rows have resolved FKs vs. orphaned UIDs (no matching canonical record). `child2_orphaned` will be higher than other orphan counts because some literacy sessions only have one child.

**Use Cases:**
- **Data Quality Dashboard:** Show orphan stats as progress bars (resolved vs. orphaned per FK)
- **Preview Tables:** Display sample rows to verify sync data looks correct
- **Debugging:** Identify broken FK links after syncs

---

## 2026 Session Tables

### Data Model Reference

These are the full field lists for the 2026 session models. Frontend engineers building dashboards should reference these when deciding which fields to request from future API endpoints.

#### LiteracySession2026

| Field | Type | Description |
|-------|------|-------------|
| `source_airtable_id` | string | Unique Airtable record ID (upsert key) |
| `session_record` | int | Airtable auto-number |
| `session_uid` | string | Composite business key (e.g. `SES-2026-03-10-YTH-1905-SCH-00283-CH-16023`) |
| `session_date` | date | When the session took place |
| `youth_uid` | string | Youth UID string (e.g. `YTH-1905`) |
| `school_uid` | string | School UID string (e.g. `SCH-00283`) |
| `child_uid_1` | string | First child UID (e.g. `CH-16023`) |
| `child_uid_2` | string | Second child UID (nullable -- some sessions have 1 child) |
| `youth` | FK -> Youth | Resolved FK (nullable) |
| `school` | FK -> School | Resolved FK (nullable) |
| `child_1` | FK -> CanonicalChild | Resolved FK (nullable) |
| `child_2` | FK -> CanonicalChild | Resolved FK (nullable) |
| `child_names` | string | Semicolon-separated child names from Airtable |
| `sounds_covered` | string | Raw sounds text entered by LC |
| `sounds_covered_clean` | string | Normalised sounds (lowercased, punctuation removed) |
| `blending_level` | string | e.g. `CVC`, `CVCC` |
| `duplicate_status` | string | `Unique` or `Duplicate` |
| `overall_session_status` | string | `Clean` or `Needs fix` |
| `capture_delay` | int | Days between session date and capture |
| `capture_delay_flag` | string | e.g. `On Time`, `Late` |
| `duplicate_fingerprint` | string | Composite string for duplicate detection |
| `created_in_airtable` | datetime | When the record was created in Airtable |

#### NumeracySession2026

| Field | Type | Description |
|-------|------|-------------|
| `source_airtable_id` | string | Unique Airtable record ID (upsert key) |
| `session_record` | int | Airtable auto-number |
| `session_uid` | string | Composite business key |
| `session_date` | date | When the session took place |
| `youth_uid` | string | Youth UID string |
| `school_uid` | string | School UID string |
| `child_uids` | JSON array | Array of `CH-XXXXX` UIDs (3-10 children per group session) |
| `children_count` | int | Number of children in the group |
| `youth` | FK -> Youth | Resolved FK (nullable) |
| `school` | FK -> School | Resolved FK (nullable) |
| `group_count_level` | string | e.g. `31-40` (group's current counting level) |
| `group_number_recognition` | string | e.g. `Recognises 1-5` |
| `duplicate_status` | string | `Unique` or `Duplicate` |
| `overall_session_status` | string | `Clean` or `Needs fix` |
| `capture_delay` | int | Days between session date and capture |
| `capture_delay_flag` | string | e.g. `On Time`, `Late` |
| `duplicate_fingerprint` | string | Composite string for duplicate detection |
| `created_in_airtable` | date | When the record was created in Airtable |

#### CanonicalChild

| Field | Type | Description |
|-------|------|-------------|
| `source_airtable_id` | string | Airtable record ID (upsert key) |
| `child_uid` | string | `CH-XXXXX` format UID (cross-table join key) |
| `mcode` | int | Stable integer child identifier |
| `first_name` | string | |
| `surname` | string | |
| `full_name` | string | |
| `gender` | string | |
| `identity_confidence` | string | e.g. `Multi-Year Record` |
| `years_active` | JSON array | e.g. `[2024, 2025, 2026]` |
| `programme` | JSON array | e.g. `["Literacy Child"]` |
| `school_2025` | string | School name in 2025 |
| `grade_2025` | string | Grade in 2025 |

#### Youth

| Field | Type | Description |
|-------|------|-------------|
| `airtable_id` | string | Airtable record ID |
| `employee_id` | int | Unique employee number |
| `youth_uid` | string | `YTH-XXXX` format UID (cross-table join key) |
| `full_name` | string | Auto-generated from first_names + last_name |
| `first_names` | string | |
| `last_name` | string | |
| `employment_status` | string | `Active` or `Inactive` |
| `job_title` | string | |
| `school` | FK -> School | Current school placement |
| `mentor` | FK -> Mentor | Supervising mentor |
| `dob`, `age`, `gender`, `race` | various | Demographics |
| `cell_phone_number`, `email` | various | Contact info |

#### School

| Field | Type | Description |
|-------|------|-------------|
| `airtable_id` | string | Airtable record ID |
| `school_uid` | string | `SCH-XXXXX` format UID (cross-table join key) |
| `school_number` | int | Auto-increment number from Airtable |
| `name` | string | School name |
| `type` | string | `ECDC`, `Primary School`, `Secondary School`, `Other` |
| `suburb` | string | |
| `city` | string | |
| `site_type` | string | Site type from Airtable |
| `latitude`, `longitude` | decimal | Coordinates |
| `actively_working_in` | string | Whether MASI is currently active at this school |

#### Staff

| Field | Type | Description |
|-------|------|-------------|
| `source_airtable_id` | string | Airtable record ID (upsert key) |
| `employee_number` | int | Unique employee number |
| `name` | string | Full name |
| `first_names` | string | |
| `last_name` | string | |
| `gender` | string | |
| `race` | string | |
| `email` | string | |
| `cell_number` | string | |
| `date_of_birth` | date | |

---

### Frontend Integration: ETL Endpoints

```typescript
const API_URL = process.env.NEXT_PUBLIC_API_URL;

// Fetch sync status for all tables
async function getEtlStatus(token: string) {
  const res = await fetch(`${API_URL}/etl-status/`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return res.json();
}

// Fetch preview data for a specific table
async function getEtlPreview(token: string, tableName: string) {
  const res = await fetch(`${API_URL}/etl-preview/${tableName}/`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return res.json();
}
```

### Existing Frontend Implementation

The preview page is already built at `/operations/preview` in the Next.js frontend:
- **API functions:** `src/lib/api/preview/index.ts`
- **Page component:** `src/app/operations/preview/page.tsx`
- Uses SWR for data fetching, Clerk for auth, shadcn for UI (Card, Tabs, Table, Badge)

---

## Common Patterns & Best Practices

### Filtering
All visit endpoints support three common filters:
- **Time Filter:** Use `?time_filter=30days` to get recent data
- **School Filter:** Use `?school=10` to filter by school ID
- **Mentor Filter:** Use `?mentor=5` to filter by mentor user ID
- **Combine Filters:** `?time_filter=90days&school=10&mentor=5`

### Pagination
Currently, the API returns all results. Consider implementing pagination for large datasets:
- **Recommendation:** Add `?page=1&page_size=50` for future scalability

### Error Handling
All endpoints return standard HTTP status codes:
- `200 OK` - Successful GET/PUT/PATCH
- `201 Created` - Successful POST
- `204 No Content` - Successful DELETE
- `400 Bad Request` - Invalid data
- `401 Unauthorized` - Authentication required
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Resource doesn't exist
- `500 Internal Server Error` - Server error

### Data Validation
- All boolean fields default to `false`
- Quality ratings must be between 1-10
- Dates should be in ISO format (YYYY-MM-DD)
- The `mentor` field is automatically set from authenticated user on POST
- `school_id` is required when creating visits (write-only field)
- Created/updated timestamps are automatically managed

---

## Frontend Integration Examples

### Fetching Dashboard Data
```javascript
// Get dashboard summary with filters
const response = await fetch('/api/dashboard-summary/?time_filter=30days&school=10', {
  headers: {
    'Authorization': 'Bearer YOUR_TOKEN'
  }
});
const data = await response.json();
```

### Creating a New Visit
```javascript
// Submit a new mentor visit
const response = await fetch('/api/mentor-visits/', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer YOUR_TOKEN',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    school_id: 10,
    visit_date: '2024-11-20',
    letter_trackers_correct: true,
    reading_trackers_correct: true,
    sessions_correct: true,
    admin_correct: true,
    quality_rating: 8,
    supplies_needed: 'More books',
    commentary: 'Great session'
  })
});
```

### Loading Dropdown Options
```javascript
// Populate school dropdown
const schools = await fetch('/api/schools/').then(r => r.json());
const mentors = await fetch('/api/mentors/').then(r => r.json());
```

---

## Additional Resources

### Swagger/OpenAPI Documentation
Interactive API documentation is available at:
- **Schema:** `/api/schema/`
- **Swagger UI:** `/api/schema/docs/`

### Testing the API
You can test all endpoints using:
- Swagger UI (recommended for quick testing)
- Postman or similar API clients
- Browser DevTools for GET requests
- cURL commands

---

## Summary

This API serves two layers:

**1. Mentor Visit CRUD (manual data entry)**
- MASI Literacy, Yebo, 1000 Stories, Numeracy visit endpoints
- Created by mentors via frontend forms
- Supports filtering by time, school, mentor

**2. Canonical Data + 2026 Sessions (Airtable-synced, read-only)**
- Dimension tables: `School`, `Youth`, `CanonicalChild`, `Staff`
- Fact tables: `LiteracySession2026`, `NumeracySession2026`
- FK relationships resolved during sync (UIDs -> canonical records)
- ETL status and preview endpoints for monitoring and data quality
- Data flows: Airtable -> management commands -> PostgreSQL -> API -> frontend

All endpoints require Clerk or Session authentication. Visit endpoints support CRUD; canonical/session endpoints are read-only from the frontend.

