from rest_framework import serializers
from .models import MentorVisit, School
from django.contrib.auth.models import User


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model (for mentor field)"""
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email']


class SchoolSerializer(serializers.ModelSerializer):
    """Serializer for School model"""
    class Meta:
        model = School
        fields = ['id', 'name', 'type', 'city', 'address', 'contact_phone', 'contact_email']


class MentorVisitSerializer(serializers.ModelSerializer):
    """Serializer for MentorVisit model"""
    mentor = UserSerializer(read_only=True)
    school = SchoolSerializer(read_only=True)
    
    class Meta:
        model = MentorVisit
        fields = [
            'id',
            'mentor',
            'school',
            'visit_date',
            'letter_trackers_correct',
            'reading_trackers_correct',
            'sessions_correct',
            'admin_correct',
            'quality_rating',
            'supplies_needed',
            'commentary',
            'created_at',
            'updated_at'
        ] 