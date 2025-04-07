import os
import sys

# Setup Django environment FIRST - before any Django imports
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'masi_website.settings')

import django
django.setup()

# Import models after setting up Django
from dashboards.models import School, MentorVisit
from django.contrib.auth.models import User

def delete_fake_data():
    """Delete all fake data created for testing"""
    
    print("WARNING: This will delete all MentorVisit and School records.")
    confirm = input("Are you sure you want to proceed? (yes/no): ")
    
    if confirm.lower() != 'yes':
        print("Deletion aborted.")
        return
    
    # Option to keep real users
    keep_users = input("Do you want to keep user accounts? (yes/no): ")
    
    # Delete in proper order to respect foreign key constraints
    visit_count = MentorVisit.objects.count()
    MentorVisit.objects.all().delete()
    
    school_count = School.objects.count()
    School.objects.all().delete()
    
    user_count = 0
    if keep_users.lower() != 'yes':
        # Keep superuser accounts
        user_count = User.objects.filter(is_superuser=False).count()
        User.objects.filter(is_superuser=False).delete()
    
    print(f"Successfully deleted:")
    print(f"- {visit_count} mentor visits")
    print(f"- {school_count} schools")
    if keep_users.lower() != 'yes':
        print(f"- {user_count} non-superuser user accounts")
    
    print("\nYour database is now ready for real data.")

if __name__ == "__main__":
    delete_fake_data()