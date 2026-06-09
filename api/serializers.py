from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError
from .models import (
    MentorVisit, YeboVisit, ThousandStoriesVisit, NumeracyVisit, School,
    SchoolClosure, StaffAbsence, Youth,
)
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
    # Explicitly allow null for optional fields
    letter_trackers_correct = serializers.BooleanField(required=False, allow_null=True)
    reading_trackers_correct = serializers.BooleanField(required=False, allow_null=True)
    sessions_correct = serializers.BooleanField(required=False, allow_null=True)
    admin_correct = serializers.BooleanField(required=False, allow_null=True)
    quality_rating = serializers.IntegerField(required=False, allow_null=True)
    supplies_needed = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    commentary = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = MentorVisit
        fields = [
            'id',
            'mentor',
            'school',
            'school_id',  # For writing
            'visit_date',
            'visit_type',
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
        extra_kwargs = {
            'visit_type': {'required': False},
        }


class YeboVisitSerializer(serializers.ModelSerializer):
    """Serializer for YeboVisit model"""
    mentor = UserSerializer(read_only=True)
    school = SchoolSerializer(read_only=True)
    school_id = serializers.PrimaryKeyRelatedField(
        queryset=School.objects.all(),
        source='school',
        write_only=True
    )
    # Explicitly allow null for optional fields
    paired_reading_took_place = serializers.BooleanField(required=False, allow_null=True)
    paired_reading_tracking_updated = serializers.BooleanField(required=False, allow_null=True)
    afternoon_session_quality = serializers.IntegerField(required=False, allow_null=True)
    after_school_observation = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    paired_reading_observation = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    commentary = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = YeboVisit
        fields = [
            'id',
            'mentor',
            'school',
            'school_id',  # For writing
            'visit_date',
            'visit_type',
            'paired_reading_took_place',
            'paired_reading_tracking_updated',
            'afternoon_session_quality',
            'after_school_observation',
            'paired_reading_observation',
            'commentary',
            'created_at',
            'updated_at'
        ]
        extra_kwargs = {
            'visit_type': {'required': False},
            'afternoon_session_quality': {'required': False, 'allow_null': True},
            'after_school_observation': {'required': False, 'allow_blank': True},
            'paired_reading_observation': {'required': False, 'allow_blank': True},
            'commentary': {'required': False, 'allow_blank': True},
        }


class ThousandStoriesVisitSerializer(serializers.ModelSerializer):
    """Serializer for ThousandStoriesVisit model"""
    mentor = UserSerializer(read_only=True)
    school = SchoolSerializer(read_only=True)
    school_id = serializers.PrimaryKeyRelatedField(
        queryset=School.objects.all(),
        source='school',
        write_only=True
    )
    # Explicitly allow null for optional fields
    library_neat_and_tidy = serializers.BooleanField(required=False, allow_null=True)
    tracking_sheets_up_to_date = serializers.BooleanField(required=False, allow_null=True)
    book_boxes_and_borrowing = serializers.BooleanField(required=False, allow_null=True)
    daily_target_met = serializers.BooleanField(required=False, allow_null=True)
    story_time_quality = serializers.IntegerField(required=False, allow_null=True)
    other_comments = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = ThousandStoriesVisit
        fields = [
            'id',
            'mentor',
            'school',
            'school_id',  # For writing
            'visit_date',
            'visit_type',
            'library_neat_and_tidy',
            'tracking_sheets_up_to_date',
            'book_boxes_and_borrowing',
            'daily_target_met',
            'story_time_quality',
            'other_comments',
            'created_at',
            'updated_at'
        ]
        extra_kwargs = {
            'visit_type': {'required': False},
            'story_time_quality': {'required': False, 'allow_null': True},
            'other_comments': {'required': False, 'allow_blank': True},
        }


class NumeracyVisitSerializer(serializers.ModelSerializer):
    """Serializer for NumeracyVisit model"""
    mentor = UserSerializer(read_only=True)
    school = SchoolSerializer(read_only=True)
    school_id = serializers.PrimaryKeyRelatedField(
        queryset=School.objects.all(),
        source='school',
        write_only=True
    )
    # Explicitly allow null for optional fields
    numeracy_tracker_correct = serializers.BooleanField(required=False, allow_null=True)
    teaching_counting = serializers.BooleanField(required=False, allow_null=True)
    teaching_number_concepts = serializers.BooleanField(required=False, allow_null=True)
    teaching_patterns = serializers.BooleanField(required=False, allow_null=True)
    teaching_addition_subtraction = serializers.BooleanField(required=False, allow_null=True)
    quality_rating = serializers.IntegerField(required=False, allow_null=True)
    supplies_needed = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    commentary = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = NumeracyVisit
        fields = [
            'id',
            'mentor',
            'school',
            'school_id',  # For writing
            'visit_date',
            'visit_type',
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
        extra_kwargs = {
            'visit_type': {'required': False},
            'quality_rating': {'required': False, 'allow_null': True},
            'supplies_needed': {'required': False, 'allow_blank': True},
            'commentary': {'required': False, 'allow_blank': True},
        }


class SchoolClosureSerializer(serializers.ModelSerializer):
    """Closure CRUD. scope_key/source/created_by are derived or server-set; the
    model's clean() validates that the scope fields match the scope_type."""
    scope_display = serializers.SerializerMethodField()

    class Meta:
        model = SchoolClosure
        fields = [
            'id', 'date', 'scope_type', 'scope_school', 'scope_school_type',
            'scope_region', 'scope_key', 'scope_display', 'is_open', 'source',
            'reason', 'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['scope_key', 'source', 'created_by', 'created_at', 'updated_at']

    def get_scope_display(self, obj):
        if obj.scope_type == 'global':
            return 'All schools'
        if obj.scope_type == 'type':
            return f'All {obj.get_scope_school_type_display()} schools' if obj.scope_school_type else 'All (by type)'
        if obj.scope_type == 'region':
            return obj.scope_region or 'Region'
        if obj.scope_type == 'school':
            return obj.scope_school.name if obj.scope_school_id else 'School'
        return obj.scope_key

    def validate(self, attrs):
        # Validate scope consistency through the model's clean(), merging with the
        # existing instance on PATCH so partial updates still validate.
        get = (lambda f: attrs.get(f, getattr(self.instance, f, None))) if self.instance else attrs.get
        probe = SchoolClosure(
            date=get('date'),
            scope_type=get('scope_type'),
            scope_school=get('scope_school'),
            scope_school_type=get('scope_school_type'),
            scope_region=get('scope_region'),
            is_open=get('is_open') or False,
        )
        try:
            probe.clean()
        except DjangoValidationError as e:
            raise serializers.ValidationError(getattr(e, 'message_dict', e.messages))
        return attrs


class StaffAbsenceSerializer(serializers.ModelSerializer):
    """Per-youth absence. youth_uid is derived from the selected youth."""
    youth_name = serializers.SerializerMethodField()

    class Meta:
        model = StaffAbsence
        fields = [
            'id', 'date', 'youth', 'youth_uid', 'youth_name', 'reason', 'note',
            'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['youth_uid', 'created_by', 'created_at', 'updated_at']

    def get_youth_name(self, obj):
        return obj.youth.full_name if obj.youth_id else obj.youth_uid

    def validate_youth(self, youth):
        if not youth.youth_uid:
            raise serializers.ValidationError('That youth has no youth_uid and cannot have absences recorded.')
        return youth