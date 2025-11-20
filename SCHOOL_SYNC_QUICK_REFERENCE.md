# School Sync - Quick Reference

> **Updated for Current Airtable Schema** - See `SCHOOL_SYNC_UPDATES.md` for details on changes.

## 🚀 Quick Start (3 Steps)

### 1. Set Environment Variables
```bash
export AIRTABLE_API_KEY="your_api_key"
export AIRTABLE_SCHOOLS_BASE_ID="your_base_id"
export AIRTABLE_SCHOOLS_TABLE_ID="your_table_id"
```

### 2. Preview Changes (Safe!)
```bash
python manage.py sync_airtable_schools --dry-run --verbose
```

### 3. Apply Changes
```bash
python manage.py sync_airtable_schools --verbose
```

---

## 📋 Common Commands

### Test with just 5 records
```bash
python manage.py sync_airtable_schools --dry-run --limit 5 --verbose
```

### Export Airtable data locally (for repeated testing)
```bash
python scripts/export_airtable_schools.py
```

### Use local data (no API calls)
```bash
python manage.py sync_airtable_schools --local --dry-run --verbose
```

### Run actual sync with local data
```bash
python manage.py sync_airtable_schools --local --verbose
```

---

## ✅ Safety Checklist

- [ ] Environment variables configured
- [ ] Ran with `--dry-run` first
- [ ] Reviewed what would be created/updated
- [ ] Tested with `--limit 5` 
- [ ] Ready to run actual sync

---

## 🔍 What Gets Updated

| ✅ SAFE TO SYNC | ❌ NEVER SYNCED |
|-----------------|-----------------|
| School name | School ID (auto-number) |
| Type (Primary/ECD/High School) | Mentors (separate table) |
| Programmes (Literacy, etc.) | Literacy Coaches (lookup) |
| Contact person & phone | Numeracy Sessions (lookup) |
| Principal | Total Children (formula) |
| Address, City, Suburb | Total Youth (formula) |
| Coordinates (direct fields) | All lookup/formula fields |
| Actively Working In | |

| ✅ ALWAYS SAFE | ❌ NEVER |
|----------------|---------|
| Add new schools | Delete schools |
| Update school info | Break relationships |
| Update contact details | Remove Youth links |
| Update addresses | Remove Visit records |
| Update coordinates | Remove Children |

---

## 📊 Check Results

### In Python/Django Shell
```python
from api.models import AirtableSyncLog

# Last sync
last = AirtableSyncLog.objects.filter(sync_type='schools').order_by('-started_at').first()
print(f"Created: {last.records_created}")
print(f"Updated: {last.records_updated}")
print(f"Success: {last.success}")
```

### In Django Admin
Navigate to: **Admin → Airtable Sync Logs → Schools**

---

## 🆘 Troubleshooting

| Problem | Solution |
|---------|----------|
| "No records found" | Check environment variables |
| "Missing school name" | Normal - some Airtable records incomplete |
| Coordinates not extracted | Maps URL format varied - manually add if needed |
| Script takes too long | Use `--local` flag with exported data |

---

## 🔑 Key Points

1. **Never deletes** - Only adds/updates schools
2. **Dry-run first** - Always preview before applying
3. **Atomic transactions** - All changes or none
4. **Preserves relationships** - All Youth/Visits/Children stay linked
5. **Logs everything** - Check AirtableSyncLog table

---

## 📁 Files Created

- `api/management/commands/sync_airtable_schools.py` - Main sync script
- `scripts/export_airtable_schools.py` - Export tool
- `SCHOOL_SYNC_GUIDE.md` - Full documentation
- `SCHOOL_SYNC_QUICK_REFERENCE.md` - This file

