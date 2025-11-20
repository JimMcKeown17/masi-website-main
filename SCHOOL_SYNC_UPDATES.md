# School Sync Script - Updates for Current Airtable Schema

## What Changed

The sync script has been updated to match your **actual current Airtable schema**, which is simpler and different from the initial specification.

## Key Differences from Original

### 1. Field Names Changed

| Old (Initial Spec) | New (Current) | Change |
|-------------------|---------------|--------|
| School/ Center Name | School | Simpler field name |
| School Type (single select) | Type (multiple select) | Now can have multiple types |
| School Contact Person Full Name + Title | Main Contact | Combined into single field |
| Phone Number / School's Phone Number | Main Contact Phone Number | Single contact phone field |
| School's Email | *(not in schema)* | No email field |
| Location (URL) | Coord East + Coord South | Direct coordinate numbers instead of URL |
| Active Masinyusane Programme | Programmes | Different field name |

### 2. Simplified Processing

**Old approach:**
- Extracted coordinates from Google Maps URLs using regex
- Built addresses from separate components (street number, street name, suburb, postal code)
- Combined contact titles with names
- Combined principal titles with names

**New approach:**
- Uses direct coordinate fields (Coord East, Coord South)
- Uses pre-formatted Address field, optionally appends Suburb
- Uses Main Contact as-is
- Uses Principal as-is

### 3. Field Type Changes

| Field | Old Type | New Type | Handling |
|-------|----------|----------|----------|
| Type | Single select | Multiple select | Takes first value as primary type |
| Actively Working In | *(not specified)* | Boolean checkbox | Converts to "Yes"/"No" string |
| Programmes | Single select | Multiple select | Joins with commas into site_type |

## Updated Field Mapping

### Fields That ARE Synced

```python
Airtable Field          → Django Field          Notes
─────────────────────────────────────────────────────────────────
School                  → name                  Required
Type                    → type                  ECD→ECDC, Primary→Primary School, High School→Secondary School
Programmes              → site_type             Comma-separated list
Main Contact            → contact_person        
Main Contact Phone      → contact_phone         Formatted
Principal               → principal             
Address                 → address               Appends Suburb if available
City                    → city                  
Coord East              → latitude              Direct number
Coord South             → longitude             Direct number
Actively Working In     → actively_working_in   Boolean → "Yes"/"No"
```

### Fields That are NOT Synced

These are **lookup fields** or **formulas** calculated from other linked tables:

- School ID (auto-number, not needed)
- Mentors (multiple select - managed separately)
- All "Literacy *" fields (lookups from Masi Literacy Sites)
- All "Numeracy *" fields (lookups from Masi Numeracy Sites)
- All "Zazi Izandi *" fields (lookups from Zazi Izandi Sites)
- All "1000 Stories *" fields (lookups from 1000 Stories Sites)
- All "Top Learners *" fields (lookups from All TL High Schools)
- All "Yearbeyond *" fields (lookups from Yebo Sites)
- All "EduTech *" fields (lookups from EduTech Sites)
- All "ZZ ECD *" fields (lookups from ZZ ECD table)
- Total Children, Total Youth, Total Sessions (formulas)
- Google Maps Link, Google Maps (formula/button)
- Rural Or City (not in Django model)

## Code Changes Made

### 1. Removed Functions
- `extract_lat_long_from_url()` - No longer needed (direct coordinate fields)
- `build_address_string()` - No longer needed (pre-formatted address)

### 2. Updated Functions
- `map_airtable_school_type()` - Now handles multiple select type field

### 3. Updated Field Extraction
```python
# OLD
school_name = self.extract_value(fields.get('School/ Center Name'))
location_url = self.extract_value(fields.get('Location'))
latitude, longitude = self.extract_lat_long_from_url(location_url)

# NEW
school_name = self.extract_value(fields.get('School'))
latitude = fields.get('Coord East')
longitude = fields.get('Coord South')
```

## Testing Recommendations

### 1. Test with Your Actual Data

Since the schema is now correct, you should be able to test with real Airtable data:

```bash
# Export your actual Airtable data
python scripts/export_airtable_schools.py

# Test with dry-run
python manage.py sync_airtable_schools --local --dry-run --verbose

# Test with small batch
python manage.py sync_airtable_schools --local --dry-run --limit 5 --verbose
```

### 2. Verify Field Mappings

Check that the mappings work correctly:
- School types (Primary, ECD, High School)
- Multiple programmes (Literacy, 1000 Stories, etc.)
- Coordinates (Coord East = latitude, Coord South = longitude)
- Actively Working In (checkbox → "Yes"/"No")

### 3. Check Existing Data

If you already have schools in your Django database, verify they match correctly:

```python
from api.models import School

# Check which schools have airtable_id
schools_with_airtable_id = School.objects.filter(airtable_id__isnull=False)
print(f"Schools with Airtable ID: {schools_with_airtable_id.count()}")

# Check which schools don't
schools_without_airtable_id = School.objects.filter(airtable_id__isnull=True)
print(f"Schools without Airtable ID: {schools_without_airtable_id.count()}")

# For schools without airtable_id, they won't be updated by the sync
# (they're probably old/historical data)
```

## Important Notes

### 1. Lookup Fields

Many of the fields you see in Airtable (like "Literacy Coaches", "Total Sessions", etc.) are **lookup or formula fields**. These are automatically calculated from other linked tables and should **NOT** be synced to the School model directly.

If you need this data in Django, you should:
- Create separate models/tables for Literacy Sites, Numeracy Sites, etc.
- Use Django's ORM to calculate these values when needed

### 2. Type Field

The "Type" field in Airtable is **multiple select**, meaning a school can be both "Primary" and "ECD". The sync script currently takes the **first type** as the primary type since Django's model expects a single choice.

If you need to store multiple types, you would need to:
- Change the Django model field to support multiple types
- Update the sync script to handle the list

### 3. Actively Working In

This is stored as a boolean in Airtable but as varchar(5) in Django. The script converts:
- `true` → `"Yes"`
- `false` → `"No"`
- `null/empty` → `None`

## Summary

✅ **Script updated** to match current Airtable schema  
✅ **Documentation updated** with correct field names  
✅ **Unnecessary functions removed** (URL parsing, address building)  
✅ **Direct coordinate fields** now used  
✅ **Multiple select fields** properly handled  
✅ **Lookup/formula fields** correctly identified as non-syncing  

The script is now ready to sync with your actual Airtable "Schools" table!

