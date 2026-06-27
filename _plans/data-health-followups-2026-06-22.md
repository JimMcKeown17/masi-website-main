# Data-health follow-ups (from 2026-06-22 work)

Expanded answers to the follow-up list. Items 1-3 done. Below: the ones that
needed digging, each with the actual records + a recommended action. All figures
are read-only prod queries (`/tmp/data_health_dig.sql`), 2026-06-22.

---

## 5. "Youth at an unknown school" (4) — WHO they are

These are **active** youth with a site-assigned job title whose **Site Placement
in Airtable didn't match any School row** (so `school_id` is null → they fall off
the grid). PG only stores the resolved FK, not the raw placement string, so staff
need to open each in Airtable and check/fix the **Site Placement** field:

| Employee ID | Name | Job title | youth_uid |
|---|---|---|---|
| 2116 | Asiphe Biko | Numeracy Coach | YTH-2116 |
| 2157 | Nomthandazo Mkele | Numeracy Coach | YTH-2157 |
| 1877 | Sinawe Socishe | Numeracy Coach | YTH-1877 |
| 2167 | Chulumanco Zalabe | ZZ ECD Coach | YTH-2167 |

**Action (staff):** in Airtable, check each one's Site Placement — likely a typo
or a spelling that doesn't match the School name, or a school not yet in the DB.
Once corrected, the next youth sync resolves the school and they leave this flag.

**This is the core of your request** — see "Panel enhancement" at the bottom: we
can list these names directly under the flag so staff don't need this doc.

## 6. "Blank job title" (1) — WHO

It's **Employee ID 1796** — and the record is **almost entirely empty**: no
full name, no job title, no school. It was also in the 88 blank-DOB list. This
looks like a **stub / placeholder row** in the Airtable youth table that has an
Employee ID but nothing filled in (not a real person missing one field — which is
why "no one is missing a job title in Airtable" is consistent with this).

**Action (staff):** look up Employee ID 1796 in Airtable. Either complete it (if
it's a real new hire) or delete the stub. If deleted in Airtable, the next youth
sync removes it from PG automatically (orphan-delete).

## 7. "406 mentor unmatched" — root cause found (it is NOT a simple sync_airtable_staff run)

The youth sync resolves each youth's Mentor **by name against the `Mentor` model
(`api_mentor`)**. But `sync_airtable_staff` writes a **different table — `Staff`
(`staff`)**. So running `sync_airtable_staff` does not refresh the table the youth
sync actually reads.

Prod numbers:

| | count |
|---|---|
| `api_mentor` rows (what youth-sync reads) | 323 |
| `staff` rows (what `sync_airtable_staff` writes) | 325 |
| active youth with `mentor_id` NULL | **124** |
| active youth total | 433 |
| last `staff` sync | **2026-03-12** (3 months ago) |

- The "406" in the sync log is unmatched across **all 1,800** youth (incl. former
  staff); among **active** youth it's **124** — still ~29%.
- There is **no nightly Mentor sync** at all — `api_mentor` is populated only by
  one-off imports (`import_mentor_visits`, `import_airtable_youth`), so it drifts.
- `Staff` itself last synced 3 months ago, so even it is stale (100 youth were
  just added; their mentors may be new staff not in either table).

**Recommended fix (architectural — your call):**
1. Short term: re-run `sync_airtable_staff` to refresh `Staff`, then decide #2.
2. Proper fix: **point the youth sync's mentor lookup at `Staff`** (the table that
   has a real sync) instead of the ad-hoc `Mentor` table — or build a dedicated
   `sync_airtable_mentors`. Two tables holding "the same people" is the smell here.
3. Then re-run the youth sync; the 124/406 should drop sharply. Whatever remains is
   genuine name-format mismatches to reconcile.

> Note: this only affects the `mentor_id` link on youth (dashboards/grouping). It
> does NOT affect the grid's staffing counts.

## 8. Stray school rows — recommended strategy (and confirmed safe)

There are **two rows each** for Bright Suns and Charlotte Educare — the canonical
Airtable row (has a UID) and a **stray orphan** (no UID), left behind because
`sync_airtable_schools` never deletes:

| id | name | school_uid | youth | grid cells | stats |
|---|---|---|---|---|---|
| 354 | Bright Suns | SCH-00330 | 0 | 1 | 1 | ← canonical (keep) |
| **360** | Bright Suns | *(none)* | **0** | **0** | 1 | ← **stray (delete)** |
| 352 | Charlotte Educare | SCH-00329 | 0 | 1 | 1 | ← canonical (keep) |
| **358** | Charlotte Educare | *(none)* | **0** | **0** | 1 | ← **stray (delete)** |

The strays (**id 360, id 358**) have **no youth and no grid cells** — only an
orphan `SchoolYearStats` row (junk the refresh created). They're the rows tripping
the "Schools with no UID" flag.

**Recommended strategy:** delete id 360 and id 358 in **Django admin** (Schools →
filter for blank School UID → delete; the orphan stats row goes with them). No
re-pointing needed since nothing references them. After deletion the flag clears.
(I did not run the delete — destructive on prod, and admin lets you eyeball any
cascade first. I can write a tiny idempotent management command instead if you'd
prefer that to clicking.)

## 9. Stray CSVs — committed (done this session).

## 10. The ~70 Zazi schools — exactly what's happening

**Mechanism (Masi side, fully explained):**
1. Each School has a `site_type`. For these ~70 schools, `site_type` lists **Zazi
   iZandi**, so the grid refresh **seeds a `zazi_izandi` cell** — the programme is
   marked "present" purely from the school's type, before any data is checked.
2. Child identities/reach for Zazi come **only** from the nightly Zazi export
   (`resolve_zazi_export`), because **Zazi sessions live in the separate Zazi
   backend** (`Zazi_iZandi_Website_2025`), not in Masi's `literacy_sessions_2026`
   / `numeracy_sessions_2026`.
3. For these ~70, the export returned **nothing** — their cells are
   `count_source=manual`, `children_count=NULL`, which only happens when
   `zazi_here` was `None` (i.e. the school was **absent from the export payload**).
   They are NOT in the "unmapped Zazi schools" list (only 2 are), so their Masi
   records and UIDs are fine — they simply didn't appear in the export.

So: **the programme is flagged present (from site_type) but the 2026 Zazi export
has zero data for them.** That's the entire "reach without identities" for Zazi.

**CONFIRMED via cross-DB check (Zazi prod, 2026-06-24):** it is neither "no
sessions yet" nor the reconciliation gap — it is **Masi `site_type` over-tagging
Zazi iZandi.** Evidence:

| | count |
|---|---|
| Masi schools with a `zazi_izandi` cell (2026, from `site_type`) | **179** |
| ...with real Zazi reach (children_count > 0, from the export) | **92** |
| ...with an empty Zazi cell (no export data) | **87** (74 of them flagged) |
| Schools mapped in the Zazi `api_schoolidentity2026` (program → Masi uid) | **92** |
| Of the 74 flagged uids, how many are mapped on the Zazi side | **2** |

The Zazi system maps/operates at **92** schools, and all 92 flow into the grid.
But Masi `site_type` marks **179** schools as Zazi — so **87 schools carry a Zazi
cell that Zazi never backs**, because Zazi doesn't run there in 2026 (only 2 of the
74 flagged are even in the Zazi map). `sessions_2026` links to schools by
`program_name` → `school_uid`; the 72 unmapped flagged schools have no program at
all on the Zazi side.

**So the root cause is Masi-side, not Zazi-side:** `School.site_type` (synced from
Airtable) lists Zazi iZandi for ~87 schools where Zazi isn't a 2026 site — likely
2025/historical or planned sites whose tag never got cleared.

**Decision for Jim:**
- If those ~87 are genuinely NOT 2026 Zazi sites → correct `site_type` at the
  **Airtable** source (it syncs from there); the phantom cells + flags disappear.
- If they ARE planned 2026 Zazi sites awaiting data → it's expected; the panel's
  "expected Zazi gap" framing already handles it, no action.
- Code alternative (design call): seed a `zazi_izandi` cell only when the export
  has data, not from `site_type` alone — eliminates all 87 phantom cells at once.

Either way it's a tagging/design question, not a data-pipeline bug. (The 2
mapped-but-flagged schools are minor edge cases — mapped on the Zazi side but their
participants likely fall in the 1,269 unresolved.)

---

## Panel enhancement — list the actual records under each flag (answers #5's ask)

> "The flag is nice, but no one knows what to actually fix."

Make each flag drill down to the offending records, in-panel:

| Flag | Records to show | Data available now? |
|---|---|---|
| Schools with no UID | school names | **Yes** (already in `schools_missing_uid`) — just not rendered as a list |
| Masi coach, no sessions / Reach buckets | school name + programmes | **Yes** (reach buckets already carry `{school, school_uid, programmes}`) |
| Youth at an unknown school | youth name + employee_id + job title | **No** — backend currently stores only `{title: count}`; enrich `compute_youth_active` to return the youth records |
| Blank job title | youth name + employee_id | **No** — same enrichment |

**Plan:**
- Backend: `compute_youth_active` returns `site_assigned_no_school_detail` and
  `unmapped_detail` as `[{employee_id, full_name, job_title}]`; thread into the
  integrity dict + `build_grid_health`. (reach buckets + missing-uid already carry
  what's needed.) Update tests.
- Frontend: render an expandable record list under each flag (name + ID, and for
  schools the name). Staff click the flag, see exactly who/what to fix in Airtable.

Contained change (one backend commit + one frontend cherry-pick), high payoff.
Recommend building it next.
