# Avoiding School Duplicates - Complete Guide

## The Problem

If you have schools in your Django database that were created **before** Airtable sync was set up, they won't have an `airtable_id`. When you run the sync, these schools might be created again (as duplicates) because the sync script only matches by `airtable_id`.

## The Solution - Two New Tools

### 1. Check for Duplicates BEFORE Syncing
### 2. Link Existing Schools During Sync

---

## Step 1: Check for Potential Duplicates

Run this command to scan for schools that exist in both Django and Airtable with the same name:

```bash
python manage.py check_school_duplicates --local
```

### What It Shows You

```
Django Schools: 150
Airtable Schools: 324

Schools WITH airtable_id: 50
Schools WITHOUT airtable_id: 100

========================================================================
POTENTIAL DUPLICATES (by name matching):
========================================================================

Found 15 potential duplicates:

Django School:
  ID: 42
  Name: Alex Jayiya
  Airtable ID: None
  Has Youth: 5
  Has Children: 120
  Has Visits: 45

Would match Airtable School:
  Airtable ID: rec0tkJLFZunQOi9D
  Name: Alex Jayiya
```

### Understanding the Output

- **Django Schools**: Total schools in your database
- **Airtable Schools**: Total schools in Airtable
- **Schools WITH airtable_id**: Already linked and will be updated safely
- **Schools WITHOUT airtable_id**: Old/historical schools (potential for duplicates)
- **POTENTIAL DUPLICATES**: Schools that have the same name in both places

---

## Step 2: Link Existing Schools (Prevent Duplicates)

If duplicates are found, use the `--link-existing` flag to **link** them instead of creating duplicates:

### Test First (Dry Run)

```bash
python manage.py sync_airtable_schools --local --link-existing --dry-run --verbose
```

This will show you what would be linked:

```
[DRY RUN] Would link existing school to Airtable: Alex Jayiya (Django ID: 42)
[DRY RUN] Would create new school: New School From Airtable
[DRY RUN] Would update school: Existing Linked School

Linked Existing Schools to Airtable (15):
  - Alex Jayiya (Django ID: 42, Airtable ID: rec0tkJLFZunQOi9D)
  - Jongilanga (Django ID: 18, Airtable ID: rec01xtaNrv3Hpg7r)
  ...

Created Schools (309):
  - New School ABC (Airtable ID: recXXXXXXXXXXXXXXX)
  ...
```

### Apply the Link (For Real)

Once you're satisfied with the dry-run results:

```bash
python manage.py sync_airtable_schools --local --link-existing --verbose
```

This will:
1. **Link** existing Django schools (by name) to their Airtable records
2. **Create** schools that only exist in Airtable
3. **Update** schools that are already linked
4. **Never delete** any schools

---

## Complete Workflow

### First Time Setup (Preventing Duplicates)

```bash
# 1. Export Airtable data
python scripts/export_airtable_schools.py

# 2. Check for duplicates
python manage.py check_school_duplicates --local

# 3. If duplicates found, test linking
python manage.py sync_airtable_schools --local --link-existing --dry-run --verbose --limit 10

# 4. Review the output carefully!

# 5. Run full dry-run
python manage.py sync_airtable_schools --local --link-existing --dry-run --verbose

# 6. If everything looks good, run for real
python manage.py sync_airtable_schools --local --link-existing --verbose

# 7. Verify results
python manage.py check_school_duplicates --local
```

### Regular Updates (After Initial Link)

Once all schools are linked, you don't need `--link-existing` anymore:

```bash
# Regular sync (no linking needed)
python manage.py sync_airtable_schools --verbose
```

---

## Comparison: With vs Without --link-existing

### WITHOUT --link-existing (Default Behavior)

```
Django DB:
  - School: "Alex Jayiya" (ID: 42, airtable_id: None)
  
Airtable:
  - School: "Alex Jayiya" (Airtable ID: rec0tkJLFZunQOi9D)
  
AFTER SYNC:
  - School: "Alex Jayiya" (ID: 42, airtable_id: None) ← OLD RECORD
  - School: "Alex Jayiya" (ID: 325, airtable_id: rec0tkJLFZunQOi9D) ← DUPLICATE!
  
❌ Result: DUPLICATE CREATED
```

### WITH --link-existing

```
Django DB:
  - School: "Alex Jayiya" (ID: 42, airtable_id: None)
  
Airtable:
  - School: "Alex Jayiya" (Airtable ID: rec0tkJLFZunQOi9D)
  
AFTER SYNC:
  - School: "Alex Jayiya" (ID: 42, airtable_id: rec0tkJLFZunQOi9D) ← LINKED!
  
✅ Result: NO DUPLICATE, EXISTING SCHOOL LINKED
```

---

## How Name Matching Works

The `--link-existing` flag matches schools by:
- **Case-insensitive** name comparison (`Alex Jayiya` = `alex jayiya`)
- **Whitespace trimming** (`School A ` = `School A`)
- **Only schools WITHOUT airtable_id** (won't touch already-linked schools)

### Examples of Matches

```
Django Name           Airtable Name        Match?
─────────────────────────────────────────────────
"Alex Jayiya"         "Alex Jayiya"        ✅ Yes
"Alex Jayiya"         "alex jayiya"        ✅ Yes (case-insensitive)
"Alex Jayiya "        "Alex Jayiya"        ✅ Yes (trimmed)
"Alex Jayiya"         "Alex J"             ❌ No
```

---

## Safety Features

### What Gets Linked

- ✅ Django school with **no airtable_id**
- ✅ Name matches Airtable school (case-insensitive, trimmed)
- ✅ All existing data (Youth, Children, Visits) preserved

### What NEVER Gets Linked

- ❌ Schools already having an airtable_id (already linked)
- ❌ Schools with different names
- ❌ Nothing gets deleted

### Dry-Run Mode

- Always test with `--dry-run` first
- See exactly what would be linked
- No changes are saved to the database
- Review before running for real

---

## Troubleshooting

### "No potential duplicates found!"

Good! This means:
- Either you don't have old schools without airtable_id
- Or the names don't match between Django and Airtable

You can run the sync without `--link-existing`:

```bash
python manage.py sync_airtable_schools --dry-run --verbose
```

### "Linked 0 schools" but check found duplicates

This can happen if:
1. Names don't match exactly (check for typos, extra spaces)
2. Schools already have airtable_id (check the duplicate checker output)

### What about schools WITHOUT matches?

Schools in Django that don't have matches in Airtable will:
- **NOT be deleted** (safe!)
- **NOT be updated** (they're orphaned/historical data)
- **Remain in database** with airtable_id = None

This is intentional to preserve historical data.

---

## Command Reference

### Check for Duplicates

```bash
# Using local file (fast)
python manage.py check_school_duplicates --local

# Using Airtable API (fresh data)
python manage.py check_school_duplicates
```

### Sync with Linking

```bash
# Dry-run with linking (TEST FIRST!)
python manage.py sync_airtable_schools --link-existing --dry-run --verbose

# Dry-run with linking + limit (test 10 schools)
python manage.py sync_airtable_schools --link-existing --dry-run --verbose --limit 10

# Actual sync with linking (CAREFUL!)
python manage.py sync_airtable_schools --link-existing --verbose

# Using local file (faster for testing)
python manage.py sync_airtable_schools --local --link-existing --dry-run --verbose
```

### Regular Sync (After Initial Link)

```bash
# Regular sync (no linking)
python manage.py sync_airtable_schools --verbose
```

---

## Best Practices

1. **Always run duplicate check first**
2. **Always test with --dry-run before real sync**
3. **Use --limit for initial testing** (e.g., `--limit 10`)
4. **Review the output carefully**
5. **Keep backups** (optional but recommended for first sync)
6. **Only use --link-existing for first sync** (not needed after)

---

## Summary

### New Commands

| Command | Purpose |
|---------|---------|
| `check_school_duplicates` | Find schools that exist in both places |
| `sync_airtable_schools --link-existing` | Link existing schools instead of creating duplicates |

### When to Use --link-existing

| Scenario | Use --link-existing? |
|----------|----------------------|
| First time syncing | ✅ Yes (if duplicates found) |
| Regular updates | ❌ No |
| Old schools without airtable_id | ✅ Yes |
| All schools already linked | ❌ No (won't make a difference) |

### Safety

- ✅ Never deletes schools
- ✅ Never breaks relationships
- ✅ Only links schools without airtable_id
- ✅ Dry-run mode to preview
- ✅ Case-insensitive name matching

