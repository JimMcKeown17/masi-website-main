from rest_framework import serializers
from .models import MentorVisit, YeboVisit, ThousandStoriesVisit, NumeracyVisit, School
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
    """Serializer for MentorVisit model (MASI Literacy)"""
    mentor = UserSerializer(read_only=True)
    school = SchoolSerializer(read_only=True)
    school_id = serializers.PrimaryKeyRelatedField(
        queryset=School.objects.all(),
        source='school',
        write_only=True
    )
    
    class Meta:
        model = MentorVisit
        fields = [
            'id',
            'mentor',
            'school',
            'school_id',  # For writing
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


class YeboVisitSerializer(serializers.ModelSerializer):
    """Serializer for YeboVisit model"""
    mentor = UserSerializer(read_only=True)
    school = SchoolSerializer(read_only=True)
    school_id = serializers.PrimaryKeyRelatedField(
        queryset=School.objects.all(),
        source='school',
        write_only=True
    )
    
    class Meta:
        model = YeboVisit
        fields = [
            'id',
            'mentor',
            'school',
            'school_id',  # For writing
            'visit_date',
            'paired_reading_took_place',
            'paired_reading_tracking_updated',
            'afternoon_session_quality',
            'commentary',
            'created_at',
            'updated_at'
        ]


class ThousandStoriesVisitSerializer(serializers.ModelSerializer):
    """Serializer for ThousandStoriesVisit model"""
    mentor = UserSerializer(read_only=True)
    school = SchoolSerializer(read_only=True)
    school_id = serializers.PrimaryKeyRelatedField(
        queryset=School.objects.all(),
        source='school',
        write_only=True
    )
    
    class Meta:
        model = ThousandStoriesVisit
        fields = [
            'id',
            'mentor',
            'school',
            'school_id',  # For writing
            'visit_date',
            'library_neat_and_tidy',
            'tracking_sheets_up_to_date',
            'book_boxes_and_borrowing',
            'daily_target_met',
            'story_time_quality',
            'other_comments',
            'created_at',
            'updated_at'
        ]


class NumeracyVisitSerializer(serializers.ModelSerializer):
    """Serializer for NumeracyVisit model"""
    mentor = UserSerializer(read_only=True)
    school = SchoolSerializer(read_only=True)
    school_id = serializers.PrimaryKeyRelatedField(
        queryset=School.objects.all(),
        source='school',
        write_only=True
    )
    
    class Meta:
        model = NumeracyVisit
        fields = [
            'id',
            'mentor',
            'school',
            'school_id',  # For writing
            'visit_date',
            'numeracy_tracker_correct',
            'teaching_counting',
            'teaching_number_concepts',
            'teaching_patterns',
            'teaching_addition_subtraction',
            'quality_rating',
            'supplies_needed',
            'commentary',
            'created_at',
            'updated_at'
        ]
        
class MentorSerializer(serializers.ModelSerializer):
    """Serializer for User model (for mentor field)"""
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email']
        
class SchoolSerializer(serializers.ModelSerializer):
    """Serializer for School model"""
    class Meta:
        model = School
        fields = ['id', 'name', 'type', 'city', 'address', 'contact_phone', 'contact_email']