# Airtable → Postgres → Downstream: Operational Pipeline Guide

**This repo is the source of truth.** It owns the Airtable → Postgres ingestion (models + sync
commands) and the outbound serving to downstream consumers (the Next.js site via DRF, and the
**Streamlit data portal** at `../../Masi_Data_Site/masi_data_streamlit/` via a parquet snapshot).

> **Read alongside** [`etl_data_architecture_plan.md`](./etl_data_architecture_plan.md) — that is
> the *strategic* roadmap (raw / canonical / reporting layers, canonical-key strategy, phased plan).
> **This** doc is the *operational* companion: the current sync convention, the as-verified state
> of the data as it exists today, and the concrete **2026 literacy assessments** pipeline (which is
> Phase-4 "assessment architecture cleanup" work, being pulled forward — see §6).

---

## 1. The convention every sync follows (current, verified in `api/`)

Model each Airtable table at **its natural grain**; key it for idempotent upsert.

- **Upsert key:** `source_airtable_id` (the Airtable record id).
- **Business key:** a stable UID — `child_uid` (`CH-XXXXX`), `youth_uid` (`YTH-XXXX`),
  `school_uid` (`SCH-XXXXX`), or a per-event UID. (Note: the strategic plan names `mcode` /
  `employee_id` as canonical keys; the **implemented** newer models moved to these UID strings —
  reconciling that naming is part of "nailing down canonical", see §5.)
- **Dimensions vs facts:** canonical dimensions (`CanonicalChild`, `School`, `Youth`, `Mentor`)
  are separate tables; event facts (`LiteracySession2026`, assessments) carry **FKs to
  dimensions resolved by UID**, never denormalised name strings.

Command blueprint (reference: `sync_airtable_children.py`, `sync_airtable_literacy_sessions_2026.py`,
`sync_airtable_2025_assessments.py`):

1. Config via `os.getenv` after `load_dotenv()`: `AIRTABLE_TOKEN` + per-table `*_BASE_ID`/`*_TABLE_ID`.
2. Paginate through `api.airtable_sync.fetch_airtable_records`, retaining filters and selected fields across every offset page, with explicit timeout and bounded transient retries.
3. `map_fields()` with `safe_str`/`safe_int`; **strip `None`** so blanks don't overwrite good data.
   Linked fields return **record-ID arrays** → resolve to FKs; lookups return display strings.
4. Resolve FKs from **pre-loaded dimension dicts** (`{child_uid: CanonicalChild}`, …), not per-row queries.
5. **Bulk upsert** on `source_airtable_id`: one incoming-ID-scoped `values()` fetch, then
   `bulk_create` + `bulk_update` (batch 500) in one `transaction.atomic()`.
6. Write an **`AirtableSyncLog`** (created/updated/failed).
7. Support `--dry-run` / `--verbose`.
8. Register the table in the ETL-preview `TABLE_CONFIG` (`/api/etl-status/`, `/api/etl-preview/<table>/`).

The 2026 literacy and numeracy session commands also support `--incremental-new`. Their immutable Airtable creation-time watermark lives in `AirtableSyncCursor`, separate from `AirtableSyncLog`; upsert and cursor advancement commit atomically. Full mode remains necessary for source edits and FK repair. See `build-log.md` for deployment state and known deletion boundaries.

### 1.1 Youth subsidy linked-table enrichment

`sync_airtable_youth` keeps Youth Basic Data canonical. Its Airtable record ID remains
`Youth.airtable_id`, so orphan reconciliation never switches identity to the linked table.
The command fetches Combined Youth Data separately through
`AIRTABLE_COMBINED_YOUTH_DATA_TABLE_ID`, joins via the Basic `Combined Youth Data` link,
and copies only Funder, subsidy status, subsidy start date, and subsidy end date.

The four subsidy fields publish atomically. Every Basic row must resolve to exactly one
Combined record. Missing configuration, a Combined fetch or schema failure, missing link,
multiple links, or an unresolved target makes enrichment incomplete. Canonical Basic
fields may still publish, but existing subsidy fields are preserved and new rows receive
null subsidy values. The command records a versioned fail-closed health receipt and exits
non-zero. Source counts on the Youth Budget page use only the last complete receipt.

Dry run performs the complete transformation and reports exact create, update, skip, and
orphan-delete counts without writes. An empty canonical pull is refused before orphan
calculation. On apply, orphan deletion, creates, and updates share one database transaction.

---

## 2. Serving downstream (outbound)

Three patterns exist; pick per consumer:

| Consumer | Mechanism | When |
| --- | --- | --- |
| Next.js site | DRF API (`api/urls.py`) | Live reporting reads |
| Sibling "Zazi" backend | Internal export endpoints, `X-Internal-Auth` vs `MASI_INTERNAL_API_SECRET` | Server-to-server |
| **Streamlit portal** | **Parquet snapshot** written into `../../Masi_Data_Site/masi_data_streamlit/data/parquet/raw/` | Fast, file-based, batch datasets |

The Streamlit app does **not** connect to Postgres today (it reads CSV/parquet/Airtable). For the
2026 assessments we produce a wide parquet via an **export management command** (§6). Direct
Streamlit→Postgres (`EXTERNAL_DATABASE_URL`) remains a future option, not the current build.

---

## 3. Environment (verified names, in this repo's `.env`)

`AIRTABLE_TOKEN` (newer) / `AIRTABLE_API_KEY` (older); per-table `*_BASE_ID`/`*_TABLE_ID`
(e.g. `AIRTABLE_LITERACY_ASSESSMENTS_2026_BASE_ID` / `..._TABLE_ID`). DB: `DATABASE_URL`
(Django, via `dj_database_url`); `EXTERNAL_/INTERNAL_/PROD_DATABASE_URL` for external consumers.
The `.env` has spaces around some `=` → **`bash source` chokes; parse in Python** if scripting.

---

## 4. Cadence — match the data, don't cron by reflex

Only **literacy sessions** and **numeracy sessions** run as nightly crons today. **Assessments
happen in ~30-day windows** a few times a year — outside a window nothing changes, so an
assessment sync is a **once-off / per-window on-demand** command, not a nightly cron.

---

## 5. As-verified current state (2026-H1) — *fact, re-checkable*

Supersedes stale specifics in the March audit where they conflict (e.g. `CanonicalChild` with
UID keys and the 2026 session models now **exist**; the plan predates them).

### Canonical is real but **fragmented across Airtable bases** — the core thing to nail down
- Django-synced canonical dimensions: `CanonicalChild` (`canonical_children`, `child_uid`,
  synced from base `app6ayjg1NwvYdZQf` / `tbleBg6n4f3dcJ8vJ` "Child Registry"), `School`
  (`school_uid`), `Youth` (`youth_uid`), `Mentor`.
- **But** the 2026 assessments base `appEcfbzkyFQZbwzH` carries its **own** `Child DB` /
  `School DB` / `Youth DB` copies (`tbldSBbdPYtrGHJOy` / `tblbR9MwPdZdxaJkc` / `tbliPjagXTJ15Pt9p`).
  So the same entity may exist in ≥2 Airtable bases. "One canonical source, linked by PKs" is the
  *goal*; confirming these copies reconcile by UID is the foundational work.
- Canonical-key drift: strategic plan says `mcode`/`employee_id`; implementation uses UID strings.
  Decide the single canonical key per entity and document it.

### The 2026 assessments base `appEcfbzkyFQZbwzH`
| Table | ID | Grain / note |
| --- | --- | --- |
| Assessments DB | `tblISTxhZj7rMiBWp` | **Long**: 1 row/child × term × year. ~13,860 rows (2025 **and** 2026). Join key `Child UID`. 11 raw sub-scores + `Total`. |
| 2026 On The Programme | `tbliHph1VYATZnYKA` | Per-child roster ~1,388. `All Sessions Count v2`, `Mentor`, `2026 On The Programme` (Yes). |
| Child / School / Youth DB | see above | Base-local dimension copies. |
| Child Assessment Tracker | `tblUYwKCNWicHBFbm` | 1 row/child × window; collection logistics. |

### ⚠️ Verified caveats
1. **`2026 On The Programme.All Sessions Count v2` is a static `number`, not a live rollup** — the
   OTP table doesn't even link to a sessions table. It reconciles with real `LiteracySession2026`
   row-counts for only **46 / 1,388** children. **Do not treat it as an authoritative session
   total.** The true session-events source for a per-`child_uid` count is still to be confirmed.
2. **On-the-Programme lost granularity**: 2025 had `Yes/No/Awaiting/Left/Absent`; 2026 is
   presence-in-roster = Yes, absence = No.
3. **`Grade` includes ECD centre-names** as options → normalise non-grade values to `PreR`.
4. **Duplicates**: ~91 `(child, term)` pairs in 2026 → dedupe on `duplicate_status`/`capture_status`.
5. **2026 matched pairs**: of ~3,946 children with 2026 rows, only ~**1,034** have both Jan and Jun
   (the computable-midline set).

---

## 6. The 2026 midline literacy assessments pipeline — *decided direction, spec pending*

This is Phase-4 assessment work pulled forward to meet an urgent analysis need, built to be
**forward-compatible** with the canonical foundation (keys on UIDs; FKs to existing dimensions).

**New models** (`api/models.py`):
- `LiteracyAssessment2026` — **long** (1 row per child × term × year), upsert `source_airtable_id`,
  business key `child_uid`, FKs to `CanonicalChild`/`School` (assessor→`Youth`), 11 raw sub-scores +
  total, `year`/`term`, `duplicate_status`/`capture_status`. Stores full cross-year history;
  diverges from the wide `Assessment2025` on purpose (wideness is a projection concern).
- `OnTheProgramme2026` — per-child roster (mentor, on-programme, session count) — **interim**
  dimension pending the session-source reconciliation in §5 caveat 1. Long-term these are *derived*.

**New commands** (`api/management/commands/`):
- `sync_airtable_literacy_assessments_2026.py` — Airtable → `LiteracyAssessment2026` (convention §1).
- `sync_airtable_on_the_programme_2026.py` — Airtable → `OnTheProgramme2026`.
- `export_literacy_2026_parquet.py` — ORM read → filter `Year=2026` → dedupe → **pivot long→wide**
  (`Jan - {skill}` / `June - {skill}`) → join enrichment → resolve dimension names → write
  `../../Masi_Data_Site/masi_data_streamlit/data/parquet/raw/2026_literacy_midline.parquet`,
  columns matching the 2025 wide sheet.

**Testing:** command unit tests over Airtable-shaped fixtures (dedupe kills the ~91 dups; pivot
lands Jan/Jun correctly; enrichment join; `Year` filter; matched-pair count ≈ 1,034) + an
independent Airtable-vs-parquet reconciliation script + golden-row hand-traces.

**Open items (owner: data/ops):** provenance of `2026 On The Programme`; the true literacy
session-events table so Total Sessions can be *derived*, not ingested from the unreliable rollup.

---

## 7. 2026 numeracy assessments pipeline

The numeracy pipeline uses the same long-fact plus roster-projection architecture, but it does not
reuse the 2025 name-based merge. All identity resolution and analysis use `child_uid`.

### Source configuration

- Assessments: `AIRTABLE_NUMERACY_2026_ASSESSMENTS_BASE_ID` and
  `AIRTABLE_NUMERACY_2026_ASSESSMENTS_TABLE_ID`
- Roster: `AIRTABLE_NUMERACY_ON_THE_PROGRAMME_2026_BASE_ID` and
  `AIRTABLE_NUMERACY_ON_THE_PROGRAMME_2026_TABLE_ID`
- Authentication: `AIRTABLE_TOKEN`, with `AIRTABLE_API_KEY` as the fallback

`NumeracyAssessment2026` preserves every raw source event, including missing child UIDs and duplicate
business groups. `NumeracyOnTheProgramme2026` is a separate one-row-per-child roster. Assessment
upserts use Airtable record ID. Roster upserts resolve Airtable record ID first and child UID second,
which safely adopts a recreated source record.

Publication is fail closed for operational integrity failures: failed or incomplete latest syncs,
guarded retirement failures, duplicate roster UIDs, a truncated pull, an invalid output shape, or
reconciliation drift. Record-level data quality does not make the whole dashboard unavailable.
Instead, missing H1 UIDs, unresolved canonical identities, conflicting duplicates, and invalid
component scores are written to a correction report and the affected assessment group is
quarantined. Its roster row remains in the parquet, its affected term scores remain null, and its
exclusion flag and reason are explicit. Scores are never clipped or averaged. Identical duplicates
are the only duplicate class resolved automatically, using the lexicographically smallest Airtable
record ID for deterministic selection.

The export writes three sibling artifacts atomically where applicable:

- `2026_numeracy_midline.parquet`: roster-shaped results with quality flags
- `2026_numeracy_quality_exceptions.csv`: name-free source correction queue
- `2026_numeracy_quality_summary.json`: aggregate counts for Streamlit

Streamlit presents the aggregate quarantine count on the results page and exposes the correction
queue only on the internal `2026 Numeracy Data Quality` page. After correcting Airtable, rerun both
sync commands, export, and reconciliation locally. Do not run the exporter on Render because its
output target is the sibling local Streamlit repository.

Run against the configured local Postgres database only:

```bash
venv/bin/python manage.py sync_airtable_numeracy_assessments_2026 --dry-run --verbose
venv/bin/python manage.py sync_airtable_numeracy_on_programme_2026 --dry-run --verbose
venv/bin/python manage.py sync_airtable_numeracy_assessments_2026
venv/bin/python manage.py sync_airtable_numeracy_on_programme_2026
venv/bin/python manage.py export_numeracy_2026_parquet --dry-run
venv/bin/python manage.py export_numeracy_2026_parquet
venv/bin/python manage.py reconcile_numeracy_2026 \
  --golden-uid CH-EXAMPLE1 --golden-uid CH-EXAMPLE2 --golden-uid CH-EXAMPLE3
```

For local diagnosis when an operational sync gate blocks the ordinary dry run, use
`export_numeracy_2026_parquet --dry-run --force`. This produces the name-free source-correction CSV
but cannot publish a parquet. There is no numeracy assessment cron because assessment collection is
window-based.
