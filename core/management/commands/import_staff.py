from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import UserProfile
import csv
from django.db import transaction

class Command(BaseCommand):
    help = 'Import staff members from a CSV file and create User and UserProfile records'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Path to the CSV file')

    def handle(self, *args, **kwargs):
        csv_file_path = kwargs['csv_file']
        
        try:
            with open(csv_file_path, 'r', encoding='utf-8-sig') as file:
                # Read and print headers for debugging
                reader = csv.DictReader(file)
                headers = reader.fieldnames
                self.stdout.write(f"Found headers: {headers}")
                
                with transaction.atomic():
                    for row in reader:
                        # Print row for debugging
                        self.stdout.write(f"Processing row: {row}")
                        
                        # Create email from the data
                        email = row['Email'].strip()
                        
                        # Skip if user already exists
                        if User.objects.filter(email=email).exists():
                            self.stdout.write(
                                self.style.WARNING(
                                    f'User with email {email} already exists, skipping...'
                                )
                            )
                            continue
                        
                        # Create the user
                        user = User.objects.create(
                            username=email,  # Use email as username
                            email=email,
                            first_name=row['First Name'].strip(),
                            last_name=row['Surname'].strip(),
                            is_active=True
                        )
                        
                        # Update or create the user profile
                        UserProfile.objects.filter(user=user).update(
                            job_title=row['Job Title'].strip(),
                            project=row['Project'].strip()
                        )
                        
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'Successfully created user and profile for {email}'
                            )
                        )

                self.stdout.write(
                    self.style.SUCCESS(
                        'Staff import completed successfully!'
                    )
                )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f'Error processing file: {str(e)}'
                )
            ) 