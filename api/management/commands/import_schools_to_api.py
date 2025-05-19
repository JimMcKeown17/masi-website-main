import csv
from decimal import Decimal
from django.core.management.base import BaseCommand
from api.models import School

class Command(BaseCommand):
    help = 'Import or update schools from CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the CSV file')
        parser.add_argument('--update', action='store_true', help='Update existing records')

    def handle(self, *args, **kwargs):
        csv_file_path = kwargs['csv_file']
        update_existing = kwargs['update']
        
        with open(csv_file_path, 'r', encoding='utf-8-sig') as file:  # utf-8-sig handles BOM
            reader = csv.DictReader(file)
            schools_created = 0
            schools_updated = 0
            schools_skipped = 0
            
            for row in reader:
                try:
                    # Extract all fields from CSV
                    school_id = int(row.get('School ID', '0').strip())
                    school_name = row.get('School', '').strip()
                    school_type = row.get('Type', '').strip()
                    address = row.get('Address', '').strip()
                    city = row.get('City', '').strip()
                    
                    # Handle potential empty or malformed lat/long values
                    latitude_str = row.get('Latitude', '').strip()
                    longitude_str = row.get('Longitude', '').strip()
                    
                    latitude = None
                    longitude = None
                    
                    if latitude_str and latitude_str.lower() != 'none':
                        try:
                            latitude = Decimal(latitude_str)
                        except (ValueError, TypeError):
                            self.stdout.write(self.style.WARNING(f"Invalid latitude for {school_name}: {latitude_str}"))
                    
                    if longitude_str and longitude_str.lower() != 'none':
                        try:
                            longitude = Decimal(longitude_str)
                        except (ValueError, TypeError):
                            self.stdout.write(self.style.WARNING(f"Invalid longitude for {school_name}: {longitude_str}"))
                    
                    principal = row.get('Principal', '').strip()
                    contact_person = row.get('Main Contact', '').strip()
                    contact_phone = row.get('Main Contact Phone Number', '').strip()
                    actively_working_in = row.get('Actively Working In', '').strip()
                    
                    if not school_name:
                        self.stdout.write(self.style.WARNING(f"Skipping row - no school name found: {row}"))
                        schools_skipped += 1
                        continue
                        
                    if not school_id:
                        self.stdout.write(self.style.WARNING(f"Skipping row - no school ID found: {row}"))
                        schools_skipped += 1
                        continue
                    
                    # Check if school exists by school_id (primary identifier)
                    try:
                        school = School.objects.get(school_id=school_id)
                        created = False
                    except School.DoesNotExist:
                        # Also try to match by name if school_id doesn't match
                        try:
                            school = School.objects.get(name=school_name)
                            created = False
                            # Update the school_id for existing record that was matched by name
                            school.school_id = school_id
                        except School.DoesNotExist:
                            # If no match by ID or name, we'll create a new school
                            school = School(school_id=school_id)
                            created = True
                    
                    if created or update_existing:
                        # Set or update all fields
                        school.name = school_name
                        school.type = school_type
                        school.latitude = latitude
                        school.longitude = longitude
                        school.address = address
                        school.city = city
                        school.principal = principal
                        school.contact_person = contact_person
                        school.contact_phone = contact_phone
                        school.actively_working_in = actively_working_in
                        school.is_active = True
                        school.save()
                        
                        if created:
                            schools_created += 1
                            self.stdout.write(self.style.SUCCESS(f"Created school: {school_name} (ID: {school_id})"))
                        else:
                            schools_updated += 1
                            self.stdout.write(self.style.WARNING(f"Updated school: {school_name} (ID: {school_id})"))
                    else:
                        self.stdout.write(self.style.WARNING(f"School already exists (not updated): {school_name} (ID: {school_id})"))
                        schools_skipped += 1
                        
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error processing row: {row}"))
                    self.stdout.write(self.style.ERROR(f"Exception: {str(e)}"))
                    schools_skipped += 1
            
            self.stdout.write(self.style.SUCCESS(
                f"Import complete! {schools_created} schools created, {schools_updated} schools updated, {schools_skipped} schools skipped."
            ))