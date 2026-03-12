from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

# Existing choices
SCHOOL_TYPE_CHOICES = [
    ('ECDC', 'Early Childhood Development'),
    ('Primary School', 'Primary School'),
    ('Secondary School', 'Secondary School'),
    ('Other', 'Other')
]

# New choices
EMPLOYMENT_STATUS_CHOICES = [
    ('Active', 'Active'),
    ('Inactive', 'Inactive')
]

GENDER_CHOICES = [
    ('Male', 'Male'),
    ('Female', 'Female'),
    ('Other', 'Other')
]

RACE_CHOICES = [
    ('Black African', 'Black African'),
    ('Coloured', 'Coloured'),
    ('White', 'White'),
    ('Indian/Asian', 'Indian/Asian'),
    ('Other', 'Other')
]

ACCOUNT_TYPE_CHOICES = [
    ('Savings', 'Savings'),
    ('Current', 'Current'),
    ('Cheque', 'Cheque')
]

ID_TYPE_CHOICES = [
    ('RSA ID', 'RSA ID'),
    ('Foreign ID', 'Foreign ID'),
    ('Passport', 'Passport')
]

class School(models.Model):
    """Model representing a school where youth work and children learn"""
    school_id = models.IntegerField(null=True, blank=True, help_text="School ID from CSV import")
    airtable_id = models.CharField(max_length=100, blank=True, null=True, unique=True, help_text="Airtable record ID")
    school_uid = models.CharField(max_length=50, blank=True, null=True, unique=True, db_index=True, help_text="SCH-XXXXX format UID — join key for 2026 session tables")
    school_number = models.IntegerField(null=True, blank=True, help_text="Auto-increment number from Airtable")
    name = models.CharField(max_length=200)
    type = models.CharField(max_length=200, choices=SCHOOL_TYPE_CHOICES, blank=True, null=True)
    suburb = models.CharField(max_length=100, blank=True, null=True)
    site_type = models.CharField(max_length=100, blank=True, null=True, help_text="Site type from Airtable")
    latitude = models.DecimalField(max_digits=10, decimal_places=8, blank=True, null=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=8, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    contact_phone = models.CharField(max_length=40, blank=True, null=True)
    contact_email = models.EmailField(blank=True, null=True)
    contact_person = models.CharField(max_length=200, blank=True, null=True)
    principal = models.CharField(max_length=200, blank=True, null=True)  # Adding principal field to match CSV
    city = models.CharField(max_length=100, blank=True, null=True)  # Adding city field to match CSV
    actively_working_in = models.CharField(max_length=5, blank=True, null=True)  # For "Actively Working In" column
    is_active = models.BooleanField(default=True)
    date_added = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['name']
        verbose_name = "School"
        verbose_name_plural = "Schools"


class Youth(models.Model):
    """Model representing a youth/literacy coach"""
    # Identification
    airtable_id = models.CharField(max_length=100, blank=True, null=True, unique=True, help_text="Airtable record ID")
    employee_id = models.IntegerField(unique=True)
    youth_uid = models.CharField(max_length=50, blank=True, null=True, unique=True, db_index=True, help_text="YTH-XXXX format UID — join key for 2026 session tables")
    first_names = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    full_name = models.CharField(max_length=255, blank=True)
    
    # Demographics
    dob = models.DateField(verbose_name="Date of Birth", blank=True, null=True)
    age = models.IntegerField(blank=True, null=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, null=True)
    race = models.CharField(max_length=100, choices=RACE_CHOICES, blank=True, null=True)
    
    # ID information
    id_type = models.CharField(max_length=50, choices=ID_TYPE_CHOICES, blank=True, null=True)
    rsa_id_number = models.CharField(max_length=50, blank=True, null=True)
    foreign_id_number = models.CharField(max_length=50, blank=True, null=True)
    
    # Contact information
    cell_phone_number = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    emergency_number = models.CharField(max_length=40, blank=True, null=True)
    
    # Address
    street_number = models.CharField(max_length=50, blank=True, null=True)
    street_address = models.CharField(max_length=255, blank=True, null=True)
    suburb_township = models.CharField(max_length=255, blank=True, null=True)
    city_or_town = models.CharField(max_length=255, blank=True, null=True)
    postal_code = models.CharField(max_length=50, blank=True, null=True)
    
    # Employment details
    job_title = models.CharField(max_length=100, blank=True, null=True)
    employment_status = models.CharField(max_length=50, choices=EMPLOYMENT_STATUS_CHOICES, default='Active')
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    reason_for_leaving = models.CharField(max_length=255, blank=True, null=True)
    income_tax_number = models.CharField(max_length=50, blank=True, null=True)
    
    # Banking details
    bank_name = models.CharField(max_length=100, blank=True, null=True)
    account_type = models.CharField(max_length=50, choices=ACCOUNT_TYPE_CHOICES, blank=True, null=True)
    branch_code = models.CharField(max_length=50, blank=True, null=True)
    account_number = models.CharField(max_length=50, blank=True, null=True)
    
    # Relationships
    school = models.ForeignKey(School, on_delete=models.SET_NULL, related_name='youth', blank=True, null=True)
    mentor = models.ForeignKey('Mentor', on_delete=models.SET_NULL, related_name='mentored_youth', blank=True, null=True)
    
    # System fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        # Auto-generate full_name from first_names and last_name
        if self.first_names and self.last_name:
            self.full_name = f"{self.first_names} {self.last_name}"
            
        # Calculate age if DOB is provided
        if self.dob and not self.age:
            today = timezone.now().date()
            self.age = today.year - self.dob.year - ((today.month, today.day) < (self.dob.month, self.dob.day))
            
        super(Youth, self).save(*args, **kwargs)
    
    def __str__(self):
        if self.full_name:
            return f"{self.full_name} (#{self.employee_id})"
        return f"Youth #{self.employee_id}"
    
    class Meta:
        verbose_name = "Youth"
        verbose_name_plural = "Youth"
        ordering = ['last_name', 'first_names']


class Child(models.Model):
    """Model representing a child who receives teaching/coaching"""
    airtable_id = models.CharField(max_length=100, blank=True, null=True, unique=True, help_text="Airtable record ID")
    full_name = models.CharField(max_length=255)
    mcode = models.CharField(max_length=50, blank=True, null=True, help_text="Unique code for the child")
    grade = models.CharField(max_length=50, blank=True, null=True)
    on_programme = models.BooleanField(default=True)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='children')
    
    # System fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.full_name} ({self.grade or 'Unknown grade'})"
    
    class Meta:
        verbose_name = "Child"
        verbose_name_plural = "Children"
        ordering = ['full_name']


class CanonicalChild(models.Model):
    """
    Canonical child record synced from the master Airtable children table.

    This is the stable cross-year identity record for every child on the programme.
    One row per child. mcode and child_uid are stable across years and Airtable tables.

    The existing Child model (below) is legacy — it has a required school FK and is
    only used by the old Session model. This model is the clean canonical replacement.

    Upsert key: source_airtable_id.
    Business key: mcode (unique integer, e.g. 6191).
    Cross-table join key: child_uid (e.g. 'CH-6191') — referenced in 2026 session tables.
    """
    source_airtable_id = models.CharField(max_length=100, unique=True, db_index=True)
    child_uid = models.CharField(max_length=50, unique=True, db_index=True, help_text="CH-XXXXX format UID")
    mcode = models.IntegerField(unique=True, db_index=True, help_text="Stable integer child identifier")
    first_name = models.CharField(max_length=200, blank=True, null=True)
    surname = models.CharField(max_length=200, blank=True, null=True)
    full_name = models.CharField(max_length=400, blank=True, null=True)
    gender = models.CharField(max_length=10, blank=True, null=True)
    identity_confidence = models.CharField(max_length=100, blank=True, null=True, help_text="e.g. Multi-Year Record")
    years_active = models.JSONField(default=list, blank=True, help_text="List of years the child was active")
    programme = models.JSONField(default=list, blank=True, help_text="e.g. ['Literacy Child']")
    school_2025 = models.CharField(max_length=200, blank=True, null=True)
    grade_2025 = models.CharField(max_length=50, blank=True, null=True)
    created_in_airtable = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.full_name or self.child_uid} (mcode={self.mcode})"

    class Meta:
        db_table = 'canonical_children'
        ordering = ['mcode']


class Mentor(models.Model):
    """Mentor who supervises youth coaches. Has dashboard login via User FK."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, blank=True, null=True)
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)

    # System fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        verbose_name = "Mentor"
        verbose_name_plural = "Mentors"


class Staff(models.Model):
    """
    Staff HR record synced from the Airtable HR staff database.

    Covers all staff (mentors, admin, finance, etc.) — current and former.
    Canonical key: employee_number (unique integer).
    Upsert key: source_airtable_id.
    """
    source_airtable_id = models.CharField(max_length=100, blank=True, null=True, unique=True, db_index=True)
    employee_number = models.IntegerField(blank=True, null=True, unique=True, db_index=True)

    # Identity
    name = models.CharField(max_length=255)
    first_names = models.CharField(max_length=255, blank=True, null=True)
    last_name = models.CharField(max_length=255, blank=True, null=True)
    gender = models.CharField(max_length=20, blank=True, null=True)
    race = models.CharField(max_length=100, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    id_number = models.CharField(max_length=50, blank=True, null=True)
    identification_type = models.CharField(max_length=50, blank=True, null=True)
    drivers_license_code = models.CharField(max_length=50, blank=True, null=True)

    # Contact
    cell_number = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    emergency_cell_number = models.CharField(max_length=50, blank=True, null=True)

    # Address
    unit_number = models.CharField(max_length=50, blank=True, null=True)
    complex_name = models.CharField(max_length=100, blank=True, null=True)
    street_number = models.CharField(max_length=50, blank=True, null=True)
    street = models.CharField(max_length=255, blank=True, null=True)
    suburb = models.CharField(max_length=100, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    postal_code = models.CharField(max_length=20, blank=True, null=True)

    # System fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} (#{self.employee_number})"

    class Meta:
        db_table = 'staff'
        ordering = ['name']
        verbose_name = "Staff"
        verbose_name_plural = "Staff"


class MentorVisit(models.Model):
    """Model representing a mentor's visit to a school (existing model)"""
    mentor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='visits')
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='visits')
    visit_date = models.DateField(default=timezone.now)

    # Visit type
    VISIT_TYPE_CHOICES = [
        ('observation', 'Observation'),
        ('meeting', 'Meeting'),
        ('delivery', 'Delivery'),
        ('other', 'Other'),
    ]
    visit_type = models.CharField(
        max_length=20,
        choices=VISIT_TYPE_CHOICES,
        default='observation',
        verbose_name="Type of Visit"
    )

    # Checkbox observations (null for non-observation visits)
    letter_trackers_correct = models.BooleanField(null=True, blank=True, verbose_name="Are LC's using their Letter Trackers correctly?")
    reading_trackers_correct = models.BooleanField(null=True, blank=True, verbose_name="Are LC's using their Reading Trackers correctly?")
    sessions_correct = models.BooleanField(null=True, blank=True, verbose_name="Are TA's using their Session Trackers correctly?")
    admin_correct = models.BooleanField(null=True, blank=True, verbose_name="Are TA's completing their admin correctly?")

    # Quality rating
    RATING_CHOICES = [(i, str(i)) for i in range(1, 11)]
    quality_rating = models.IntegerField(choices=RATING_CHOICES, null=True, blank=True,
                                        verbose_name="Quality of Sessions Observed")

    # Text fields
    supplies_needed = models.TextField(blank=True, null=True, verbose_name="Any Supplies Needed")
    commentary = models.TextField(blank=True, null=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.mentor.username} visited {self.school.name} on {self.visit_date}"
    
    class Meta:
        ordering = ['-visit_date']
        verbose_name = "Mentor Visit"
        verbose_name_plural = "Mentor Visits"


class YeboVisit(models.Model):
    """Model representing a mentor's Yebo program visit to a school"""
    mentor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='yebo_visits')
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='yebo_visits')
    visit_date = models.DateField(default=timezone.now)

    # Visit type
    VISIT_TYPE_CHOICES = [
        ('observation', 'Observation'),
        ('meeting', 'Meeting'),
        ('delivery', 'Delivery'),
        ('other', 'Other'),
    ]
    visit_type = models.CharField(
        max_length=20,
        choices=VISIT_TYPE_CHOICES,
        default='observation',
        verbose_name="Type of Visit"
    )

    # Yebo-specific observations (null for non-observation visits)
    paired_reading_took_place = models.BooleanField(null=True, blank=True, verbose_name="Did paired reading take place?")
    paired_reading_tracking_updated = models.BooleanField(null=True, blank=True, verbose_name="Paired reading tracking up to date")
    
    # Afternoon session quality rating
    RATING_CHOICES = [(i, str(i)) for i in range(1, 11)]
    afternoon_session_quality = models.IntegerField(choices=RATING_CHOICES, null=True, blank=True,
                                                   verbose_name="Afternoon session quality")

    # Observation text fields
    after_school_observation = models.TextField(blank=True, null=True, verbose_name="After-School Observation")
    paired_reading_observation = models.TextField(blank=True, null=True, verbose_name="Paired Reading Observation")

    # Commentary
    commentary = models.TextField(blank=True, null=True, verbose_name="Commentary")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.mentor.username} visited {self.school.name} (Yebo) on {self.visit_date}"
    
    class Meta:
        ordering = ['-visit_date']
        verbose_name = "Yebo Visit"
        verbose_name_plural = "Yebo Visits"


class ThousandStoriesVisit(models.Model):
    """Model representing a mentor's 1000 Stories program visit to a school"""
    mentor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='thousand_stories_visits')
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='thousand_stories_visits')
    visit_date = models.DateField(default=timezone.now)

    # Visit type
    VISIT_TYPE_CHOICES = [
        ('observation', 'Observation'),
        ('meeting', 'Meeting'),
        ('delivery', 'Delivery'),
        ('other', 'Other'),
    ]
    visit_type = models.CharField(
        max_length=20,
        choices=VISIT_TYPE_CHOICES,
        default='observation',
        verbose_name="Type of Visit"
    )

    # 1000 Stories-specific observations (null for non-observation visits)
    library_neat_and_tidy = models.BooleanField(null=True, blank=True, verbose_name="Is the library neat and tidy?")
    tracking_sheets_up_to_date = models.BooleanField(null=True, blank=True, verbose_name="Are all tracking sheets up to date?")
    book_boxes_and_borrowing = models.BooleanField(null=True, blank=True, verbose_name="Is book boxes and book borrowing taking place?")
    daily_target_met = models.BooleanField(null=True, blank=True, verbose_name="Daily target of stories read is met?")
    
    # Quality rating for story time session
    RATING_CHOICES = [(i, str(i)) for i in range(1, 11)]
    story_time_quality = models.IntegerField(choices=RATING_CHOICES, null=True, blank=True,
                                           verbose_name="Quality of Story time session")
    
    # Other comments
    other_comments = models.TextField(blank=True, null=True, verbose_name="Other comments")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.mentor.username} visited {self.school.name} (1000 Stories) on {self.visit_date}"
    
    class Meta:
        ordering = ['-visit_date']
        verbose_name = "1000 Stories Visit"
        verbose_name_plural = "1000 Stories Visits"


class NumeracyVisit(models.Model):
    """Model representing a mentor's Numeracy program visit to a school"""
    mentor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='numeracy_visits')
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='numeracy_visits')
    visit_date = models.DateField(default=timezone.now)

    # Visit type
    VISIT_TYPE_CHOICES = [
        ('observation', 'Observation'),
        ('meeting', 'Meeting'),
        ('delivery', 'Delivery'),
        ('other', 'Other'),
    ]
    visit_type = models.CharField(
        max_length=20,
        choices=VISIT_TYPE_CHOICES,
        default='observation',
        verbose_name="Type of Visit"
    )

    # Numeracy-specific observations (null for non-observation visits)
    numeracy_tracker_correct = models.BooleanField(null=True, blank=True, verbose_name="Using Numeracy Tracker Correctly")
    teaching_counting = models.BooleanField(null=True, blank=True, verbose_name="Teaching Counting")
    teaching_number_concepts = models.BooleanField(null=True, blank=True, verbose_name="Teaching Number Concepts")
    teaching_patterns = models.BooleanField(null=True, blank=True, verbose_name="Teaching Patterns")
    teaching_addition_subtraction = models.BooleanField(null=True, blank=True, verbose_name="Teaching Addition/Subtraction")
    
    # Quality rating
    RATING_CHOICES = [(i, str(i)) for i in range(1, 11)]
    quality_rating = models.IntegerField(choices=RATING_CHOICES, null=True, blank=True,
                                        verbose_name="Quality of Sessions Observed")

    # Text fields
    supplies_needed = models.TextField(blank=True, null=True, verbose_name="Any Supplies Needed")
    commentary = models.TextField(blank=True, null=True, verbose_name="Commentary")
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.mentor.username} visited {self.school.name} (Numeracy) on {self.visit_date}"
    
    class Meta:
        ordering = ['-visit_date']
        verbose_name = "Numeracy Visit"
        verbose_name_plural = "Numeracy Visits"


class Session(models.Model):
    """Model representing a teaching session between a youth and a child"""
    # Identification
    airtable_id = models.CharField(max_length=100, unique=True, help_text="Airtable record ID")
    session_id = models.IntegerField(unique=True, verbose_name="Session ID")
    
    # Foreign key relationships
    youth = models.ForeignKey(Youth, on_delete=models.CASCADE, related_name='sessions')
    child = models.ForeignKey(Child, on_delete=models.CASCADE, related_name='sessions')
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='sessions')
    mentor = models.ForeignKey(Mentor, on_delete=models.SET_NULL, null=True, related_name='sessions')
    
    # Session details
    total_weekly_sessions = models.IntegerField(default=0, verbose_name="Total Weekly Sessions")
    submitted_for_week = models.IntegerField(default=0, verbose_name="Submitted for Week")
    week = models.CharField(max_length=50)
    month = models.CharField(max_length=50)
    month_year = models.CharField(max_length=50, verbose_name="Month and Year")
    sessions_met_minimum = models.CharField(max_length=10, verbose_name="Met Minimum")
    capture_date = models.DateField(verbose_name="Capture Date")
    
    # Timestamps
    created_in_airtable = models.DateTimeField(verbose_name="Created in Airtable")
    created_in_system = models.DateTimeField(auto_now_add=True, verbose_name="Created in System")
    updated_in_system = models.DateTimeField(auto_now=True, verbose_name="Last Updated")
    
    def __str__(self):
        return f"Session {self.session_id} - {self.child.full_name} with {self.youth.full_name}"
    
    class Meta:
        ordering = ['-capture_date']
        verbose_name = "Session"
        verbose_name_plural = "Sessions"


class AirtableSyncLog(models.Model):
    """Model to track Airtable synchronization history"""
    sync_type = models.CharField(max_length=50, verbose_name="Sync Type")  # 'youth', 'sessions', etc.
    started_at = models.DateTimeField(auto_now_add=True, verbose_name="Started At")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Completed At")
    records_processed = models.IntegerField(default=0, verbose_name="Records Processed")
    records_created = models.IntegerField(default=0, verbose_name="Records Created")
    records_updated = models.IntegerField(default=0, verbose_name="Records Updated")
    records_skipped = models.IntegerField(default=0, verbose_name="Records Skipped")
    error_message = models.TextField(blank=True, null=True, verbose_name="Error Message")
    success = models.BooleanField(default=False, verbose_name="Success")
    
    def mark_complete(self, success=True, error_message=None):
        """Mark the sync as complete"""
        self.completed_at = timezone.now()
        self.success = success
        if error_message:
            self.error_message = error_message
        self.save()
        
    def __str__(self):
        return f"{self.sync_type} sync on {self.started_at.strftime('%Y-%m-%d %H:%M')}"
    
    class Meta:
        verbose_name = "Airtable Sync Log"
        verbose_name_plural = "Airtable Sync Logs"
        ordering = ['-started_at']
        
        
# api/models.py (add to your existing models)

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

class WELA_assessments(models.Model):
    # Core identification
    mcode = models.CharField(max_length=20, db_index=True, help_text="Unique student identifier")
    assessment_year = models.IntegerField(help_text="Assessment year (2022, 2023, 2024)")
    
    # School and demographic info
    school = models.CharField(max_length=200)
    city = models.CharField(max_length=100)
    centre = models.CharField(max_length=100, blank=True, null=True)
    type = models.CharField(max_length=50, blank=True, null=True)  # Primary/Both
    class_name = models.CharField(max_length=20, blank=True, null=True)
    teacher = models.CharField(max_length=100, blank=True, null=True)
    grade = models.CharField(max_length=20)
    language = models.CharField(max_length=50)
    
    # Mentor info
    mentor = models.CharField(max_length=100, blank=True, null=True)
    
    # Student info
    surname = models.CharField(max_length=100)
    name = models.CharField(max_length=100)
    full_name = models.CharField(max_length=200)
    gender = models.CharField(max_length=1, choices=[('M', 'Male'), ('F', 'Female')])
    
    # Program participation
    total_sessions = models.IntegerField(blank=True, null=True)
    on_programme = models.CharField(max_length=10, blank=True, null=True)
    current_lc = models.CharField(max_length=100, blank=True, null=True)
    
    # January Assessment Scores
    jan_letter_sounds = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    jan_story_comprehension = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    jan_listen_first_sound = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    jan_listen_words = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    jan_writing_letters = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    jan_read_words = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    jan_read_sentences = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    jan_read_story = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    jan_write_cvcs = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    jan_write_sentences = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    jan_write_story = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    jan_total = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0)])
    
    # June Assessment Scores
    june_letter_sounds = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    june_story_comprehension = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    june_listen_first_sound = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    june_listen_words = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    june_writing_letters = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    june_read_words = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    june_read_sentences = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    june_read_story = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    june_write_cvcs = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    june_write_sentences = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    june_write_story = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    june_total = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0)])
    
    # November Assessment Scores  
    nov_letter_sounds = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    nov_story_comprehension = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    nov_listen_first_sound = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    nov_listen_words = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    nov_writing_letters = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    nov_read_words = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    nov_read_sentences = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    nov_read_story = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    nov_write_cvcs = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    nov_write_sentences = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    nov_write_story = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0), MaxValueValidator(100)])
    nov_total = models.IntegerField(blank=True, null=True, validators=[MinValueValidator(0)])
    
    # Data capture info
    captured_by = models.CharField(max_length=100, blank=True, null=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'wela_assessments'
        indexes = [
            models.Index(fields=['mcode', 'assessment_year']),
            models.Index(fields=['school', 'assessment_year']),
            models.Index(fields=['grade', 'assessment_year']),
            models.Index(fields=['mentor', 'assessment_year']),
        ]
        unique_together = ['mcode', 'assessment_year']  # Same student can have multiple years
    
    def __str__(self):
        return f"{self.full_name} ({self.mcode}) - {self.assessment_year}"
    
    @property
    def jan_improvement_from_baseline(self):
        """Calculate improvement from January to June"""
        if self.jan_total and self.june_total:
            return self.june_total - self.jan_total
        return None
    
    @property 
    def year_end_improvement(self):
        """Calculate improvement from January to November"""
        if self.jan_total and self.nov_total:
            return self.nov_total - self.jan_total
        return None
    
    @property
    def improvement_percentage(self):
        """Calculate percentage improvement from Jan to Nov"""
        if self.jan_total and self.nov_total and self.jan_total > 0:
            return round(((self.nov_total - self.jan_total) / self.jan_total) * 100, 2)
        return None
    
    
from django.db import models


class LiteracySession2026(models.Model):
    """
    Literacy session records from the 2026 Airtable sessions table.

    Structure changed significantly from 2025 — now uses UIDs for cross-table
    references (Youth UID, School UID, Child UID) instead of text names.
    These UIDs will eventually link to canonical Youth, School, and Child tables.

    Grain: one row per session. Each session involves exactly 2 children.
    Upsert key: source_airtable_id (unique Airtable record ID).
    """
    source_airtable_id = models.CharField(max_length=100, unique=True, db_index=True)
    session_record = models.IntegerField(null=True, blank=True, help_text="Airtable auto-number")
    session_uid = models.CharField(max_length=200, blank=True, null=True, db_index=True,
                                   help_text="Composite business key: SES-date-YTH-SCH-CH")
    session_date = models.DateField(null=True, blank=True)

    # UIDs — will eventually FK to canonical tables
    youth_uid = models.CharField(max_length=50, blank=True, null=True, db_index=True,
                                 help_text="e.g. YTH-1905")
    school_uid = models.CharField(max_length=50, blank=True, null=True, db_index=True,
                                  help_text="e.g. SCH-00283")
    child_uid_1 = models.CharField(max_length=50, blank=True, null=True, help_text="e.g. CH-16023")
    child_uid_2 = models.CharField(max_length=50, blank=True, null=True, help_text="e.g. CH-16566")
    child_names = models.CharField(max_length=500, blank=True, null=True,
                                   help_text="Semicolon-separated child names from Airtable")

    # Session content
    sounds_covered = models.CharField(max_length=500, blank=True, null=True,
                                      help_text="Raw sounds covered text entered by LC")
    sounds_covered_clean = models.CharField(max_length=500, blank=True, null=True,
                                            help_text="Normalised sounds (lowercased, punctuation removed)")
    blending_level = models.CharField(max_length=100, blank=True, null=True)

    # Quality / observability fields — useful for dashboard and data quality reporting
    duplicate_status = models.CharField(max_length=50, blank=True, null=True,
                                        help_text="e.g. Unique or Duplicate")
    overall_session_status = models.CharField(max_length=50, blank=True, null=True,
                                              help_text="Clean or Needs fix")
    capture_delay = models.IntegerField(null=True, blank=True,
                                        help_text="Days between session date and when it was captured")
    capture_delay_flag = models.CharField(max_length=100, blank=True, null=True)
    duplicate_fingerprint = models.CharField(max_length=500, blank=True, null=True,
                                             help_text="Composite string used for duplicate detection")

    # Timestamps
    created_in_airtable = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'literacy_sessions_2026'
        indexes = [
            models.Index(fields=['session_date']),
            models.Index(fields=['youth_uid']),
            models.Index(fields=['school_uid']),
        ]

    def __str__(self):
        return f"{self.session_uid or self.source_airtable_id} ({self.session_date})"


class NumeracySession2026(models.Model):
    """
    Numeracy session records from the 2026 Airtable sessions table.

    Key difference from literacy 2026: numeracy sessions have 3-10 children per
    session (a group), not exactly 2. Child UIDs are stored as a JSON array.
    Data is group-level (count level, number recognition) not per-child.

    Upsert key: source_airtable_id (unique Airtable record ID).
    """
    source_airtable_id = models.CharField(max_length=100, unique=True, db_index=True)
    session_record = models.IntegerField(null=True, blank=True, help_text="Airtable auto-number")
    session_uid = models.CharField(max_length=500, blank=True, null=True, db_index=True,
                                   help_text="Composite business key: SES-date-YTH-SCH-CH...")
    session_date = models.DateField(null=True, blank=True)

    # UIDs — will eventually FK to canonical tables
    youth_uid = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    school_uid = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    child_uids = models.JSONField(default=list, blank=True,
                                  help_text="Array of CH-XXXXX UIDs for all children in this session")
    children_count = models.IntegerField(null=True, blank=True)

    # Session content — group-level, not per-child
    group_count_level = models.CharField(max_length=50, blank=True, null=True,
                                         help_text="e.g. 31-40 (emoji stripped from Airtable value)")
    group_number_recognition = models.CharField(max_length=100, blank=True, null=True,
                                                help_text="e.g. Recognises 1-5")

    # Quality / observability fields
    duplicate_status = models.CharField(max_length=50, blank=True, null=True)
    overall_session_status = models.CharField(max_length=50, blank=True, null=True)
    capture_delay = models.IntegerField(null=True, blank=True,
                                        help_text="Days between session date and capture")
    capture_delay_flag = models.CharField(max_length=100, blank=True, null=True)
    duplicate_fingerprint = models.CharField(max_length=500, blank=True, null=True)

    # Timestamps (Created is a date not datetime in this Airtable table)
    created_in_airtable = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'numeracy_sessions_2026'
        indexes = [
            models.Index(fields=['session_date']),
            models.Index(fields=['youth_uid']),
            models.Index(fields=['school_uid']),
        ]

    def __str__(self):
        return f"{self.session_uid or self.source_airtable_id} ({self.session_date})"


from django.db import models

class LiteracySession(models.Model):
    session_id = models.IntegerField(unique=True)
    lc_full_name = models.CharField(max_length=255, blank=True)
    child_full_name = models.CharField(max_length=255, blank=True)
    school = models.CharField(max_length=255, blank=True)
    grade = models.CharField(max_length=50, blank=True)
    sessions_capture_date = models.DateField(null=True, blank=True)
    total_weekly_sessions_received = models.IntegerField(default=0)
    reading_level = models.CharField(max_length=100, blank=True)
    letters_done = models.JSONField(default=list, blank=True)
    mentor = models.CharField(max_length=255, blank=True)
    site_type = models.CharField(max_length=100, blank=True)
    on_the_programme = models.CharField(max_length=50, blank=True)
    month = models.CharField(max_length=50, blank=True)
    week = models.CharField(max_length=50, blank=True)
    month_and_year = models.CharField(max_length=50, blank=True)
    created = models.DateTimeField(null=True, blank=True)
    sessions_met_minimum = models.CharField(max_length=10, blank=True)
    duplicate_flag = models.CharField(max_length=255, blank=True)
    employee_id = models.CharField(max_length=50, blank=True)
    mcode = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"{self.child_full_name} ({self.school}) - {self.sessions_capture_date}"


class NumeracySessionChild(models.Model):
    source_airtable_id = models.CharField(max_length=100, blank=True, null=True, db_index=True, help_text="Airtable record ID — used as upsert key so we never delete the whole table")
    session_id = models.CharField(max_length=255, blank=True, null=True)
    nc_full_name = models.CharField(max_length=255, blank=True, null=True)
    numeracy_site = models.CharField(max_length=255, blank=True, null=True)
    child_name = models.CharField(max_length=255, blank=True, null=True)
    sessions_capture_date = models.DateField(blank=True, null=True)
    children_in_group = models.IntegerField(blank=True, null=True)
    created = models.CharField(max_length=50, blank=True, null=True)
    current_count_level = models.CharField(max_length=50, blank=True, null=True)
    baseline_count_level = models.JSONField(default=list, blank=True, null=True)
    number_recognition = models.CharField(max_length=50, blank=True, null=True)
    month = models.CharField(max_length=50, blank=True, null=True)
    week = models.CharField(max_length=50, blank=True, null=True)
    month_and_year = models.CharField(max_length=50, blank=True, null=True)
    all_sites = models.JSONField(default=list, blank=True, null=True)
    site_placement = models.CharField(max_length=255, blank=True, null=True)
    employee_id = models.CharField(max_length=255, blank=True, null=True)
    mentor = models.CharField(max_length=255, blank=True, null=True)
    employment_status = models.CharField(max_length=255, blank=True, null=True)
    duplicate_flag = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        verbose_name = "Numeracy Session (Child Level)"
        verbose_name_plural = "Numeracy Sessions (Child Level)"
        indexes = [
            models.Index(fields=["session_id"]),
            models.Index(fields=["nc_full_name"]),
            models.Index(fields=["numeracy_site"]),
            models.Index(fields=["child_name"]),
        ]

    def __str__(self):
        return f"{self.child_name or 'Unknown Child'} - {self.session_id or 'No ID'}"


# 2025 Assessment choices
GENDER_CHOICES_2025 = [
    ('Male', 'Male'),
    ('Female', 'Female'),
]

RACE_CHOICES_2025 = [
    ('Black', 'Black'),
    ('Coloured', 'Coloured'),
]

LANGUAGE_CHOICES_2025 = [
    ('IsiXhosa', 'IsiXhosa'),
    ('English', 'English'),
]

GRADE_CHOICES_2025 = [
    ('PreR', 'PreR'),
    ('Grade R', 'Grade R'),
    ('Grade 1', 'Grade 1'),
    ('Grade 2', 'Grade 2'),
    ('Grade 3', 'Grade 3'),
]

CENTRE_TYPE_CHOICES_2025 = [
    ('Primary', 'Primary'),
    ('ECD', 'ECD'),
    ('Both', 'Both'),
    ('Wcd', 'Wcd'),
]

ON_PROGRAMME_CHOICES_2025 = [
    ('Yes', 'Yes'),
    ('No', 'No'),
    ('Awaiting', 'Awaiting'),
    ('Left', 'Left'),
    ('Absent', 'Absent'),
]

BASELINE_STATUS_CHOICES = [
    ('Present Baseline', 'Present Baseline'),
    ('Missing Baseline', 'Missing Baseline'),
]

MIDLINE_STATUS_CHOICES = [
    ('Midline Present', 'Midline Present'),
    ('Midline Missing', 'Midline Missing'),
    ('N/A', 'N/A'),
]

ENDLINE_STATUS_CHOICES = [
    ('Present Endline', 'Present Endline'),
    ('Missing Endline', 'Missing Endline'),
]


class Assessment2025(models.Model):
    """
    Model for 2025 Children's Database assessments.
    Maps directly to the Airtable '2025 Children's Database - Main' table.
    """
    
    # Airtable sync identifier
    airtable_id = models.CharField(
        max_length=100, 
        unique=True, 
        help_text="Airtable record ID for syncing"
    )
    
    # Core identification
    mcode = models.CharField(
        max_length=100, 
        db_index=True, 
        blank=True, 
        null=True,
        help_text="Unique student identifier"
    )
    surname = models.CharField(max_length=255, blank=True, null=True)
    name = models.CharField(max_length=255, blank=True, null=True)
    full_name = models.CharField(max_length=255, blank=True, null=True)
    
    # Demographics
    gender = models.CharField(
        max_length=10, 
        choices=GENDER_CHOICES_2025, 
        blank=True, 
        null=True
    )
    race = models.CharField(
        max_length=20, 
        choices=RACE_CHOICES_2025, 
        blank=True, 
        null=True
    )
    language = models.CharField(
        max_length=20, 
        choices=LANGUAGE_CHOICES_2025, 
        blank=True, 
        null=True
    )
    
    # School/Class info
    school = models.CharField(max_length=200, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    grade = models.CharField(
        max_length=20, 
        choices=GRADE_CHOICES_2025, 
        blank=True, 
        null=True
    )
    class_name = models.CharField(
        max_length=20, 
        blank=True, 
        null=True,
        help_text="Class identifier (e.g., RA, RB, 1A)"
    )
    teacher = models.CharField(max_length=100, blank=True, null=True)
    centre_type = models.CharField(
        max_length=20, 
        choices=CENTRE_TYPE_CHOICES_2025, 
        blank=True, 
        null=True
    )
    mentor = models.CharField(max_length=100, blank=True, null=True)
    
    # Program participation
    on_programme = models.CharField(
        max_length=20, 
        choices=ON_PROGRAMME_CHOICES_2025, 
        blank=True, 
        null=True
    )
    capturer = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        help_text="Person who captured the data"
    )
    
    # Status fields
    baseline_status = models.CharField(
        max_length=20, 
        choices=BASELINE_STATUS_CHOICES, 
        blank=True, 
        null=True
    )
    midline_status = models.CharField(
        max_length=20, 
        choices=MIDLINE_STATUS_CHOICES, 
        blank=True, 
        null=True
    )
    endline_status = models.CharField(
        max_length=20, 
        choices=ENDLINE_STATUS_CHOICES, 
        blank=True, 
        null=True
    )
    
    # Exclusion fields
    exclude = models.BooleanField(
        blank=True, 
        null=True,
        help_text="Mark True to exclude this record from analysis"
    )
    exclude_reason = models.TextField(
        blank=True, 
        null=True,
        help_text="Reason for excluding this record"
    )
    
    # ========================================
    # January Assessment Scores (Baseline)
    # ========================================
    jan_letter_sounds = models.IntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(0)]
    )
    jan_story_comprehension = models.IntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(0)]
    )
    jan_listen_first_sound = models.IntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(0)]
    )
    jan_listen_words = models.IntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(0)]
    )
    jan_writing_letters = models.IntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(0)]
    )
    jan_read_words = models.IntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(0)]
    )
    jan_read_sentences = models.IntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(0)]
    )
    jan_read_story = models.IntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(0)]
    )
    jan_write_cvcs = models.IntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(0)]
    )
    jan_write_sentences = models.IntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(0)]
    )
    jan_write_story = models.IntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(0)]
    )
    jan_total = models.IntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(0)],
        help_text="Computed total of all January scores"
    )
    
    # ========================================
    # June Assessment Scores (Midline)
    # ========================================
    june_letter_sounds = models.IntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(0)]
    )
    june_story_comprehension = models.IntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(0)]
    )
    june_listen_first_sound = models.IntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(0)]
    )
    june_listen_words = models.IntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(0)]
    )
    june_writing_letters = models.IntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(0)]
    )
    june_read_words = models.IntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(0)]
    )
    june_read_sentences = models.IntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(0)]
    )
    june_read_story = models.IntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(0)]
    )
    june_write_cvcs = models.IntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(0)]
    )
    june_write_sentences = models.IntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(0)]
    )
    june_write_story = models.IntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(0)]
    )
    june_total = models.IntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(0)],
        help_text="Computed total of all June scores"
    )
    
    # ========================================
    # November Assessment Scores (Endline)
    # ========================================
    nov_letter_sounds = models.IntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(0)]
    )
    nov_story_comprehension = models.IntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(0)]
    )
    nov_listen_first_sound = models.IntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(0)]
    )
    nov_listen_words = models.IntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(0)]
    )
    nov_writing_letters = models.IntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(0)]
    )
    nov_read_words = models.IntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(0)]
    )
    nov_read_sentences = models.IntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(0)]
    )
    nov_read_story = models.IntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(0)]
    )
    nov_write_cvcs = models.IntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(0)]
    )
    nov_write_sentences = models.IntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(0)]
    )
    nov_write_story = models.IntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(0)]
    )
    nov_total = models.IntegerField(
        blank=True, null=True,
        validators=[MinValueValidator(0)],
        help_text="Computed total of all November scores"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'assessment_2025'
        verbose_name = "2025 Assessment"
        verbose_name_plural = "2025 Assessments"
        indexes = [
            models.Index(fields=['mcode']),
            models.Index(fields=['school']),
            models.Index(fields=['grade']),
            models.Index(fields=['mentor']),
            models.Index(fields=['on_programme']),
        ]
    
    def __str__(self):
        return f"{self.full_name or 'Unknown'} ({self.mcode or 'No Mcode'}) - {self.school or 'No School'}"
    
    def save(self, *args, **kwargs):
        # Auto-generate full_name if not provided
        if not self.full_name and (self.surname or self.name):
            parts = [self.surname or '', self.name or '']
            self.full_name = ' '.join(filter(None, parts))
        super().save(*args, **kwargs)
    
    # ========================================
    # Computed Properties
    # ========================================
    
    @property
    def computed_jan_total(self):
        """Calculate January total from individual scores"""
        scores = [
            self.jan_letter_sounds, self.jan_story_comprehension,
            self.jan_listen_first_sound, self.jan_listen_words,
            self.jan_writing_letters, self.jan_read_words,
            self.jan_read_sentences, self.jan_read_story,
            self.jan_write_cvcs, self.jan_write_sentences,
            self.jan_write_story
        ]
        valid_scores = [s for s in scores if s is not None]
        return sum(valid_scores) if valid_scores else None
    
    @property
    def computed_june_total(self):
        """Calculate June total from individual scores"""
        scores = [
            self.june_letter_sounds, self.june_story_comprehension,
            self.june_listen_first_sound, self.june_listen_words,
            self.june_writing_letters, self.june_read_words,
            self.june_read_sentences, self.june_read_story,
            self.june_write_cvcs, self.june_write_sentences,
            self.june_write_story
        ]
        valid_scores = [s for s in scores if s is not None]
        return sum(valid_scores) if valid_scores else None
    
    @property
    def computed_nov_total(self):
        """Calculate November total from individual scores"""
        scores = [
            self.nov_letter_sounds, self.nov_story_comprehension,
            self.nov_listen_first_sound, self.nov_listen_words,
            self.nov_writing_letters, self.nov_read_words,
            self.nov_read_sentences, self.nov_read_story,
            self.nov_write_cvcs, self.nov_write_sentences,
            self.nov_write_story
        ]
        valid_scores = [s for s in scores if s is not None]
        return sum(valid_scores) if valid_scores else None
    
    @property
    def baseline_to_midline_improvement(self):
        """Calculate improvement from January to June"""
        jan = self.jan_total or self.computed_jan_total
        june = self.june_total or self.computed_june_total
        if jan is not None and june is not None:
            return june - jan
        return None
    
    @property
    def baseline_to_endline_improvement(self):
        """Calculate improvement from January to November"""
        jan = self.jan_total or self.computed_jan_total
        nov = self.nov_total or self.computed_nov_total
        if jan is not None and nov is not None:
            return nov - jan
        return None
    
    @property
    def improvement_percentage(self):
        """Calculate percentage improvement from January to November"""
        jan = self.jan_total or self.computed_jan_total
        nov = self.nov_total or self.computed_nov_total
        if jan and nov and jan > 0:
            return round(((nov - jan) / jan) * 100, 2)
        return None
