import os
import random
from datetime import datetime, timedelta

# Setup Django environment FIRST - before any Django imports
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'masi_website.settings')

import django
django.setup()

# Now import Django modules after setup
from django.utils import timezone
from django.contrib.auth.models import User
from dashboards.models import School, MentorVisit

def create_fake_schools(num_schools=10):
    """Create fake school data"""
    school_types = ['ECDC', 'Primary School', 'Secondary School', 'Other']
    school_names = [
        "Fumisukoma Primary", "Ngwebeni Primary", "Kwabhekokuhle ECDC", 
        "Mavela Secondary", "Siyahlomula Primary", "Emadwaleni Secondary",
        "Sakhumzi ECDC", "Nkululeko Primary", "Ikusasalethu Secondary",
        "Siphumele Primary", "Zamokuhle ECDC", "Masibambane Secondary",
        "Vukuzakhe Primary", "Thembelihle Secondary", "Khanyisani ECDC",
        "Sizanani Primary", "Siyathuthuka Secondary", "Thembalethu ECDC",
        "Sinethemba Primary", "Vulamehlo Secondary"
    ]
    
    created_schools = []
    
    # Use a subset of school names
    selected_names = random.sample(school_names, min(num_schools, len(school_names)))
    
    for name in selected_names:
        school_type = name.split()[-1] if name.split()[-1] in school_types else random.choice(school_types)
        
        school = School.objects.create(
            name=name,
            type=school_type,
            latitude=random.uniform(-33.9, -33.4),  # South Africa KZN region
            longitude=random.uniform(25.0, 26.0),
            address=f"{random.randint(1, 100)} Main Road, {random.choice(['Durban', 'Pietermaritzburg', 'Richards Bay', 'Newcastle'])}",
            contact_phone=f"07{random.randint(10000000, 99999999)}",
            contact_email=f"contact@{name.lower().replace(' ', '')}.edu.za",
            contact_person=random.choice(["Mr. Ndlovu", "Mrs. Mkhize", "Ms. Zulu", "Mr. Mthembu", "Mrs. Dlamini"]),
            is_active=random.choices([True, False], weights=[0.9, 0.1])[0],
        )
        created_schools.append(school)
        print(f"Created school: {school.name}")
    
    return created_schools

def create_fake_mentors(num_mentors=5):
    """Create fake mentor users"""
    mentor_names = [
        ("Buyiswa", "Xaba"), ("Fiks", "Mahola"), ("Chombe", "Gqabu"), 
        ("Zama", "Zulu"), ("michael", "Brown"), ("jennifer", "Davis"),
        ("robert", "Miller"), ("patricia", "Wilson"), ("james", "Moore"),
        ("elizabeth", "Taylor")
    ]
    
    created_mentors = []
    
    # Use a subset of mentor names
    selected_mentors = random.sample(mentor_names, min(num_mentors, len(mentor_names)))
    
    for first, last in selected_mentors:
        username = f"{first.lower()}.{last.lower()}"
        email = f"{username}@masiproject.org"
        
        # Check if user already exists
        if User.objects.filter(username=username).exists():
            user = User.objects.get(username=username)
        else:
            user = User.objects.create_user(
                username=username,
                email=email,
                password="password123",  # Simple password for test accounts
                first_name=first.capitalize(),
                last_name=last.capitalize()
            )
            user.save()
        
        created_mentors.append(user)
        print(f"Created/retrieved mentor user: {user.username}")
    
    return created_mentors

def create_fake_visits(mentors, schools, num_visits=50):
    """Create fake mentor visits data"""
    # Generate visits over the last 3 months
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=90)
    
    for _ in range(num_visits):
        # Random date within the last 3 months
        random_days = random.randint(0, (end_date - start_date).days)
        visit_date = start_date + timedelta(days=random_days)
        
        # Randomly select mentor and school
        mentor = random.choice(mentors)
        school = random.choice(schools)
        
        # Create random visit data with some patterns for dashboard visualization
        visit = MentorVisit.objects.create(
            mentor=mentor,
            school=school,
            visit_date=visit_date,
            letter_trackers_correct=random.choices([True, False], weights=[0.7, 0.3])[0],
            reading_trackers_correct=random.choices([True, False], weights=[0.6, 0.4])[0],
            sessions_correct=random.choices([True, False], weights=[0.8, 0.2])[0],
            admin_correct=random.choices([True, False], weights=[0.5, 0.5])[0],
            quality_rating=random.choices(range(1, 11), weights=[0.05, 0.05, 0.1, 0.1, 0.2, 0.2, 0.1, 0.1, 0.05, 0.05])[0],
            supplies_needed=random.choice([
                "Need more letter trackers and pencils", 
                "Running low on reading booklets", 
                "No supplies needed at this time",
                "Need replacement whiteboards",
                ""
            ]) if random.random() > 0.5 else "",
            commentary=random.choice([
                "Sessions are going well. Students are engaged and making progress.",
                "TAs need additional training on the reading assessment protocol.",
                "School principal was present and very supportive of the program.",
                "Several students were absent due to transportation issues.",
                "Had to reschedule some sessions due to a school event.",
                "Noticed significant improvement in student reading levels since last visit."
            ]) if random.random() > 0.3 else ""
        )
        print(f"Created visit: {visit}")

def main():
    print("Generating fake data for MASI Dashboard...")
    
    # Check if there's already data
    existing_schools = School.objects.count()
    existing_visits = MentorVisit.objects.count()
    
    print(f"Found {existing_schools} existing schools and {existing_visits} existing visits")
    
    if existing_schools > 0 and existing_visits > 0:
        confirm = input("Data already exists in the database. Do you want to add more fake data? (y/n): ")
        if confirm.lower() != 'y':
            print("Aborted. No changes made to the database.")
            return
    
    # Create fake data
    schools = create_fake_schools(15)
    mentors = create_fake_mentors(5)
    create_fake_visits(mentors, schools, 100)
    
    print("\nFake data generation complete!")
    print(f"Created {len(schools)} schools, {len(mentors)} mentors, and {MentorVisit.objects.count() - existing_visits} visit records")
    print("\nYou can now build your dashboards with this test data.")
    print("Remember to delete this data before going live by running:")
    print("python manage.py flush")

if __name__ == "__main__":
    main()