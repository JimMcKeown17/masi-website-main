# ETL Phase 1 + 3: Link Fact Tables to Canonical Models + Preview Page

Created: 2026-03-12

## Context

Phase 0 is complete -- all sync commands use safe upsert + AirtableSyncLog. Canonical tables exist (CanonicalChild, Youth, Staff, School) and 2026 session tables exist (LiteracySession2026, NumeracySession2026). However, the 2026 session tables store UIDs as **plain strings** (`youth_uid`, `school_uid`, `child_uid_1`, etc.) with no FK relationships to canonical tables. This means we can't do efficient Django ORM traversal or enforce referential integrity.

The goal: add real FK links from fact tables to canonical tables, resolve them during sync, create API endpoints to serve this data, and build a frontend preview page to verify everything works end-to-end.

## Decision: Skip mapping tables

ChildSourceMap/SchoolSourceMap/YouthSourceMap add complexity with no immediate value. The UID string fields already serve as the cross-reference. Defer indefinitely.

---

## Step 1: Add nullable FK fields to 2026 session models

**File:** `api/models.py`

Add to `LiteracySession2026` (after the existing UID string fields around line 686):
```python
# Resolved FKs (populated during sync by UID lookup)
youth = models.ForeignKey('Youth', on_delete=models.SET_NULL, null=True, blank=True,
                          related_name='literacy_sessions_2026')
school = models.ForeignKey('School', on_delete=models.SET_NULL, null=True, blank=True,
                           related_name='literacy_sessions_2026')
child_1 = models.ForeignKey('CanonicalChild', on_delete=models.SET_NULL, null=True, blank=True,
                            related_name='literacy_sessions_as_child1')
child_2 = models.ForeignKey('CanonicalChild', on_delete=models.SET_NULL, null=True, blank=True,
                            related_name='literacy_sessions_as_child2')
```

Add to `NumeracySession2026` (after UID fields around line 745):
```python
youth = models.ForeignKey('Youth', on_delete=models.SET_NULL, null=True, blank=True,
                          related_name='numeracy_sessions_2026')
school = models.ForeignKey('School', on_delete=models.SET_NULL, null=True, blank=True,
                           related_name='numeracy_sessions_2026')
```

No M2M for numeracy child_uids -- the JSON array is fine. Resolution for numeracy children happens at query time if needed.

Then: `python manage.py makemigrations api && python manage.py migrate`

---

## Step 2: Create `resolve_session_fks` management command

**New file:** `api/management/commands/resolve_session_fks.py`

Standalone command to backfill FKs on existing rows. Pattern:

1. Build lookup dicts: `youth_by_uid`, `school_by_uid`, `child_by_uid` from canonical tables
2. Query LiteracySession2026 rows where FK is null but UID is not null
3. Set FK from lookup dict, bulk_update in batches of 500
4. Same for NumeracySession2026 (youth + school only)
5. Print summary: resolved count, still-orphaned count per FK

This is a one-time backfill + ongoing utility for debugging.

---

## Step 3: Modify 2026 sync commands to resolve FKs during sync

**Files:**
- `api/management/commands/sync_airtable_literacy_sessions_2026.py`
- `api/management/commands/sync_airtable_numeracy_sessions_2026.py`

Changes to each:

1. At top of `handle()`, build lookup dicts:
   ```python
   from api.models import Youth, School, CanonicalChild
   youth_by_uid = {y.youth_uid: y for y in Youth.objects.filter(youth_uid__isnull=False)}
   school_by_uid = {s.school_uid: s for s in School.objects.filter(school_uid__isnull=False)}
   child_by_uid = {c.child_uid: c for c in CanonicalChild.objects.all()}  # literacy only
   ```

2. In `extract_row()`, add FK resolution to the returned dict:
   ```python
   youth=youth_by_uid.get(youth_uid_value),
   school=school_by_uid.get(school_uid_value),
   child_1=child_by_uid.get(child_uid_1),  # literacy only
   child_2=child_by_uid.get(child_uid_2),  # literacy only
   ```

3. In `bulk_upsert()`, add FK id fields to `update_fields`:
   ```python
   'youth_id', 'school_id', 'child_1_id', 'child_2_id'  # literacy
   'youth_id', 'school_id'  # numeracy
   ```

4. Log unresolved count after processing.

---

## Step 4: Create ETL preview API endpoints

**New file:** `api/views/etl_preview.py`

Two endpoints, both authenticated:

### `GET /api/etl-status/`
Returns sync health summary for all tables:
```json
{
  "tables": [
    {
      "name": "Schools",
      "record_count": 326,
      "last_sync": "2026-03-10T08:00:00Z",
      "last_sync_records": 326
    },
    ...
  ]
}
```
Queries `AirtableSyncLog` for latest successful sync per sync_type, plus `.count()` on each model.

### `GET /api/etl-preview/<table_name>/`
Returns sample rows + FK resolution stats for one table. `table_name` is one of: `schools`, `youth`, `children`, `staff`, `literacy-2026`, `numeracy-2026`.

For session tables, includes orphan stats:
```json
{
  "record_count": 5000,
  "orphan_stats": {
    "youth_resolved": 4950,
    "youth_orphaned": 50,
    "school_resolved": 4990,
    "school_orphaned": 10
  },
  "sample_rows": [...]
}
```

Sample rows use `select_related` and inline dict serialization (no serializer classes -- this is internal tooling).

**Wire up:**
- `api/views/__init__.py` -- add imports for `etl_status`, `etl_preview`
- `api/urls.py` -- add two paths

---

## Step 5: Backend tests

**File:** `api/tests.py`

Three test classes:

1. `TestFKResolution` -- Create canonical records + session with matching UIDs. Run resolution logic. Assert FKs populated.
2. `TestEtlStatusEndpoint` -- Create AirtableSyncLog records. Hit endpoint. Assert structure.
3. `TestEtlPreviewEndpoint` -- Create mixed resolved/orphaned data. Hit endpoint. Assert orphan stats correct.

---

## Step 6: Frontend preview page

**New file:** `frontend/masi-website/src/lib/api/preview/index.ts`
```typescript
export async function getEtlStatus(token: string) { ... }
export async function getEtlPreview(token: string, tableName: string) { ... }
```
Follow exact pattern from `src/lib/api/mentors/dashboard.ts`.

**New file:** `frontend/masi-website/src/app/operations/preview/page.tsx`

Single client component page following the mentors page pattern (SWR + Clerk + shadcn):
- Header: "ETL Data Preview"
- Status cards row: one card per table (record count + last sync time) from `/api/etl-status/`
- Tabs (shadcn `Tabs`): Schools | Youth | Children | Staff | Literacy 2026 | Numeracy 2026
- Each tab: orphan stats bar (for session tables) + sample data table (shadcn `Table`, 20 rows)
- Resolved FK names shown alongside UIDs (e.g. "YTH-1905 -- John Smith")

---

## Order of Work

| # | Task | Files |
|---|------|-------|
| 1 | Add FK fields to models + migrate | `api/models.py` |
| 2 | Create `resolve_session_fks` command | `api/management/commands/resolve_session_fks.py` |
| 3 | Modify literacy 2026 sync to resolve FKs | `api/management/commands/sync_airtable_literacy_sessions_2026.py` |
| 4 | Modify numeracy 2026 sync to resolve FKs | `api/management/commands/sync_airtable_numeracy_sessions_2026.py` |
| 5 | Run backfill + verify in shell | -- |
| 6 | Create `etl_preview.py` view + wire URLs | `api/views/etl_preview.py`, `api/urls.py`, `api/views/__init__.py` |
| 7 | Write backend tests | `api/tests.py` |
| 8 | Create frontend API functions + preview page | `src/lib/api/preview/index.ts`, `src/app/operations/preview/page.tsx` |

---

## Verification

1. Run syncs in order: schools, children, youth, staff, then literacy 2026, numeracy 2026
2. Run `resolve_session_fks` to backfill existing rows
3. Check Django shell: `LiteracySession2026.objects.filter(youth__isnull=False).count()` should be > 0
4. Hit `http://localhost:8000/api/etl-status/` -- verify counts and sync times
5. Hit `http://localhost:8000/api/etl-preview/literacy-2026/` -- verify sample rows have resolved names
6. Open `http://localhost:3000/operations/preview` -- verify cards, tabs, and data tables render
7. Run `python manage.py test api`

## Not doing

- Mapping tables (ChildSourceMap, etc.) -- UIDs already serve this purpose
- M2M for numeracy child_uids -- JSON array is fine for now
- Full CRUD serializers for 2026 tables -- read-only internal tooling
- Changes to legacy tables or existing mentor dashboard endpoints
- 1000 Stories session sync -- no 2026 Airtable table for it yet
