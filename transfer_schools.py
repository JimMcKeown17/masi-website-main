import os
import django

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "masi_website.settings")
django.setup()

from dashboards.models import School as OldSchool
from api.models import School as NewSchool

def transfer_schools():
    # Get all schools from the old model
    old_schools = OldSchool.objects.all()
    print(f"Found {old_schools.count()} schools to transfer")
    
    # Create new schools based on the old data
    for old_school in old_schools:
        new_school = NewSchool(
            name=old_school.name,
            type=old_school.type,
            latitude=old_school.latitude if hasattr(old_school, 'latitude') else None,
            longitude=old_school.longitude if hasattr(old_school, 'longitude') else None,
            address=old_school.address if hasattr(old_school, 'address') else None,
            contact_phone=old_school.contact_phone if hasattr(old_school, 'contact_phone') else None,
            contact_email=old_school.contact_email if hasattr(old_school, 'contact_email') else None,
            contact_person=old_school.contact_person if hasattr(old_school, 'contact_person') else None,
            is_active=old_school.is_active if hasattr(old_school, 'is_active') else True,
            # New fields
            airtable_id=None,
            site_type=None,
        )
        new_school.save()
        print(f"Transferred school: {new_school.name}")
    
    print("School transfer completed!")

if __name__ == "__main__":
    transfer_schools()