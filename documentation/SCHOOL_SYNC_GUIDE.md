# School Database Sync Guide

## Overview

This guide explains how to safely sync your Django school database with Airtable data without breaking existing relationships.

## Why This is Safe

1. **Never Deletes Schools**: Only adds new schools or updates existing ones
2. **Matches by Airtable ID**: Uses the `airtable_id` field to identify existing schools
3. **Preserves Relationships**: All relationships (Youth, Children, Visits, Sessions) remain intact
4. **Dry-Run Mode**: Preview all changes before applying them
5. **Atomic Transactions**: All changes happen together or not at all
6. **Detailed Logging**: Tracks every sync operation in the database

## Your Existing Relationships

The School model has these relationships that will **NOT** be affected:
- Youth → School (SET_NULL)
- Child → School (CASCADE, but we never delete schools)
- MentorVisit → School (CASCADE, but we never delete schools)
- YeboVisit → School (CASCADE, but we never delete schools)
- ThousandStoriesVisit → School (CASCADE, but we never delete schools)
- NumeracyVisit → School (CASCADE, but we never delete schools)
- Session → School (CASCADE, but we never delete schools)

## Setup

### 1. Environment Variables

Add these to your environment variables (`.env` file or hosting platform):

```bash
# Airtable API Token
AIRTABLE_API_KEY=your_airtable_api_key_here

# Base ID for your schools database
AIRTABLE_SCHOOLS_BASE_ID=your_base_id_here

# Table ID for schools (e.g., tblXXXXXXXXXXXXXX)
AIRTABLE_SCHOOLS_TABLE_ID=your_table_id_here
```

**How to find these values:**
1. Go to https://airtable.com/create/tokens
2. Create a new token with access to your schools base
3. For Base ID and Table ID:
   - Open your Airtable base
   - Go to Help → API Documentation
   - Base ID is shown at the top
   - Table ID is in the URL when viewing the table

### 2. Install Required Package (if not already installed)

```bash
pip install requests
```

## Field Mapping

This shows how Airtable fields map to your Django School model:

| Airtable Field | Django Field | Notes |
|----------------|--------------|-------|
| School | `name` | Required - school name |
| School ID | *(not synced)* | Auto-number in Airtable, not needed |
| Type | `type` | Multiple select → Mapped to choices (ECD→ECDC, Primary→Primary School, High School→Secondary School) |
| Programmes | `site_type` | Multiple select → Stored as comma-separated list |
| Main Contact | `contact_person` | Contact person name |
| Main Contact Phone Number | `contact_phone` | Cleaned format |
| Principal | `principal` | Principal's name |
| Address | `address` | Combined with Suburb if available |
| Suburb | Part of `address` | Appended to Address field |
| City | `city` | |
| Coord East | `latitude` | Direct number field |
| Coord South | `longitude` | Direct number field |
| Actively Working In | `actively_working_in` | Boolean → Converted to "Yes"/"No" |

**Fields NOT Synced** (lookups/formulas/not needed):
- Mentors (multiple select - stored in separate table)
- Literacy/Numeracy/Zazi Izandi/1000 Stories/etc. (all lookup fields from linked records)
- Literacy Coaches/Sessions/Children (all lookups - calculated elsewhere)
- Total Children/Youth/Sessions (formulas - calculated)
- Google Maps Link/Button (formula - can be reconstructed)
- Rural Or City (not in Django model currently)

## Usage

### Step 1: Test with Dry Run (RECOMMENDED FIRST)

Preview what would happen without making any changes:

```bash
python manage.py sync_airtable_schools --dry-run --verbose
```

This will show you:
- Which schools would be created
- Which schools would be updated (and what would change)
- Which schools are already up to date
- Any errors or skipped records

### Step 2: Test with Limited Records

Test with just a few records to verify everything works:

```bash
python manage.py sync_airtable_schools --dry-run --limit 5 --verbose
```

### Step 3: Run the Actual Sync

Once you're confident, run the actual sync:

```bash
python manage.py sync_airtable_schools --verbose
```

### Optional: Use Local JSON File

If you want to avoid repeated API calls during testing, you can:

1. Export your Airtable data to JSON (using the API or a script)
2. Save it as `data_exports/airtable_schools_data.json`
3. Run with `--local` flag:

```bash
python manage.py sync_airtable_schools --local --dry-run --verbose
```

## Command Options

| Option | Description |
|--------|-------------|
| `--dry-run` | Preview changes without saving to database |
| `--verbose` | Show detailed information about each operation |
| `--limit N` | Process only the first N records (for testing) |
| `--local` | Use local JSON file instead of Airtable API |

## What Happens During Sync

1. **Fetches data** from Airtable (or local file)
2. **For each school**:
   - Checks if it exists by `airtable_id`
   - **If exists**: Compares fields and updates only if changes detected
   - **If new**: Creates a new school record
3. **Logs everything** to `AirtableSyncLog` table
4. **Prints summary** of created/updated/skipped records

## Monitoring and Logs

### Check Sync History

```python
from api.models import AirtableSyncLog

# View recent syncs
recent_syncs = AirtableSyncLog.objects.filter(sync_type='schools').order_by('-started_at')[:10]
for sync in recent_syncs:
    print(f"{sync.started_at}: Created={sync.records_created}, Updated={sync.records_updated}, Success={sync.success}")
```

### Django Admin

You can also view sync logs in Django Admin under "Airtable Sync Logs".

## Safety Features

### 1. No Deletions
The script **never** deletes schools, even if they're removed from Airtable. This ensures:
- Historical data remains intact
- Relationships with Youth, Children, and Visits are preserved

### 2. Smart Updates
- Only updates fields that have actual values in Airtable
- Doesn't overwrite existing data with blank values
- Detects when no changes are needed (avoids unnecessary updates)

### 3. Transaction Safety
- All operations happen in a single database transaction
- If anything fails, all changes are rolled back
- Database remains in consistent state

## Troubleshooting

### "No records found"
- Check your environment variables are set correctly
- Verify the Base ID and Table ID match your Airtable setup
- Ensure your API token has access to the base

### "Missing school name"
- Some Airtable records don't have the "School" field filled
- These records are safely skipped with a warning

### "Duplicate school name"
- The script uses `airtable_id` to match, not name
- Different schools can have the same name
- Each gets a unique database record

### Missing Coordinates
- If Coord East or Coord South fields are empty in Airtable, latitude/longitude will be None
- This is safe - other fields will still update
- You can manually add coordinates in Airtable or Django Admin later

## Extending the Script

### Add New Fields

If you want to map additional Airtable fields:

1. Add the field to your `School` model (create a migration)
2. Update the script's `school_data` dictionary around line 320
3. Run migrations and test with `--dry-run`

Example - Adding "Rural Or City" field:

```python
# In models.py (api/models.py)
rural_or_city = models.CharField(max_length=10, blank=True, null=True)

# In sync_airtable_schools.py (add extraction around line 295)
rural_or_city = self.extract_value(fields.get('Rural Or City'))

# In sync_airtable_schools.py (add to school_data dictionary around line 320)
'rural_or_city': rural_or_city,
```

Then create and run the migration:
```bash
python manage.py makemigrations
python manage.py migrate
```

### Schedule Regular Syncs

You can set up a cron job or Celery task to run syncs automatically:

```bash
# Example cron job (daily at 2 AM)
0 2 * * * cd /path/to/project && python manage.py sync_airtable_schools
```

## Best Practices

1. **Always test with --dry-run first**
2. **Start with --limit during initial testing**
3. **Use --verbose to understand what's happening**
4. **Review the sync logs after each run**
5. **Backup your database before first sync** (optional, but recommended)

## Support

If you encounter issues:
1. Run with `--dry-run --verbose` to see detailed output
2. Check the `AirtableSyncLog` table for error messages
3. Review the field mapping section to ensure data compatibility
4. Check that all environment variables are correctly set

