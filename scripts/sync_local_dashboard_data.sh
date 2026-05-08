#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")/.."
source venv/bin/activate

DRY_RUN=false

if [ "${1:-}" = "--dry-run" ]; then
    DRY_RUN=true
fi

if [ "$DRY_RUN" = true ]; then
    echo "Running dashboard data sync in DRY RUN mode (no DB writes)"
    python manage.py sync_airtable_children --dry-run
    python manage.py sync_airtable_schools --dry-run
    python manage.py sync_airtable_staff --dry-run
    python manage.py sync_airtable_youth --dry-run
    python manage.py sync_airtable_literacy_sessions_2026 --dry-run
    python manage.py sync_airtable_numeracy_sessions_2026 --dry-run
    echo "Dry run complete."
    exit 0
fi

echo "Running full local dashboard data sync..."
python manage.py sync_airtable_children
python manage.py sync_airtable_schools
python manage.py sync_airtable_staff
python manage.py sync_airtable_youth
python manage.py sync_airtable_literacy_sessions_2026
python manage.py sync_airtable_numeracy_sessions_2026
python manage.py resolve_session_fks
echo "Local dashboard data sync complete."
