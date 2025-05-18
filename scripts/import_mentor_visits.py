import os
import sys
import django
import pandas as pd
from datetime import datetime

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "masi_website.settings")
django.setup()

from django.contrib.auth.models import User
from api.models import School, MentorVisit

# Load your CSV file
df = pd.read_csv("static/data/consolidated_visits_2.csv")

print(f"📄 Loaded {len(df)} rows")

# Loop through and insert MentorVisit records
for index, row in df.iterrows():
    try:
        # ✅ Lookup mentor by username from the new 'username' column
        mentor = User.objects.get(username=row["username"])

        # Lookup school by name
        school = School.objects.get(name=row["school"])

        # Parse visit date
        visit_date = pd.to_datetime(row["visit_date"]).date()

        # Create MentorVisit with defaults
        MentorVisit.objects.create(
            mentor=mentor,
            school=school,
            visit_date=visit_date,
            letter_trackers_correct=False,
            reading_trackers_correct=False,
            sessions_correct=False,
            admin_correct=False,
            quality_rating=None,
            supplies_needed="",
            commentary=""
        )

        print(f"✅ Row {index}: {mentor.username} @ {school.name} on {visit_date}")

    except Exception as e:
        print(f"❌ Error at row {index}: {e}")

print("🚀 Mentor visit import complete.")
