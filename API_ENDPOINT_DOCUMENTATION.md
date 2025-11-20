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

This API provides comprehensive endpoints for managing four educational programs:
1. **MASI Literacy** - Core literacy coaching program
2. **Yebo** - Paired reading program
3. **1000 Stories** - Library and story time program
4. **Numeracy** - Math skills development program

All endpoints follow RESTful conventions and support standard CRUD operations where applicable. The API is designed to support both data collection (visit submissions) and analytics (dashboard summaries and filtered queries).

