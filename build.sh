#!/bin/bash
# Exit on error
set -e

echo "Starting build process..."

# Install Python dependencies
pip install -r requirements.txt

# Install Node.js dependencies if they're not already installed
if [ -f "package.json" ]; then
  echo "Installing Node.js dependencies..."
  npm install
fi

# Compile SCSS to CSS using your existing npm script
if [ -f "package.json" ]; then
  echo "Compiling SCSS to CSS..."
  npm run sass-build
fi

# Run database migrations
echo "Running database migrations..."
python manage.py migrate

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# If in production environment, upload to Google Cloud Storage
echo "Syncing static files to Google Cloud Storage..."
gsutil -m rsync -r staticfiles/ gs://masi-website/
echo "Static files synced to Google Cloud Storage"

echo "Build process completed!"