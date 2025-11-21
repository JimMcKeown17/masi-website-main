# School Database Sync - Safety Mechanism Explained

## The Problem You Had

```
Your Concern:
"I'm nervous about updating my school database because of 
the links to other tables and data."
```

## The Safe Solution

### 1. How Matching Works

```
Airtable Record                Django Database
┌─────────────────┐           ┌─────────────────┐
│ ID: rec123ABC   │  ──────>  │ airtable_id:    │
│                 │  MATCHES  │ rec123ABC       │
│ Name: School A  │           │ name: School A  │
│ City: PE        │           │ city: PE        │
└─────────────────┘           └─────────────────┘

✅ SAFE: Updates existing record by airtable_id
❌ NEVER: Deletes or breaks relationships
```

### 2. What Happens to Your Existing Data

#### Scenario A: School EXISTS in both places

```
BEFORE SYNC:
┌─────────────────────────────┐
│ School: Seyisi P School     │ ← Has 15 Youth linked
│ airtable_id: rec123         │ ← Has 200 Children
│ city: [OLD DATA]            │ ← Has 50 Visits
│ address: [OLD DATA]         │
└─────────────────────────────┘

AIRTABLE HAS:
┌─────────────────────────────┐
│ School: Seyisi P School     │
│ airtable_id: rec123         │ ← SAME ID = MATCH!
│ City: Gqeberha              │ ← UPDATED INFO
│ Address: 10 Ntima Street... │ ← UPDATED INFO
│ Programmes: Literacy, 1000..│ ← UPDATED INFO
└─────────────────────────────┘

AFTER SYNC:
┌─────────────────────────────┐
│ School: Seyisi P School     │ ← Still has 15 Youth ✅
│ airtable_id: rec123         │ ← Still has 200 Children ✅
│ City: Gqeberha              │ ← UPDATED ✅
│ Address: 10 Ntima Street... │ ← UPDATED ✅
│ Programmes: Literacy, 1000..│ ← UPDATED ✅
└─────────────────────────────┘
```

#### Scenario B: School is NEW in Airtable

```
AIRTABLE HAS:
┌─────────────────────────────┐
│ School: New School ABC      │
│ airtable_id: rec456         │ ← Not in Django yet
│ city: East London           │
└─────────────────────────────┘

AFTER SYNC:
Django Database:
┌─────────────────────────────┐
│ School: New School ABC      │ ← CREATED ✅
│ airtable_id: rec456         │
│ city: East London           │
└─────────────────────────────┘

All existing schools untouched ✅
```

#### Scenario C: School is ONLY in Django (not in Airtable)

```
DJANGO HAS:
┌─────────────────────────────┐
│ School: Old School XYZ      │ ← Has historical data
│ airtable_id: rec789         │ ← Not in current Airtable
└─────────────────────────────┘

AFTER SYNC:
┌─────────────────────────────┐
│ School: Old School XYZ      │ ← UNTOUCHED ✅
│ airtable_id: rec789         │ ← Still has all relationships ✅
└─────────────────────────────┘

❌ NEVER DELETED - Historical data preserved!
```

### 3. Relationship Safety

```
                    ┌─────────────────┐
                    │  SCHOOL         │
                    │  (Updated Only) │
                    └────────┬────────┘
                             │
                             │ ALL RELATIONSHIPS
                             │ REMAIN INTACT
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
    ┌────────┐         ┌─────────┐        ┌──────────┐
    │ YOUTH  │         │ CHILDREN│        │  VISITS  │
    │ (Safe) │         │ (Safe)  │        │  (Safe)  │
    └────────┘         └─────────┘        └──────────┘
    
Foreign Key: SET_NULL    CASCADE           CASCADE
Result: ✅ Safe          ✅ Safe*          ✅ Safe*

*CASCADE only matters if we DELETE (which we NEVER do)
```

### 4. Transaction Safety

```
START SYNC
    │
    ├─ Fetch 100 schools from Airtable
    │
    ├─ BEGIN TRANSACTION ──────────────┐
    │                                   │
    │  ├─ Update School 1... ✅         │  If ANY
    │  ├─ Update School 2... ✅         │  operation
    │  ├─ Create School 3... ✅         │  fails...
    │  ├─ Update School 4... ❌ ERROR!  │
    │                                   │
    ├─ ROLLBACK ALL CHANGES ←──────────┘
    │  (Database unchanged)
    │
    └─ Report error, try again

Result: Database stays consistent ✅
```

### 5. Dry-Run Mode

```
NORMAL RUN                      DRY-RUN MODE
┌──────────────┐               ┌──────────────┐
│ Fetch Data   │               │ Fetch Data   │
│      ↓       │               │      ↓       │
│ Calculate    │               │ Calculate    │
│ Changes      │               │ Changes      │
│      ↓       │               │      ↓       │
│ SAVE TO DB   │←── BLOCKED    │ SHOW PREVIEW │
│      ↓       │               │      ↓       │
│ Done ✅      │               │ NO SAVE ⚠️   │
└──────────────┘               └──────────────┘

Dry-run lets you see EXACTLY what would happen
before making ANY database changes!
```

## Safety Guarantees

| Action | Status | Reason |
|--------|--------|--------|
| Delete schools | ❌ NEVER | Script doesn't have delete code |
| Break Youth links | ❌ NEVER | Only updates School fields, not relationships |
| Remove Children | ❌ NEVER | CASCADE only triggers on DELETE (we never delete) |
| Delete Visits | ❌ NEVER | CASCADE only triggers on DELETE (we never delete) |
| Partial updates | ❌ NEVER | Atomic transactions = all or nothing |
| Update school info | ✅ YES | Safe - only data fields change |
| Add new schools | ✅ YES | Safe - creates new records |
| Preserve history | ✅ YES | Old schools stay even if removed from Airtable |

## Step-by-Step Safe Process

```
1. SET ENVIRONMENT VARIABLES
   ├─ AIRTABLE_API_KEY
   ├─ AIRTABLE_SCHOOLS_BASE_ID
   └─ AIRTABLE_SCHOOLS_TABLE_ID

2. DRY-RUN WITH LIMIT
   ├─ Command: --dry-run --limit 5 --verbose
   ├─ Review: What would be created/updated?
   └─ Verify: Does it look correct?

3. DRY-RUN FULL
   ├─ Command: --dry-run --verbose
   ├─ Review: All changes
   └─ Verify: Nothing unexpected?

4. ACTUAL SYNC (SMALL BATCH)
   ├─ Command: --limit 10 --verbose
   ├─ Verify: Check database
   └─ Confirm: Relationships intact?

5. FULL SYNC
   ├─ Command: --verbose
   ├─ Monitor: Watch the output
   └─ Verify: Check AirtableSyncLog

6. VERIFY RESULTS
   ├─ Check: Django Admin
   ├─ Test: Youth still linked?
   └─ Confirm: All data intact?
```

## Common Questions

### Q: What if I have a school with Youth/Children linked, and Airtable has different data?

**A:** The school's data fields (name, address, city, etc.) will update, but the Youth and Children relationships remain completely untouched. They stay linked to the same school record.

### Q: What if a school was removed from Airtable but exists in Django with historical data?

**A:** Nothing happens to it! The script only adds or updates schools, never deletes them. Your historical data stays safe.

### Q: What if the script crashes halfway through?

**A:** The `@transaction.atomic` decorator ensures ALL changes are rolled back if any error occurs. Your database stays in the state it was before the sync started.

### Q: Can I undo a sync?

**A:** While there's no automatic undo, you can:
1. Look at the `AirtableSyncLog` to see what changed
2. Manually revert specific records if needed
3. Restore from a database backup (if you made one)

**Best practice:** Always use `--dry-run` first!

### Q: What if two schools have the same name?

**A:** No problem! The script matches by `airtable_id`, not by name. Each school gets its own unique record in Django, even if names are similar.

## Summary: Why This Is Safe

1. ✅ **Never deletes** anything
2. ✅ **Never touches** relationships (Foreign Keys)
3. ✅ **Never breaks** historical data
4. ✅ **Always uses** transactions (all-or-nothing)
5. ✅ **Always allows** preview with --dry-run
6. ✅ **Always logs** every operation
7. ✅ **Always validates** data before saving

You can confidently update your school database without fear of losing Youth, Children, Visits, or any other related data!

