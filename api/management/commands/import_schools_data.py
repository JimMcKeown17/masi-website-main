import csv
from django.core.management.base import BaseCommand
from api.models import School  # Adjust if your app is named differently

class Command(BaseCommand):
    help = 'Import and update School data from CSV using school_id as reference, or create new ones if missing'

    def add_arguments(self, parser):
        parser.add_argument('csv_path', type=str, help='Path to the CSV file')

    def handle(self, *args, **options):
        csv_path = options['csv_path']

        with open(csv_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            updated = 0
            created = 0
            skipped = []

            for row in reader:
                school_id_raw = row.get('School ID') or row.get('\ufeffSchool ID')
                try:
                    school_id = int(school_id_raw)
                except (ValueError, TypeError):
                    self.stdout.write(self.style.WARNING(f"Invalid or missing School ID in row: {row}"))
                    continue

                school = School.objects.filter(school_id=school_id).first()

                if not school:
                    school = School(school_id=school_id)
                    created += 1
                else:
                    updated += 1

                # Update or set fields
                school.name = row.get('School', school.name) or school.name
                school.type = row.get('Type', school.type) or school.type
                school.address = row.get('Address', school.address) or school.address
                school.city = row.get('City', school.city) or school.city
                school.principal = row.get('Principal', school.principal) or school.principal
                school.actively_working_in = row.get('Actively Working In', school.actively_working_in) or school.actively_working_in

                try:
                    lat = row.get('Latitude', '').strip()
                    if lat:
                        school.latitude = float(lat)
                except ValueError:
                    self.stdout.write(self.style.WARNING(f"Invalid latitude for School ID {school_id}"))

                try:
                    lon = row.get('Longitude', '').strip()
                    if lon:
                        school.longitude = float(lon)
                except ValueError:
                    self.stdout.write(self.style.WARNING(f"Invalid longitude for School ID {school_id}"))

                school.save()

        self.stdout.write(self.style.SUCCESS(f"{updated} schools updated successfully."))
        self.stdout.write(self.style.SUCCESS(f"{created} new schools created successfully."))
