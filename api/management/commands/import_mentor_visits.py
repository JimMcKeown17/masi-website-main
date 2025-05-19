from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from api.models import School, MentorVisit
from django.utils.timezone import make_aware
from datetime import datetime
import csv
import re

class Command(BaseCommand):
    help = 'Import mentor visits from CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the CSV file')

    def handle(self, *args, **options):
        csv_file_path = options['csv_file']
        
        # Track statistics
        total_rows = 0
        imported_count = 0
        skipped_count = 0
        
        # Process CSV file
        with open(csv_file_path, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            
            for row in reader:
                total_rows += 1
                
                try:
                    # Get associated mentor and school
                    try:
                        mentor = User.objects.get(id=row['mentor_id'])
                    except User.DoesNotExist:
                        self.stdout.write(self.style.WARNING(f"Mentor with ID {row['mentor_id']} not found, skipping row {row['id']}"))
                        skipped_count += 1
                        continue
                    
                    try:
                        school = School.objects.get(id=row['school_id'])
                    except School.DoesNotExist:
                        # Create a placeholder school if it doesn't exist
                        school = School.objects.create(
                            id=row['school_id'],
                            name=f"School {row['school_id']}",
                            is_active=True
                        )
                        self.stdout.write(self.style.WARNING(f"Created placeholder school with ID {row['school_id']}"))
                    
                    # Handle boolean values - convert 't'/'f' to True/False
                    letter_trackers_correct = self._to_bool(row['letter_trackers_correct'])
                    reading_trackers_correct = self._to_bool(row['reading_trackers_correct'])
                    sessions_correct = self._to_bool(row['sessions_correct'])
                    admin_correct = self._to_bool(row['admin_correct'])
                    
                    # Parse date fields
                    visit_date = datetime.strptime(row['visit_date'], '%Y-%m-%d').date()
                    
                    # Handle timestamp fields (created_at, updated_at)
                    created_at = None
                    updated_at = None
                    
                    if 'created_at' in row and row['created_at']:
                        created_at = self._parse_timestamp(row['created_at'])
                    
                    if 'updated_at' in row and row['updated_at']:
                        updated_at = self._parse_timestamp(row['updated_at'])
                    
                    # Check if the record already exists
                    visit = None
                    if 'id' in row and row['id']:
                        visit = MentorVisit.objects.filter(id=row['id']).first()
                    
                    if visit:
                        # Update existing record
                        visit.mentor = mentor
                        visit.school = school
                        visit.visit_date = visit_date
                        visit.letter_trackers_correct = letter_trackers_correct
                        visit.reading_trackers_correct = reading_trackers_correct
                        visit.sessions_correct = sessions_correct
                        visit.admin_correct = admin_correct
                        visit.quality_rating = int(row['quality_rating'])
                        visit.supplies_needed = row.get('supplies_needed', '')
                        visit.commentary = row.get('commentary', '')
                        
                        if created_at:
                            visit.created_at = created_at
                        if updated_at:
                            visit.updated_at = updated_at
                        
                        visit.save()
                        self.stdout.write(self.style.WARNING(f"Updated visit with ID {row['id']}"))
                    else:
                        # Create a new visit record
                        visit = MentorVisit(
                            mentor=mentor,
                            school=school,
                            visit_date=visit_date,
                            letter_trackers_correct=letter_trackers_correct,
                            reading_trackers_correct=reading_trackers_correct,
                            sessions_correct=sessions_correct,
                            admin_correct=admin_correct,
                            quality_rating=int(row['quality_rating']),
                            supplies_needed=row.get('supplies_needed', ''),
                            commentary=row.get('commentary', '')
                        )
                        
                        # Set ID if provided
                        if 'id' in row and row['id']:
                            visit.id = int(row['id'])
                        
                        # Set timestamps if provided
                        if created_at:
                            visit.created_at = created_at
                        if updated_at:
                            visit.updated_at = updated_at
                        
                        visit.save()
                        self.stdout.write(self.style.SUCCESS(f"Created new visit with ID {visit.id}"))
                    
                    imported_count += 1
                    
                    # Progress update every 50 records
                    if imported_count % 50 == 0:
                        self.stdout.write(self.style.SUCCESS(f"Imported {imported_count} records so far..."))
                        
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error importing row {row.get('id', 'unknown')}: {str(e)}"))
                    skipped_count += 1
        
        # Final stats
        self.stdout.write(self.style.SUCCESS(f"Import complete! Processed {total_rows} rows"))
        self.stdout.write(self.style.SUCCESS(f"Successfully imported: {imported_count}"))
        self.stdout.write(self.style.SUCCESS(f"Skipped: {skipped_count}"))
    
    def _to_bool(self, value):
        """Convert various string representations to boolean values"""
        if isinstance(value, bool):
            return value
        if not value or value.lower() in ('f', 'false', 'no', 'n', '0'):
            return False
        return True  # Default to True for any other value
    
    def _parse_timestamp(self, timestamp_str):
        """Parse timestamp strings with timezone information"""
        try:
            # Try ISO format first
            try:
                dt = datetime.fromisoformat(timestamp_str)
                return make_aware(dt)
            except ValueError:
                pass
            
            # Try with timezone
            timezone_pattern = r'(.+?)([+-]\d{2}(?::\d{2})?)?$'
            match = re.match(timezone_pattern, timestamp_str)
            
            if match:
                dt_str = match.group(1)
                # Try different formats
                for fmt in [
                    '%Y-%m-%d %H:%M:%S.%f',  # With microseconds
                    '%Y-%m-%d %H:%M:%S',     # Without microseconds
                    '%Y-%m-%d'               # Just date
                ]:
                    try:
                        dt = datetime.strptime(dt_str.strip(), fmt)
                        return make_aware(dt)
                    except ValueError:
                        continue
            
            # Fallback to basic format
            return make_aware(datetime.strptime(timestamp_str.split('+')[0].strip(), '%Y-%m-%d %H:%M:%S.%f'))
        except Exception as e:
            raise ValueError(f"Failed to parse timestamp '{timestamp_str}': {str(e)}")