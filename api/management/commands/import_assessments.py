# api/management/commands/import_assessments.py

import csv
from django.core.management.base import BaseCommand
from django.db import transaction
from api.models import WELA_assessments

class Command(BaseCommand):
    help = 'Import student assessment data from CSV file'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the CSV file')
        parser.add_argument('--year', type=int, required=True, help='Assessment year (2022, 2023, 2024)')
        parser.add_argument('--update', action='store_true', help='Update existing records')
        parser.add_argument('--dry-run', action='store_true', help='Test run without saving to database')

    def safe_int(self, value):
        """Safely convert value to int, return None if invalid"""
        if not value or str(value).strip() == '' or str(value).strip().lower() == 'none':
            return None
        try:
            return int(float(str(value).strip()))
        except (ValueError, TypeError):
            return None

    def safe_str(self, value):
        """Safely convert value to string, return empty string if None"""
        if value is None:
            return ''
        return str(value).strip()

    def handle(self, *args, **kwargs):
        csv_file_path = kwargs['csv_file']
        assessment_year = kwargs['year']
        update_existing = kwargs['update']
        dry_run = kwargs['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE - No data will be saved"))
        
        records_created = 0
        records_updated = 0
        records_skipped = 0
        errors = 0
        
        with open(csv_file_path, 'r', encoding='utf-8-sig') as file:
            reader = csv.DictReader(file)
            
            # Print column headers for debugging
            self.stdout.write(f"CSV columns found: {list(reader.fieldnames)}")
            
            with transaction.atomic():
                for row_num, row in enumerate(reader, 1):
                    try:
                        mcode = self.safe_str(row.get('Mcode', ''))
                        if not mcode:
                            self.stdout.write(self.style.WARNING(f"Row {row_num}: No Mcode found, skipping"))
                            records_skipped += 1
                            continue
                        
                        # Check if record exists
                        try:
                            assessment = WELA_assessments.objects.get(mcode=mcode, assessment_year=assessment_year)
                            exists = True
                        except WELA_assessments.DoesNotExist:
                            assessment = WELA_assessments(mcode=mcode, assessment_year=assessment_year)
                            exists = False
                        
                        if exists and not update_existing:
                            self.stdout.write(f"Row {row_num}: Assessment for {mcode} ({assessment_year}) already exists, skipping")
                            records_skipped += 1
                            continue
                        
                        # Map CSV columns to model fields
                        assessment.school = self.safe_str(row.get('School', ''))
                        assessment.city = self.safe_str(row.get('City', ''))
                        assessment.centre = self.safe_str(row.get('Centre', ''))
                        assessment.type = self.safe_str(row.get('Type', ''))
                        assessment.class_name = self.safe_str(row.get('Class', ''))
                        assessment.teacher = self.safe_str(row.get('Teacher', ''))
                        assessment.grade = self.safe_str(row.get('Grade', ''))
                        assessment.language = self.safe_str(row.get('Language', ''))
                        assessment.mentor = self.safe_str(row.get('Mentor', ''))
                        assessment.surname = self.safe_str(row.get('Surname', ''))
                        assessment.name = self.safe_str(row.get('Name', ''))
                        assessment.full_name = self.safe_str(row.get('Full Name', ''))
                        assessment.gender = self.safe_str(row.get('Gender', ''))[:1]  # Just first character
                        
                        assessment.total_sessions = self.safe_int(row.get('2024 Total Sessions', ''))
                        assessment.on_programme = self.safe_str(row.get('2024 On Programme', ''))
                        assessment.current_lc = self.safe_str(row.get('Current LC', ''))
                        
                        # January scores
                        assessment.jan_letter_sounds = self.safe_int(row.get('Jan - Letter Sounds', ''))
                        assessment.jan_story_comprehension = self.safe_int(row.get('Jan - Story Comprehension', ''))
                        assessment.jan_listen_first_sound = self.safe_int(row.get('Jan - Listen First Sound', ''))
                        assessment.jan_listen_words = self.safe_int(row.get('Jan - Listen Words', ''))
                        assessment.jan_writing_letters = self.safe_int(row.get('Jan - Writing Letters', ''))
                        assessment.jan_read_words = self.safe_int(row.get('Jan - Read Words', ''))
                        assessment.jan_read_sentences = self.safe_int(row.get('Jan - Read Sentences', ''))
                        assessment.jan_read_story = self.safe_int(row.get('Jan - Read Story', ''))
                        assessment.jan_write_cvcs = self.safe_int(row.get('Jan - Write CVCs', ''))
                        assessment.jan_write_sentences = self.safe_int(row.get('Jan - Write Sentences', ''))
                        assessment.jan_write_story = self.safe_int(row.get('Jan - Write Story', ''))
                        assessment.jan_total = self.safe_int(row.get('Jan - Total', ''))
                        
                        # June scores
                        assessment.june_letter_sounds = self.safe_int(row.get('June - Letter Sounds', ''))
                        assessment.june_story_comprehension = self.safe_int(row.get('June - Story Comprehension', ''))
                        assessment.june_listen_first_sound = self.safe_int(row.get('June - Listen First Sound', ''))
                        assessment.june_listen_words = self.safe_int(row.get('June - Listen Words', ''))
                        assessment.june_writing_letters = self.safe_int(row.get('June - Writing Letters', ''))
                        assessment.june_read_words = self.safe_int(row.get('June - Read Words', ''))
                        assessment.june_read_sentences = self.safe_int(row.get('June - Read Sentences', ''))
                        assessment.june_read_story = self.safe_int(row.get('June - Read Story', ''))
                        assessment.june_write_cvcs = self.safe_int(row.get('June - Write CVCs', ''))
                        assessment.june_write_sentences = self.safe_int(row.get('June - Write Sentences', ''))
                        assessment.june_write_story = self.safe_int(row.get('June - Write Story', ''))
                        assessment.june_total = self.safe_int(row.get('June - Total', ''))
                        
                        # November scores
                        assessment.nov_letter_sounds = self.safe_int(row.get('Nov - Letter Sounds', ''))
                        assessment.nov_story_comprehension = self.safe_int(row.get('Nov - Story Comprehension', ''))
                        assessment.nov_listen_first_sound = self.safe_int(row.get('Nov - Listen First Sound', ''))
                        assessment.nov_listen_words = self.safe_int(row.get('Nov - Listen Words', ''))
                        assessment.nov_writing_letters = self.safe_int(row.get('Nov - Writing Letters', ''))
                        assessment.nov_read_words = self.safe_int(row.get('Nov - Read Words', ''))
                        assessment.nov_read_sentences = self.safe_int(row.get('Nov - Read Sentences', ''))
                        assessment.nov_read_story = self.safe_int(row.get('Nov - Read Story', ''))
                        assessment.nov_write_cvcs = self.safe_int(row.get('Nov - Write CVCs', ''))
                        assessment.nov_write_sentences = self.safe_int(row.get('Nov - Write Sentences', ''))
                        assessment.nov_write_story = self.safe_int(row.get('Nov - Write Story', ''))
                        assessment.nov_total = self.safe_int(row.get('Nov - Total', ''))
                        
                        assessment.captured_by = self.safe_str(row.get('Captured by', ''))
                        
                        if not dry_run:
                            assessment.save()
                        
                        if exists:
                            records_updated += 1
                            self.stdout.write(f"Row {row_num}: Updated {mcode} ({assessment_year})")
                        else:
                            records_created += 1
                            self.stdout.write(f"Row {row_num}: Created {mcode} ({assessment_year})")
                            
                    except Exception as e:
                        errors += 1
                        self.stdout.write(
                            self.style.ERROR(f"Row {row_num}: Error processing {row.get('Mcode', 'unknown')}: {str(e)}")
                        )
                        if errors > 10:  # Stop after too many errors
                            self.stdout.write(self.style.ERROR("Too many errors, stopping import"))
                            break
                            
                if dry_run:
                    transaction.set_rollback(True)
        
        # Summary
        self.stdout.write(self.style.SUCCESS(
            f"Import complete! "
            f"{records_created} records created, "
            f"{records_updated} records updated, "
            f"{records_skipped} records skipped, "
            f"{errors} errors"
        ))