import csv
from django.core.management.base import BaseCommand
from dashboards.models import School

class Command(BaseCommand):
    help = 'Import or update schools from CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the CSV file')
        parser.add_argument('--update', action='store_true', help='Update existing records')

    def handle(self, *args, **kwargs):
        csv_file_path = kwargs['csv_file']
        update_existing = kwargs['update']
        
        with open(csv_file_path, 'r', encoding='utf-8-sig') as file:  # Use utf-8-sig to handle BOM
            reader = csv.DictReader(file)
            schools_created = 0
            schools_updated = 0
            
            for row in reader:
                # The column name might be 'name' or '\ufeffname' due to BOM
                school_name = row.get('name', '')
                if not school_name and '\ufeffname' in row:
                    school_name = row.get('\ufeffname', '')
                
                school_type = row.get('type', '')
                
                if not school_name:
                    self.stdout.write(self.style.WARNING(f"Skipping row - no school name found: {row}"))
                    continue
                    
                school, created = School.objects.get_or_create(
                    name=school_name,
                    defaults={
                        'type': school_type,
                        'is_active': True
                    }
                )
                
                if created:
                    schools_created += 1
                    self.stdout.write(self.style.SUCCESS(f"Created school: {school_name}"))
                elif update_existing:
                    # Update existing school with new data
                    school.type = school_type
                    school.save()
                    schools_updated += 1
                    self.stdout.write(self.style.WARNING(f"Updated school: {school_name}"))
                else:
                    self.stdout.write(self.style.WARNING(f"School already exists (not updated): {school_name}"))
            
            self.stdout.write(self.style.SUCCESS(
                f"Import complete! {schools_created} schools created, {schools_updated} schools updated."
            ))