# dashboards/models.py
from api.models import School, MentorVisit, Youth, Child, Mentor, Session, AirtableSyncLog

# Re-export models to maintain backward compatibility
__all__ = ['School', 'MentorVisit', 'Youth', 'Child', 'Mentor', 'Session', 'AirtableSyncLog']

# from django.db import models
# from django.contrib.auth.models import User
# from django.utils import timezone

# SCHOOL_TYPE_CHOICES = [
#     ('ECDC', 'Early Childhood Development'),
#     ('Primary School', 'Primary School'),
#     ('Secondary School', 'Secondary School'),
#     ('Other', 'Other')
# ]

# class School(models.Model):
#     name = models.CharField(max_length=200)
#     type = models.CharField(max_length=200, choices=SCHOOL_TYPE_CHOICES, blank=True, null=True)
#     latitude = models.DecimalField(max_digits=10, decimal_places=8, blank=True, null=True)
#     longitude = models.DecimalField(max_digits=10, decimal_places=8, blank=True, null=True)
#     address = models.CharField(max_length=255, blank=True, null=True)
#     contact_phone = models.CharField(max_length=20, blank=True, null=True)
#     contact_email = models.EmailField(blank=True, null=True)
#     contact_person = models.CharField(max_length=200, blank=True, null=True)
#     is_active = models.BooleanField(default=True)
#     date_added = models.DateTimeField(auto_now_add=True)
    
#     def __str__(self):
#         return self.name
    
#     class Meta:
#         ordering = ['name']

# class MentorVisit(models.Model):
#     mentor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='visits')
#     school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='visits')
#     visit_date = models.DateField(default=timezone.now)
    
#     # Checkbox observations
#     letter_trackers_correct = models.BooleanField(default=False, verbose_name="Are LC's using their Letter Trackers correctly?")
#     reading_trackers_correct = models.BooleanField(default=False, verbose_name="Are LC's using their Reading Trackers correctly?")
#     sessions_correct = models.BooleanField(default=False, verbose_name="Are TA's using their Session Trackers correctly?")
#     admin_correct = models.BooleanField(default=False, verbose_name="Are TA's completing their admin correctly?")
    
#     # Quality rating
#     RATING_CHOICES = [(i, str(i)) for i in range(1, 11)]
#     quality_rating = models.IntegerField(choices=RATING_CHOICES, default=5, 
#                                         verbose_name="Quality of Sessions Observed")
    
#     # Text fields
#     supplies_needed = models.TextField(blank=True, null=True, verbose_name="Any Supplies Needed")
#     commentary = models.TextField(blank=True, null=True)
    
#     # Metadata
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)
    
#     def __str__(self):
#         return f"{self.mentor.username} visited {self.school.name} on {self.visit_date}"
    
#     class Meta:
#         ordering = ['-visit_date']
