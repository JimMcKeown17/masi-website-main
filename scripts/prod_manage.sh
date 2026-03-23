#!/bin/bash
# Run a manage.py command against the PRODUCTION database.
# Usage: ./scripts/prod_manage.sh <command> [args...]
#
# Examples:
#   ./scripts/prod_manage.sh migrate
#   ./scripts/prod_manage.sh sync_airtable_children
#   ./scripts/prod_manage.sh shell
#
# CAUTION: This targets the live Render database. Double-check before running.

set -e

if [ $# -eq 0 ]; then
    echo "Usage: ./scripts/prod_manage.sh <command> [args...]"
    echo "This runs manage.py against the PRODUCTION database."
    exit 1
fi

cd "$(dirname "$0")/.."
source venv/bin/activate

# Load .env to get PROD_DATABASE_URL
PROD_URL=$(grep '^PROD_DATABASE_URL=' .env | cut -d'=' -f2- | tr -d '"')

if [ -z "$PROD_URL" ]; then
    echo "ERROR: PROD_DATABASE_URL not found in .env"
    exit 1
fi

echo "WARNING: Running against PRODUCTION database"
echo "Command: python manage.py $@"
read -p "Continue? (y/N) " confirm
if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo "Aborted."
    exit 0
fi

DATABASE_URL="$PROD_URL" python manage.py "$@"
