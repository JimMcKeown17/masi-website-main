from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


ROLE_CHOICES = [
    ('ADMIN', 'Administrator'),
    ('STAFF', 'Staff Member'),
    ('PROJECT MANAGER', 'Project Manager'),
    ('MENTOR', 'Mentor'),
    ('VIEWER', 'Viewer'),
    ('FUNDER', 'Funder'),
    ('YOUTH', 'Youth'),
]
# Create your models here.

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    job_title = models.CharField(max_length=100, blank=True, null=True)
    project = models.CharField(max_length=100, blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='VIEWER')  # NEW

    def __str__(self):
        return f"{self.user.username}'s profile"

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    profile = getattr(instance, 'profile', None)
    if profile:
        profile.save()
