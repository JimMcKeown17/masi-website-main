# Frontend-Backend Integration Guide
## MASI Web Application Backend Documentation

This guide provides comprehensive information for frontend developers and LLMs to understand and integrate with the MASI backend system.

---

## Table of Contents
1. [Backend Architecture Overview](#backend-architecture-overview)
2. [Authentication System](#authentication-system)
3. [Database Models & Data Structure](#database-models--data-structure)
4. [API Endpoints Reference](#api-endpoints-reference)
5. [Frontend Integration Examples](#frontend-integration-examples)
6. [Environment Configuration](#environment-configuration)
7. [CORS & Security](#cors--security)
8. [Common Use Cases](#common-use-cases)

---

## Backend Architecture Overview

### Tech Stack
- **Framework:** Django 5.1+ (Python web framework)
- **API:** Django REST Framework (DRF)
- **Database:** PostgreSQL (production) / SQLite3 (development)
- **Authentication:** Clerk (JWT-based authentication)
- **API Documentation:** drf-spectacular (OpenAPI/Swagger)
- **CORS:** django-cors-headers
- **Static Files:** WhiteNoise + Google Cloud Storage (production)

### Project Structure
```
masi_website/          # Main Django project
├── settings.py        # Configuration
├── urls.py           # URL routing
└── wsgi.py           # WSGI application

api/                  # REST API application
├── models.py         # Database models
├── serializers.py    # API serializers
├── views/           # API views
├── urls.py          # API URL routing
└── authentication.py # Clerk authentication

core/                # Core functionality
dashboards/          # Dashboard logic
pages/              # Public pages
templates/          # Django templates
static/             # Static assets (CSS, JS, images)
```

### Base URLs
- **Development:** `http://localhost:8000`
- **Production:** `https://masi-website-main.onrender.com`
- **API Prefix:** All API endpoints are prefixed with `/api/`

### Key Features
- RESTful API design
- Token-based authentication (Clerk JWT)
- Comprehensive filtering and querying
- Automatic timestamp management
- Data validation and error handling
- OpenAPI/Swagger documentation

---

## Authentication System

### Overview
The backend uses **Clerk** for authentication, which provides:
- JWT-based token authentication
- User management
- SSO capabilities
- Secure session handling

### How Authentication Works

#### 1. Clerk Configuration
- **Clerk Instance:** `fancy-walleye-25.clerk.accounts.dev`
- **Authentication Class:** `api.authentication.ClerkAuthentication`
- **Token Type:** Bearer JWT tokens

#### 2. Authentication Flow

```
Frontend (Clerk)                Backend (Django)
     │                                │
     │  1. User logs in via Clerk    │
     ├───────────────────────────────>│
     │                                │
     │  2. Clerk returns JWT token    │
     │<───────────────────────────────┤
     │                                │
     │  3. Frontend includes token    │
     │     in Authorization header    │
     ├───────────────────────────────>│
     │                                │
     │  4. Backend validates token    │
     │     via Clerk JWKS             │
     │                                │
     │  5. Backend creates/updates    │
     │     Django user                │
     │                                │
     │  6. API returns data           │
     │<───────────────────────────────┤
```

#### 3. Making Authenticated Requests

**Required Headers:**
```javascript
{
  'Authorization': 'Bearer YOUR_CLERK_JWT_TOKEN',
  'Content-Type': 'application/json'
}
```

**Example with Fetch API:**
```javascript
const response = await fetch('http://localhost:8000/api/me/', {
  method: 'GET',
  headers: {
    'Authorization': `Bearer ${clerkToken}`,
    'Content-Type': 'application/json'
  }
});
const userData = await response.json();
```

**Example with Axios:**
```javascript
import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000/api',
  headers: {
    'Authorization': `Bearer ${clerkToken}`,
    'Content-Type': 'application/json'
  }
});

const { data } = await api.get('/me/');
```

#### 4. User Creation/Update
The backend automatically:
- Validates Clerk JWT tokens
- Fetches user info from Clerk API
- Creates Django user if doesn't exist
- Updates existing user info (email, name)
- Uses case-insensitive email lookup

#### 5. Environment Variables Required
```bash
CLERK_SECRET_KEY=sk_test_...  # Your Clerk secret key
```

---

## Database Models & Data Structure

### Core Models

#### 1. **School**
Represents educational institutions where programs operate.

**Fields:**
```python
{
  "id": Integer (Primary Key),
  "school_id": Integer (CSV import ID),
  "airtable_id": String (Airtable record ID),
  "name": String (max 200 chars),
  "type": String (ECDC, Primary, Secondary, Other),
  "site_type": String (from Airtable),
  "latitude": Decimal (10, 8),
  "longitude": Decimal (10, 8),
  "address": String (max 255 chars),
  "contact_phone": String (max 40 chars),
  "contact_email": Email,
  "contact_person": String (max 200 chars),
  "principal": String (max 200 chars),
  "city": String (max 100 chars),
  "actively_working_in": String (max 5 chars),
  "is_active": Boolean (default: True),
  "date_added": DateTime (auto),
  "last_updated": DateTime (auto)
}
```

**Relationships:**
- Has many: Youth, Children, Sessions, MentorVisits, YeboVisits, ThousandStoriesVisits, NumeracyVisits

**Use Cases:**
- School directory
- Visit location selection
- Geographic analysis
- Contact information management

---

#### 2. **Youth**
Represents literacy coaches/youth employees working at schools.

**Fields:**
```python
{
  "id": Integer (Primary Key),
  "airtable_id": String (Airtable record ID),
  "employee_id": Integer (unique),
  "first_names": String (max 255 chars),
  "last_name": String (max 255 chars),
  "full_name": String (auto-generated),
  
  # Demographics
  "dob": Date,
  "age": Integer (auto-calculated),
  "gender": String (Male/Female/Other),
  "race": String (Black African/Coloured/White/Indian/Asian/Other),
  
  # ID Information
  "id_type": String (RSA ID/Foreign ID/Passport),
  "rsa_id_number": String (max 50 chars),
  "foreign_id_number": String (max 50 chars),
  
  # Contact
  "cell_phone_number": String (max 50 chars),
  "email": Email,
  "emergency_number": String (max 40 chars),
  
  # Address
  "street_number": String (max 50 chars),
  "street_address": String (max 255 chars),
  "suburb_township": String (max 255 chars),
  "city_or_town": String (max 255 chars),
  "postal_code": String (max 50 chars),
  
  # Employment
  "job_title": String (max 100 chars),
  "employment_status": String (Active/Inactive),
  "start_date": Date,
  "end_date": Date,
  "reason_for_leaving": String (max 255 chars),
  "income_tax_number": String (max 50 chars),
  
  # Banking
  "bank_name": String (max 100 chars),
  "account_type": String (Savings/Current/Cheque),
  "branch_code": String (max 50 chars),
  "account_number": String (max 50 chars),
  
  # Relationships
  "school_id": ForeignKey (School),
  "mentor_id": ForeignKey (Mentor),
  
  # Timestamps
  "created_at": DateTime (auto),
  "updated_at": DateTime (auto)
}
```

**Use Cases:**
- Employee management
- HR records
- Payment processing
- Performance tracking

---

#### 3. **Child**
Represents children receiving literacy/numeracy instruction.

**Fields:**
```python
{
  "id": Integer (Primary Key),
  "airtable_id": String (Airtable record ID),
  "full_name": String (max 255 chars),
  "mcode": String (max 50 chars, unique identifier),
  "grade": String (max 50 chars),
  "on_programme": Boolean (default: True),
  "school_id": ForeignKey (School),
  "created_at": DateTime (auto),
  "updated_at": DateTime (auto)
}
```

**Relationships:**
- Belongs to: School
- Has many: Sessions, WELA_assessments

**Use Cases:**
- Student enrollment tracking
- Program participation
- Assessment linkage

---

#### 4. **Mentor**
Represents mentors who oversee youth and conduct school visits.

**Fields:**
```python
{
  "id": Integer (Primary Key),
  "user_id": OneToOne (Django User),
  "name": String (max 255 chars),
  "is_active": Boolean (default: True),
  "created_at": DateTime (auto),
  "updated_at": DateTime (auto)
}
```

**Relationships:**
- Has many: Youth, Sessions, MentorVisits

---

#### 5. **MentorVisit** (MASI Literacy Program)
Records mentor observations during school visits for the literacy program.

**Fields:**
```python
{
  "id": Integer (Primary Key),
  "mentor_id": ForeignKey (User),
  "school_id": ForeignKey (School),
  "visit_date": Date (default: today),
  
  # Observations (Boolean)
  "letter_trackers_correct": Boolean,
  "reading_trackers_correct": Boolean,
  "sessions_correct": Boolean,
  "admin_correct": Boolean,
  
  # Quality Rating
  "quality_rating": Integer (1-10),
  
  # Comments
  "supplies_needed": Text,
  "commentary": Text,
  
  # Timestamps
  "created_at": DateTime (auto),
  "updated_at": DateTime (auto)
}
```

**Use Cases:**
- Quality assurance
- Supply tracking
- Program compliance monitoring
- Performance evaluation

---

#### 6. **YeboVisit** (Yebo Program)
Records Yebo program (paired reading) observations.

**Fields:**
```python
{
  "id": Integer (Primary Key),
  "mentor_id": ForeignKey (User),
  "school_id": ForeignKey (School),
  "visit_date": Date,
  
  # Observations
  "paired_reading_took_place": Boolean,
  "paired_reading_tracking_updated": Boolean,
  
  # Quality
  "afternoon_session_quality": Integer (1-10),
  
  # Comments
  "commentary": Text,
  
  # Timestamps
  "created_at": DateTime (auto),
  "updated_at": DateTime (auto)
}
```

---

#### 7. **ThousandStoriesVisit** (1000 Stories Program)
Records 1000 Stories library program observations.

**Fields:**
```python
{
  "id": Integer (Primary Key),
  "mentor_id": ForeignKey (User),
  "school_id": ForeignKey (School),
  "visit_date": Date,
  
  # Observations
  "library_neat_and_tidy": Boolean,
  "tracking_sheets_up_to_date": Boolean,
  "book_boxes_and_borrowing": Boolean,
  "daily_target_met": Boolean,
  
  # Quality
  "story_time_quality": Integer (1-10),
  
  # Comments
  "other_comments": Text,
  
  # Timestamps
  "created_at": DateTime (auto),
  "updated_at": DateTime (auto)
}
```

---

#### 8. **NumeracyVisit** (Numeracy Program)
Records numeracy program observations.

**Fields:**
```python
{
  "id": Integer (Primary Key),
  "mentor_id": ForeignKey (User),
  "school_id": ForeignKey (School),
  "visit_date": Date,
  
  # Curriculum Observations
  "numeracy_tracker_correct": Boolean,
  "teaching_counting": Boolean,
  "teaching_number_concepts": Boolean,
  "teaching_patterns": Boolean,
  "teaching_addition_subtraction": Boolean,
  
  # Quality
  "quality_rating": Integer (1-10),
  
  # Comments
  "supplies_needed": Text,
  "commentary": Text,
  
  # Timestamps
  "created_at": DateTime (auto),
  "updated_at": DateTime (auto)
}
```

---

#### 9. **Session**
Records teaching sessions between youth and children.

**Fields:**
```python
{
  "id": Integer (Primary Key),
  "airtable_id": String (Airtable record ID),
  "session_id": Integer (unique),
  "youth_id": ForeignKey (Youth),
  "child_id": ForeignKey (Child),
  "school_id": ForeignKey (School),
  "mentor_id": ForeignKey (Mentor),
  
  # Session Details
  "total_weekly_sessions": Integer,
  "submitted_for_week": Integer,
  "week": String (max 50 chars),
  "month": String (max 50 chars),
  "month_year": String (max 50 chars),
  "sessions_met_minimum": String (max 10 chars),
  "capture_date": Date,
  
  # Timestamps
  "created_in_airtable": DateTime,
  "created_in_system": DateTime (auto),
  "updated_in_system": DateTime (auto)
}
```

---

#### 10. **WELA_assessments**
Stores literacy assessment scores for children (3 assessments per year).

**Fields:**
```python
{
  "id": Integer (Primary Key),
  "mcode": String (max 20 chars, indexed),
  "assessment_year": Integer (2022, 2023, 2024),
  
  # School Info
  "school": String (max 200 chars),
  "city": String (max 100 chars),
  "centre": String (max 100 chars),
  "type": String (max 50 chars),
  "grade": String (max 20 chars),
  "language": String (max 50 chars),
  
  # Student Info
  "full_name": String (max 200 chars),
  "gender": String (M/F),
  "mentor": String (max 100 chars),
  
  # Program Participation
  "total_sessions": Integer,
  "on_programme": String (max 10 chars),
  "current_lc": String (max 100 chars),
  
  # January Assessment (11 subtests + total)
  "jan_letter_sounds": Integer (0-100),
  "jan_story_comprehension": Integer (0-100),
  "jan_listen_first_sound": Integer (0-100),
  "jan_listen_words": Integer (0-100),
  "jan_writing_letters": Integer (0-100),
  "jan_read_words": Integer (0-100),
  "jan_read_sentences": Integer (0-100),
  "jan_read_story": Integer (0-100),
  "jan_write_cvcs": Integer (0-100),
  "jan_write_sentences": Integer (0-100),
  "jan_write_story": Integer (0-100),
  "jan_total": Integer,
  
  # June Assessment (same 11 subtests + total)
  "june_*": Integer (same structure as jan_*),
  
  # November Assessment (same 11 subtests + total)
  "nov_*": Integer (same structure as jan_*),
  
  # Metadata
  "captured_by": String (max 100 chars),
  "created_at": DateTime (auto),
  "updated_at": DateTime (auto)
}
```

**Computed Properties:**
- `jan_improvement_from_baseline`: June total - January total
- `year_end_improvement`: November total - January total
- `improvement_percentage`: Percentage improvement from Jan to Nov

**Indexes:**
- `(mcode, assessment_year)` - Unique together
- `(school, assessment_year)`
- `(grade, assessment_year)`
- `(mentor, assessment_year)`

---

#### 11. **LiteracySession**
Detailed literacy session records.

**Fields:**
```python
{
  "id": Integer (Primary Key),
  "session_id": Integer (unique),
  "lc_full_name": String (max 255 chars),
  "child_full_name": String (max 255 chars),
  "school": String (max 255 chars),
  "grade": String (max 50 chars),
  "sessions_capture_date": Date,
  "total_weekly_sessions_received": Integer,
  "reading_level": String (max 100 chars),
  "letters_done": JSONField (array),
  "mentor": String (max 255 chars),
  "site_type": String (max 100 chars),
  "on_the_programme": String (max 50 chars),
  "month": String (max 50 chars),
  "week": String (max 50 chars),
  "month_and_year": String (max 50 chars),
  "created": DateTime,
  "sessions_met_minimum": String (max 10 chars),
  "duplicate_flag": String (max 255 chars),
  "employee_id": String (max 50 chars),
  "mcode": String (max 50 chars)
}
```

---

#### 12. **NumeracySessionChild**
Detailed numeracy session records (child-level).

**Fields:**
```python
{
  "id": Integer (Primary Key),
  "session_id": String (max 255 chars),
  "nc_full_name": String (max 255 chars),
  "numeracy_site": String (max 255 chars),
  "child_name": String (max 255 chars),
  "sessions_capture_date": Date,
  "children_in_group": Integer,
  "created": String (max 50 chars),
  "current_count_level": String (max 50 chars),
  "baseline_count_level": JSONField (array),
  "number_recognition": String (max 50 chars),
  "month": String (max 50 chars),
  "week": String (max 50 chars),
  "month_and_year": String (max 50 chars),
  "all_sites": JSONField (array),
  "site_placement": String (max 255 chars),
  "employee_id": String (max 255 chars),
  "mentor": String (max 255 chars),
  "employment_status": String (max 255 chars),
  "duplicate_flag": String (max 255 chars)
}
```

---

#### 13. **AirtableSyncLog**
Tracks Airtable synchronization history.

**Fields:**
```python
{
  "id": Integer (Primary Key),
  "sync_type": String (max 50 chars),  # 'youth', 'sessions', etc.
  "started_at": DateTime (auto),
  "completed_at": DateTime,
  "records_processed": Integer,
  "records_created": Integer,
  "records_updated": Integer,
  "records_skipped": Integer,
  "error_message": Text,
  "success": Boolean
}
```

---

## API Endpoints Reference

### Base Information

**Base URL:** `/api/`  
**Authentication:** All endpoints require authentication  
**Content-Type:** `application/json`

### Available Endpoints

#### User & Info Endpoints

| Method | Endpoint | Purpose | Auth Required |
|--------|----------|---------|---------------|
| GET | `/api/info/` | Get API information | Yes |
| GET | `/api/me/` | Get current user info | Yes |

#### Visit Endpoints - MASI Literacy

| Method | Endpoint | Purpose | Filters Available |
|--------|----------|---------|-------------------|
| GET | `/api/mentor-visits/` | List all mentor visits | time_filter, school, mentor |
| POST | `/api/mentor-visits/` | Create new mentor visit | - |
| GET | `/api/mentor-visits/{id}/` | Get specific visit | - |
| PUT/PATCH | `/api/mentor-visits/{id}/` | Update visit | - |
| DELETE | `/api/mentor-visits/{id}/` | Delete visit | - |

#### Visit Endpoints - Yebo Program

| Method | Endpoint | Purpose | Filters Available |
|--------|----------|---------|-------------------|
| GET | `/api/yebo-visits/` | List Yebo visits | time_filter, school, mentor |
| POST | `/api/yebo-visits/` | Create Yebo visit | - |
| GET | `/api/yebo-visits/{id}/` | Get specific visit | - |
| PUT/PATCH | `/api/yebo-visits/{id}/` | Update visit | - |
| DELETE | `/api/yebo-visits/{id}/` | Delete visit | - |

#### Visit Endpoints - 1000 Stories Program

| Method | Endpoint | Purpose | Filters Available |
|--------|----------|---------|-------------------|
| GET | `/api/thousand-stories-visits/` | List 1000 Stories visits | time_filter, school, mentor |
| POST | `/api/thousand-stories-visits/` | Create visit | - |
| GET | `/api/thousand-stories-visits/{id}/` | Get specific visit | - |
| PUT/PATCH | `/api/thousand-stories-visits/{id}/` | Update visit | - |
| DELETE | `/api/thousand-stories-visits/{id}/` | Delete visit | - |

#### Visit Endpoints - Numeracy Program

| Method | Endpoint | Purpose | Filters Available |
|--------|----------|---------|-------------------|
| GET | `/api/numeracy-visits/` | List numeracy visits | time_filter, school, mentor |
| POST | `/api/numeracy-visits/` | Create visit | - |
| GET | `/api/numeracy-visits/{id}/` | Get specific visit | - |
| PUT/PATCH | `/api/numeracy-visits/{id}/` | Update visit | - |
| DELETE | `/api/numeracy-visits/{id}/` | Delete visit | - |

#### Lookup/Helper Endpoints

| Method | Endpoint | Purpose | Description |
|--------|----------|---------|-------------|
| GET | `/api/schools/` | List all schools | Returns all active schools |
| GET | `/api/mentors/` | List all mentors | Returns users who have submitted visits |

#### Dashboard Endpoints

| Method | Endpoint | Purpose | Filters Available |
|--------|----------|---------|-------------------|
| GET | `/api/dashboard-summary/` | Get summary statistics | time_filter, school, mentor |

### Query Parameters

#### Time Filters
Use `?time_filter=` with these values:
- `7days` - Last 7 days
- `30days` - Last 30 days
- `90days` - Last 90 days
- `thisyear` - Current year
- `all` - All records (default)

#### Entity Filters
- `?school=10` - Filter by school ID
- `?mentor=5` - Filter by mentor/user ID

#### Combining Filters
```
/api/mentor-visits/?time_filter=30days&school=10&mentor=5
```

---

## Frontend Integration Examples

### 1. Setting Up Authentication

#### React Example with Clerk

```javascript
// lib/api.js
import { useAuth } from '@clerk/nextjs';
import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';

export const useAPI = () => {
  const { getToken } = useAuth();
  
  const api = axios.create({
    baseURL: API_BASE_URL,
  });
  
  // Add auth token to all requests
  api.interceptors.request.use(async (config) => {
    const token = await getToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  });
  
  return api;
};
```

#### Usage in Component

```javascript
// components/Dashboard.jsx
import { useAPI } from '@/lib/api';
import { useEffect, useState } from 'react';

export default function Dashboard() {
  const api = useAPI();
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    async function fetchData() {
      try {
        const { data } = await api.get('/dashboard-summary/?time_filter=30days');
        setSummary(data);
      } catch (error) {
        console.error('Error fetching dashboard:', error);
      } finally {
        setLoading(false);
      }
    }
    
    fetchData();
  }, []);
  
  if (loading) return <div>Loading...</div>;
  
  return (
    <div className="dashboard">
      <h1>Dashboard</h1>
      <div className="stats">
        <div className="stat-card">
          <h3>Total Visits</h3>
          <p>{summary.total_visits}</p>
        </div>
        <div className="stat-card">
          <h3>Recent Visits (30 days)</h3>
          <p>{summary.recent_visits}</p>
        </div>
        <div className="stat-card">
          <h3>Schools Visited</h3>
          <p>{summary.schools_visited}</p>
        </div>
        <div className="stat-card">
          <h3>Average Quality</h3>
          <p>{summary.avg_quality}/10</p>
        </div>
      </div>
    </div>
  );
}
```

---

### 2. Fetching Visit Data with Filters

```javascript
// hooks/useVisits.js
import { useState, useEffect } from 'react';
import { useAPI } from '@/lib/api';

export const useVisits = (visitType, filters = {}) => {
  const api = useAPI();
  const [visits, setVisits] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  useEffect(() => {
    async function fetchVisits() {
      try {
        setLoading(true);
        
        // Build query string
        const params = new URLSearchParams();
        if (filters.timeFilter) params.append('time_filter', filters.timeFilter);
        if (filters.school) params.append('school', filters.school);
        if (filters.mentor) params.append('mentor', filters.mentor);
        
        const endpoint = `/${visitType}/${params.toString() ? '?' + params.toString() : ''}`;
        const { data } = await api.get(endpoint);
        
        setVisits(data);
        setError(null);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    
    fetchVisits();
  }, [visitType, JSON.stringify(filters)]);
  
  return { visits, loading, error };
};
```

#### Using the Hook

```javascript
// pages/visits.jsx
import { useVisits } from '@/hooks/useVisits';
import { useState } from 'react';

export default function VisitsPage() {
  const [filters, setFilters] = useState({
    timeFilter: '30days',
    school: null,
    mentor: null
  });
  
  const { visits, loading, error } = useVisits('mentor-visits', filters);
  
  if (loading) return <div>Loading visits...</div>;
  if (error) return <div>Error: {error}</div>;
  
  return (
    <div>
      <h1>Mentor Visits</h1>
      
      {/* Filter Controls */}
      <div className="filters">
        <select 
          value={filters.timeFilter}
          onChange={(e) => setFilters({...filters, timeFilter: e.target.value})}
        >
          <option value="7days">Last 7 Days</option>
          <option value="30days">Last 30 Days</option>
          <option value="90days">Last 90 Days</option>
          <option value="thisyear">This Year</option>
          <option value="all">All Time</option>
        </select>
      </div>
      
      {/* Visits List */}
      <div className="visits-list">
        {visits.map(visit => (
          <div key={visit.id} className="visit-card">
            <h3>{visit.school.name}</h3>
            <p>Date: {new Date(visit.visit_date).toLocaleDateString()}</p>
            <p>Mentor: {visit.mentor.first_name} {visit.mentor.last_name}</p>
            <p>Quality Rating: {visit.quality_rating}/10</p>
            {visit.commentary && <p>Comments: {visit.commentary}</p>}
          </div>
        ))}
      </div>
    </div>
  );
}
```

---

### 3. Creating a New Visit

```javascript
// components/VisitForm.jsx
import { useState } from 'react';
import { useAPI } from '@/lib/api';

export default function MentorVisitForm({ onSuccess }) {
  const api = useAPI();
  const [formData, setFormData] = useState({
    school_id: '',
    visit_date: new Date().toISOString().split('T')[0],
    letter_trackers_correct: false,
    reading_trackers_correct: false,
    sessions_correct: false,
    admin_correct: false,
    quality_rating: 5,
    supplies_needed: '',
    commentary: ''
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  
  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    
    try {
      const { data } = await api.post('/mentor-visits/', formData);
      console.log('Visit created:', data);
      onSuccess?.(data);
      
      // Reset form
      setFormData({
        school_id: '',
        visit_date: new Date().toISOString().split('T')[0],
        letter_trackers_correct: false,
        reading_trackers_correct: false,
        sessions_correct: false,
        admin_correct: false,
        quality_rating: 5,
        supplies_needed: '',
        commentary: ''
      });
    } catch (err) {
      setError(err.response?.data?.detail || err.message);
    } finally {
      setSubmitting(false);
    }
  };
  
  return (
    <form onSubmit={handleSubmit} className="visit-form">
      <h2>Submit Mentor Visit</h2>
      
      {error && <div className="error">{error}</div>}
      
      <div className="form-group">
        <label>School *</label>
        <SchoolSelect
          value={formData.school_id}
          onChange={(id) => setFormData({...formData, school_id: id})}
        />
      </div>
      
      <div className="form-group">
        <label>Visit Date *</label>
        <input
          type="date"
          value={formData.visit_date}
          onChange={(e) => setFormData({...formData, visit_date: e.target.value})}
          required
        />
      </div>
      
      <div className="form-group">
        <label>
          <input
            type="checkbox"
            checked={formData.letter_trackers_correct}
            onChange={(e) => setFormData({...formData, letter_trackers_correct: e.target.checked})}
          />
          Letter Trackers Used Correctly
        </label>
      </div>
      
      <div className="form-group">
        <label>
          <input
            type="checkbox"
            checked={formData.reading_trackers_correct}
            onChange={(e) => setFormData({...formData, reading_trackers_correct: e.target.checked})}
          />
          Reading Trackers Used Correctly
        </label>
      </div>
      
      <div className="form-group">
        <label>
          <input
            type="checkbox"
            checked={formData.sessions_correct}
            onChange={(e) => setFormData({...formData, sessions_correct: e.target.checked})}
          />
          Session Trackers Used Correctly
        </label>
      </div>
      
      <div className="form-group">
        <label>
          <input
            type="checkbox"
            checked={formData.admin_correct}
            onChange={(e) => setFormData({...formData, admin_correct: e.target.checked})}
          />
          Admin Completed Correctly
        </label>
      </div>
      
      <div className="form-group">
        <label>Quality Rating (1-10) *</label>
        <input
          type="range"
          min="1"
          max="10"
          value={formData.quality_rating}
          onChange={(e) => setFormData({...formData, quality_rating: parseInt(e.target.value)})}
        />
        <span>{formData.quality_rating}/10</span>
      </div>
      
      <div className="form-group">
        <label>Supplies Needed</label>
        <textarea
          value={formData.supplies_needed}
          onChange={(e) => setFormData({...formData, supplies_needed: e.target.value})}
          rows={3}
        />
      </div>
      
      <div className="form-group">
        <label>Commentary</label>
        <textarea
          value={formData.commentary}
          onChange={(e) => setFormData({...formData, commentary: e.target.value})}
          rows={4}
        />
      </div>
      
      <button type="submit" disabled={submitting}>
        {submitting ? 'Submitting...' : 'Submit Visit'}
      </button>
    </form>
  );
}
```

---

### 4. School Selection Component

```javascript
// components/SchoolSelect.jsx
import { useState, useEffect } from 'react';
import { useAPI } from '@/lib/api';

export default function SchoolSelect({ value, onChange }) {
  const api = useAPI();
  const [schools, setSchools] = useState([]);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    async function fetchSchools() {
      try {
        const { data } = await api.get('/schools/');
        setSchools(data);
      } catch (error) {
        console.error('Error fetching schools:', error);
      } finally {
        setLoading(false);
      }
    }
    
    fetchSchools();
  }, []);
  
  if (loading) return <select disabled><option>Loading schools...</option></select>;
  
  return (
    <select 
      value={value} 
      onChange={(e) => onChange(e.target.value)}
      required
    >
      <option value="">Select a school...</option>
      {schools.map(school => (
        <option key={school.id} value={school.id}>
          {school.name} - {school.city}
        </option>
      ))}
    </select>
  );
}
```

---

### 5. Updating a Visit

```javascript
// api/visits.js
import { useAPI } from '@/lib/api';

export const useVisitActions = () => {
  const api = useAPI();
  
  const updateVisit = async (visitType, visitId, updates) => {
    try {
      const { data } = await api.patch(`/${visitType}/${visitId}/`, updates);
      return { success: true, data };
    } catch (error) {
      return { success: false, error: error.response?.data || error.message };
    }
  };
  
  const deleteVisit = async (visitType, visitId) => {
    try {
      await api.delete(`/${visitType}/${visitId}/`);
      return { success: true };
    } catch (error) {
      return { success: false, error: error.response?.data || error.message };
    }
  };
  
  return { updateVisit, deleteVisit };
};
```

#### Usage

```javascript
// components/EditVisitModal.jsx
import { useState } from 'react';
import { useVisitActions } from '@/api/visits';

export default function EditVisitModal({ visit, onClose, onUpdate }) {
  const { updateVisit } = useVisitActions();
  const [formData, setFormData] = useState({
    quality_rating: visit.quality_rating,
    commentary: visit.commentary,
    supplies_needed: visit.supplies_needed
  });
  
  const handleSave = async () => {
    const result = await updateVisit('mentor-visits', visit.id, formData);
    
    if (result.success) {
      onUpdate(result.data);
      onClose();
    } else {
      alert('Error updating visit: ' + result.error);
    }
  };
  
  return (
    <div className="modal">
      <h2>Edit Visit</h2>
      
      <div className="form-group">
        <label>Quality Rating</label>
        <input
          type="range"
          min="1"
          max="10"
          value={formData.quality_rating}
          onChange={(e) => setFormData({...formData, quality_rating: parseInt(e.target.value)})}
        />
        <span>{formData.quality_rating}/10</span>
      </div>
      
      <div className="form-group">
        <label>Commentary</label>
        <textarea
          value={formData.commentary}
          onChange={(e) => setFormData({...formData, commentary: e.target.value})}
          rows={4}
        />
      </div>
      
      <div className="form-group">
        <label>Supplies Needed</label>
        <textarea
          value={formData.supplies_needed}
          onChange={(e) => setFormData({...formData, supplies_needed: e.target.value})}
          rows={3}
        />
      </div>
      
      <div className="button-group">
        <button onClick={handleSave}>Save Changes</button>
        <button onClick={onClose}>Cancel</button>
      </div>
    </div>
  );
}
```

---

### 6. Error Handling Pattern

```javascript
// utils/errorHandler.js
export const handleAPIError = (error) => {
  if (error.response) {
    // Server responded with error
    const status = error.response.status;
    const data = error.response.data;
    
    switch (status) {
      case 400:
        return {
          message: 'Invalid data submitted',
          details: data
        };
      case 401:
        return {
          message: 'Please log in to continue',
          redirect: '/login'
        };
      case 403:
        return {
          message: 'You do not have permission to perform this action'
        };
      case 404:
        return {
          message: 'The requested resource was not found'
        };
      case 500:
        return {
          message: 'Server error. Please try again later.'
        };
      default:
        return {
          message: data?.detail || 'An unexpected error occurred'
        };
    }
  } else if (error.request) {
    // Request made but no response
    return {
      message: 'Unable to connect to server. Please check your internet connection.'
    };
  } else {
    // Other errors
    return {
      message: error.message || 'An error occurred'
    };
  }
};
```

#### Usage with Error Handler

```javascript
// components/VisitsList.jsx
import { useEffect, useState } from 'react';
import { useAPI } from '@/lib/api';
import { handleAPIError } from '@/utils/errorHandler';

export default function VisitsList() {
  const api = useAPI();
  const [visits, setVisits] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    async function fetchVisits() {
      try {
        setLoading(true);
        const { data } = await api.get('/mentor-visits/');
        setVisits(data);
        setError(null);
      } catch (err) {
        const errorInfo = handleAPIError(err);
        setError(errorInfo.message);
        
        // Handle redirect if needed
        if (errorInfo.redirect) {
          window.location.href = errorInfo.redirect;
        }
      } finally {
        setLoading(false);
      }
    }
    
    fetchVisits();
  }, []);
  
  if (loading) return <div>Loading...</div>;
  if (error) return <div className="error-message">{error}</div>;
  
  return (
    <div>
      {/* Render visits */}
    </div>
  );
}
```

---

## Environment Configuration

### Backend Environment Variables

Create a `.env` file in the Django project root:

```bash
# Django Settings
DJANGO_SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/masi_db

# Clerk Authentication
CLERK_SECRET_KEY=sk_test_your_clerk_secret_key

# Google Cloud Storage (Production only)
GOOGLE_CREDENTIALS={"type":"service_account",...}
GS_BUCKET_NAME=masi-website

# CORS Settings (automatically configured in settings.py)
```

### Frontend Environment Variables

Create a `.env.local` file in your Next.js/React project:

```bash
# API Configuration
NEXT_PUBLIC_API_URL=http://localhost:8000/api
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000

# Clerk Configuration
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...

# Clerk URLs
NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up
NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL=/dashboard
NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL=/dashboard
```

### Production URLs

```bash
# Production API
NEXT_PUBLIC_API_URL=https://masi-website-main.onrender.com/api

# Production Clerk Instance
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_live_...
```

---

## CORS & Security

### CORS Configuration

The backend is configured to accept requests from these origins:

**Development:**
- `http://localhost:3000` (Next.js default)
- `http://localhost:3001` (Alternative port)

**Production:**
- `https://masinyusane.org`
- `https://www.masinyusane.org`
- `https://masi-website-main.onrender.com`

### Allowed Methods
- GET
- POST
- PUT
- PATCH
- DELETE
- OPTIONS (preflight)

### Allowed Headers
- `accept`
- `accept-encoding`
- `authorization`
- `content-type`
- `origin`
- `user-agent`
- `x-csrftoken`
- `x-requested-with`

### Security Headers

**Required for All Requests:**
```javascript
{
  'Authorization': 'Bearer YOUR_CLERK_TOKEN',
  'Content-Type': 'application/json'
}
```

### HTTPS Requirements

**Production:**
- All requests must use HTTPS
- HTTP requests automatically redirect to HTTPS
- SSL certificates are required

**Development:**
- HTTP is allowed for localhost
- HTTPS not required for `127.0.0.1` or `localhost`

---

## Common Use Cases

### Use Case 1: Building a Visit Submission Form

**Requirements:**
1. Fetch list of schools
2. Create form with validation
3. Submit visit data
4. Handle success/error states

**Implementation:**
```javascript
// pages/submit-visit.jsx
import { useState } from 'react';
import SchoolSelect from '@/components/SchoolSelect';
import { useAPI } from '@/lib/api';
import { useRouter } from 'next/router';

export default function SubmitVisitPage() {
  const api = useAPI();
  const router = useRouter();
  const [programType, setProgramType] = useState('literacy');
  const [formData, setFormData] = useState({
    school_id: '',
    visit_date: new Date().toISOString().split('T')[0],
    // ... other fields based on program type
  });
  
  const handleSubmit = async (e) => {
    e.preventDefault();
    
    const endpoint = {
      literacy: '/mentor-visits/',
      yebo: '/yebo-visits/',
      stories: '/thousand-stories-visits/',
      numeracy: '/numeracy-visits/'
    }[programType];
    
    try {
      await api.post(endpoint, formData);
      alert('Visit submitted successfully!');
      router.push('/visits');
    } catch (error) {
      alert('Error: ' + error.message);
    }
  };
  
  return (
    <form onSubmit={handleSubmit}>
      {/* Form fields */}
    </form>
  );
}
```

---

### Use Case 2: Building a Dashboard

**Requirements:**
1. Fetch summary statistics
2. Display program-specific metrics
3. Show filtering options
4. Visualize data

**Implementation:**
```javascript
// pages/dashboard.jsx
import { useState, useEffect } from 'react';
import { useAPI } from '@/lib/api';
import { Chart } from '@/components/Chart';

export default function DashboardPage() {
  const api = useAPI();
  const [timeFilter, setTimeFilter] = useState('30days');
  const [summary, setSummary] = useState(null);
  
  useEffect(() => {
    async function fetchSummary() {
      const { data } = await api.get(`/dashboard-summary/?time_filter=${timeFilter}`);
      setSummary(data);
    }
    fetchSummary();
  }, [timeFilter]);
  
  if (!summary) return <div>Loading...</div>;
  
  return (
    <div className="dashboard">
      <h1>MASI Dashboard</h1>
      
      <select value={timeFilter} onChange={(e) => setTimeFilter(e.target.value)}>
        <option value="7days">Last 7 Days</option>
        <option value="30days">Last 30 Days</option>
        <option value="90days">Last 90 Days</option>
        <option value="thisyear">This Year</option>
      </select>
      
      <div className="metrics-grid">
        <MetricCard title="Total Visits" value={summary.total_visits} />
        <MetricCard title="Schools Visited" value={summary.schools_visited} />
        <MetricCard title="Average Quality" value={`${summary.avg_quality}/10`} />
      </div>
      
      <div className="program-breakdown">
        <h2>Program Activity</h2>
        <ProgramCard 
          title="MASI Literacy" 
          total={summary.literacy_visits}
          recent={summary.literacy_recent_visits}
        />
        <ProgramCard 
          title="Yebo" 
          total={summary.yebo_visits}
          recent={summary.yebo_recent_visits}
        />
        <ProgramCard 
          title="1000 Stories" 
          total={summary.stories_visits}
          recent={summary.stories_recent_visits}
        />
        <ProgramCard 
          title="Numeracy" 
          total={summary.numeracy_visits}
          recent={summary.numeracy_recent_visits}
        />
      </div>
    </div>
  );
}
```

---

### Use Case 3: Building a School Directory

**Requirements:**
1. List all schools
2. Search/filter schools
3. Display school details
4. Show school visit history

**Implementation:**
```javascript
// pages/schools.jsx
import { useState, useEffect } from 'react';
import { useAPI } from '@/lib/api';

export default function SchoolsPage() {
  const api = useAPI();
  const [schools, setSchools] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  
  useEffect(() => {
    async function fetchSchools() {
      const { data } = await api.get('/schools/');
      setSchools(data);
    }
    fetchSchools();
  }, []);
  
  const filteredSchools = schools.filter(school => {
    const matchesSearch = school.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         school.city.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesType = typeFilter === 'all' || school.type === typeFilter;
    return matchesSearch && matchesType;
  });
  
  return (
    <div className="schools-page">
      <h1>Schools Directory</h1>
      
      <div className="filters">
        <input
          type="text"
          placeholder="Search schools..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
        
        <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
          <option value="all">All Types</option>
          <option value="ECDC">Early Childhood Development</option>
          <option value="Primary School">Primary School</option>
          <option value="Secondary School">Secondary School</option>
          <option value="Other">Other</option>
        </select>
      </div>
      
      <div className="schools-grid">
        {filteredSchools.map(school => (
          <SchoolCard key={school.id} school={school} />
        ))}
      </div>
    </div>
  );
}

function SchoolCard({ school }) {
  return (
    <div className="school-card">
      <h3>{school.name}</h3>
      <p className="school-type">{school.type}</p>
      <p className="school-city">{school.city}</p>
      {school.address && <p className="school-address">{school.address}</p>}
      {school.contact_phone && <p>📞 {school.contact_phone}</p>}
      {school.contact_email && <p>📧 {school.contact_email}</p>}
      <button onClick={() => window.location.href = `/schools/${school.id}`}>
        View Details
      </button>
    </div>
  );
}
```

---

### Use Case 4: Visit History for a School

**Requirements:**
1. Fetch all visits for a specific school
2. Show visits across all programs
3. Display visit timeline
4. Allow filtering by program and time

**Implementation:**
```javascript
// pages/schools/[id]/visits.jsx
import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import { useAPI } from '@/lib/api';

export default function SchoolVisitsPage() {
  const router = useRouter();
  const { id } = router.query;
  const api = useAPI();
  
  const [visits, setVisits] = useState({
    literacy: [],
    yebo: [],
    stories: [],
    numeracy: []
  });
  
  useEffect(() => {
    if (!id) return;
    
    async function fetchVisits() {
      const [literacy, yebo, stories, numeracy] = await Promise.all([
        api.get(`/mentor-visits/?school=${id}`).then(r => r.data),
        api.get(`/yebo-visits/?school=${id}`).then(r => r.data),
        api.get(`/thousand-stories-visits/?school=${id}`).then(r => r.data),
        api.get(`/numeracy-visits/?school=${id}`).then(r => r.data)
      ]);
      
      setVisits({ literacy, yebo, stories, numeracy });
    }
    
    fetchVisits();
  }, [id]);
  
  const allVisits = [
    ...visits.literacy.map(v => ({...v, program: 'Literacy'})),
    ...visits.yebo.map(v => ({...v, program: 'Yebo'})),
    ...visits.stories.map(v => ({...v, program: '1000 Stories'})),
    ...visits.numeracy.map(v => ({...v, program: 'Numeracy'}))
  ].sort((a, b) => new Date(b.visit_date) - new Date(a.visit_date));
  
  return (
    <div className="school-visits">
      <h1>Visit History</h1>
      
      <div className="visit-stats">
        <StatCard title="Literacy Visits" count={visits.literacy.length} />
        <StatCard title="Yebo Visits" count={visits.yebo.length} />
        <StatCard title="1000 Stories" count={visits.stories.length} />
        <StatCard title="Numeracy Visits" count={visits.numeracy.length} />
      </div>
      
      <div className="visit-timeline">
        {allVisits.map((visit, index) => (
          <VisitTimelineItem key={`${visit.program}-${visit.id}`} visit={visit} />
        ))}
      </div>
    </div>
  );
}
```

---

## API Testing & Documentation

### Interactive API Documentation

**Swagger UI:**
Visit `http://localhost:8000/api/schema/docs/` for interactive API documentation where you can:
- Browse all endpoints
- See request/response schemas
- Test endpoints directly in the browser
- View authentication requirements

### Testing with cURL

**Get API Info:**
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/info/
```

**List Schools:**
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/schools/
```

**Create a Visit:**
```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "school_id": 10,
    "visit_date": "2024-11-20",
    "letter_trackers_correct": true,
    "reading_trackers_correct": true,
    "sessions_correct": true,
    "admin_correct": true,
    "quality_rating": 8,
    "supplies_needed": "Books",
    "commentary": "Great session"
  }' \
  http://localhost:8000/api/mentor-visits/
```

---

## Troubleshooting

### Common Issues

#### 1. Authentication Errors (401 Unauthorized)

**Problem:** API returns 401 Unauthorized

**Solutions:**
- Verify Clerk token is being sent in Authorization header
- Check token hasn't expired
- Ensure `CLERK_SECRET_KEY` is configured on backend
- Verify Clerk instance URL matches

#### 2. CORS Errors

**Problem:** Browser blocks requests due to CORS

**Solutions:**
- Ensure frontend URL is in `CORS_ALLOWED_ORIGINS` in `settings.py`
- Check that credentials are being sent (`credentials: 'include'`)
- Verify `Authorization` header is in `CORS_ALLOW_HEADERS`

#### 3. 404 Not Found

**Problem:** Endpoint returns 404

**Solutions:**
- Verify endpoint URL is correct (check `/api/info/` for list)
- Ensure Django server is running
- Check URL includes `/api/` prefix

#### 4. 400 Bad Request

**Problem:** Server rejects data

**Solutions:**
- Validate required fields are included
- Check field names match API expectations (e.g., `school_id` not `school`)
- Verify data types (integers, booleans, dates)
- Review error response for specific validation errors

---

## Summary

This guide provides comprehensive information for integrating with the MASI backend API. Key points:

1. **Authentication:** Use Clerk JWT tokens in Authorization header
2. **Base URL:** `/api/` prefix for all endpoints
3. **Four Programs:** Literacy, Yebo, 1000 Stories, Numeracy
4. **CRUD Operations:** Full create, read, update, delete support
5. **Filtering:** Time, school, and mentor filters available
6. **Data Models:** Comprehensive models for schools, visits, youth, children, assessments
7. **CORS:** Configured for localhost (dev) and production domains
8. **Error Handling:** Standard HTTP status codes with detailed messages

### Quick Reference Links

- **API Documentation:** See `API_ENDPOINT_DOCUMENTATION.md`
- **Interactive Docs:** `http://localhost:8000/api/schema/docs/`
- **School Sync Guide:** See `SCHOOL_SYNC_GUIDE.md`
- **Avoiding Duplicates:** See `AVOIDING_SCHOOL_DUPLICATES.md`

### Support

For additional questions or issues:
1. Check Swagger documentation for endpoint details
2. Review error messages in API responses
3. Consult Django admin panel for data verification
4. Check server logs for backend errors

---

**Last Updated:** November 20, 2024  
**API Version:** 1.0  
**Django Version:** 5.1+  
**DRF Version:** Latest

