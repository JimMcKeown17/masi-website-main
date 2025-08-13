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
    name = models.CharField(max_length=200)
    type = models.CharField(max_length=200, choices=SCHOOL_TYPE_CHOICES, blank=True, null=True)
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


class Mentor(models.Model):
    """Model representing a mentor who manages youth"""
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
        verbose_name = "Mentor Visit"
        verbose_name_plural = "Mentor Visits"


class MentorVisit(models.Model):
    """Model representing a mentor's visit to a school (existing model)"""
    mentor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='visits')
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='visits')
    visit_date = models.DateField(default=timezone.now)
    
    # Checkbox observations
    letter_trackers_correct = models.BooleanField(default=False, verbose_name="Are LC's using their Letter Trackers correctly?")
    reading_trackers_correct = models.BooleanField(default=False, verbose_name="Are LC's using their Reading Trackers correctly?")
    sessions_correct = models.BooleanField(default=False, verbose_name="Are TA's using their Session Trackers correctly?")
    admin_correct = models.BooleanField(default=False, verbose_name="Are TA's completing their admin correctly?")
    
    # Quality rating
    RATING_CHOICES = [(i, str(i)) for i in range(1, 11)]
    quality_rating = models.IntegerField(choices=RATING_CHOICES, default=5, 
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
    
    # Yebo-specific observations
    paired_reading_took_place = models.BooleanField(default=False, verbose_name="Did paired reading take place?")
    paired_reading_tracking_updated = models.BooleanField(default=False, verbose_name="Paired reading tracking up to date")
    
    # Afternoon session quality rating
    RATING_CHOICES = [(i, str(i)) for i in range(1, 11)]
    afternoon_session_quality = models.IntegerField(choices=RATING_CHOICES, default=5, 
                                                   verbose_name="Afternoon session quality")
    
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
    
    # 1000 Stories-specific observations
    library_neat_and_tidy = models.BooleanField(default=False, verbose_name="Is the library neat and tidy?")
    tracking_sheets_up_to_date = models.BooleanField(default=False, verbose_name="Are all tracking sheets up to date?")
    book_boxes_and_borrowing = models.BooleanField(default=False, verbose_name="Is book boxes and book borrowing taking place?")
    daily_target_met = models.BooleanField(default=False, verbose_name="Daily target of stories read is met?")
    
    # Quality rating for story time session
    RATING_CHOICES = [(i, str(i)) for i in range(1, 11)]
    story_time_quality = models.IntegerField(choices=RATING_CHOICES, default=5, 
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
    
    # Numeracy-specific observations
    numeracy_tracker_correct = models.BooleanField(default=False, verbose_name="Using Numeracy Tracker Correctly")
    teaching_counting = models.BooleanField(default=False, verbose_name="Teaching Counting")
    teaching_number_concepts = models.BooleanField(default=False, verbose_name="Teaching Number Concepts")
    teaching_patterns = models.BooleanField(default=False, verbose_name="Teaching Patterns")
    teaching_addition_subtraction = models.BooleanField(default=False, verbose_name="Teaching Addition/Subtraction")
    
    # Quality rating
    RATING_CHOICES = [(i, str(i)) for i in range(1, 11)]
    quality_rating = models.IntegerField(choices=RATING_CHOICES, default=5, 
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