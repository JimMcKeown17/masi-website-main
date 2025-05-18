# Create this file at: dashboards/management/commands/delete_fake_data.py

from django.core.management.base import BaseCommand
from api.models import School, MentorVisit
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Deletes fake data used for testing'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("WARNING: This will delete all MentorVisit and School records."))
        confirm = input("Are you sure you want to proceed? (yes/no): ")
        
        if confirm.lower() != 'yes':
            self.stdout.write(self.style.WARNING("Deletion aborted."))
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
        
        self.stdout.write(self.style.SUCCESS(f"Successfully deleted:"))
        self.stdout.write(self.style.SUCCESS(f"- {visit_count} mentor visits"))
        self.stdout.write(self.style.SUCCESS(f"- {school_count} schools"))
        if keep_users.lower() != 'yes':
            self.stdout.write(self.style.SUCCESS(f"- {user_count} non-superuser user accounts"))
        
        self.stdout.write(self.style.SUCCESS("\nYour database is now ready for real data."))