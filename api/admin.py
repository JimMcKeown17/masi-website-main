from django.contrib import admin
from django.utils.html import format_html
from .models import School, Youth, Child, Mentor, MentorVisit, Session, AirtableSyncLog

@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'site_type', 'is_active', 'date_added')
    list_filter = ('type', 'site_type', 'is_active')
    search_fields = ('name', 'address', 'contact_person')
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'type', 'site_type', 'is_active')
        }),
        ('Contact Information', {
            'fields': ('contact_person', 'contact_phone', 'contact_email')
        }),
        ('Location', {
            'fields': ('address', 'latitude', 'longitude')
        }),
        ('Airtable Information', {
            'fields': ('airtable_id',),
            'classes': ('collapse',)
        }),
    )

@admin.register(Youth)
class YouthAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'employee_id', 'job_title', 'school', 'mentor', 'employment_status')
    list_filter = ('employment_status', 'job_title', 'school', 'mentor', 'gender', 'race')
    search_fields = ('first_names', 'last_name', 'employee_id', 'email', 'cell_phone_number')
    fieldsets = (
        ('Basic Information', {
            'fields': ('employee_id', 'first_names', 'last_name', 'full_name', 'dob', 'age', 'gender', 'race')
        }),
        ('ID Information', {
            'fields': ('id_type', 'rsa_id_number', 'foreign_id_number')
        }),
        ('Contact Information', {
            'fields': ('cell_phone_number', 'email', 'emergency_number')
        }),
        ('Address', {
            'fields': ('street_number', 'street_address', 'suburb_township', 'city_or_town', 'postal_code')
        }),
        ('Employment Details', {
            'fields': ('job_title', 'employment_status', 'start_date', 'end_date', 'reason_for_leaving', 'income_tax_number')
        }),
        ('Banking Details', {
            'fields': ('bank_name', 'account_type', 'branch_code', 'account_number')
        }),
        ('Relationships', {
            'fields': ('school', 'mentor')
        }),
        ('Airtable Information', {
            'fields': ('airtable_id',),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ('full_name', 'age')

@admin.register(Child)
class ChildAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'grade', 'mcode', 'school', 'on_programme')
    list_filter = ('grade', 'on_programme', 'school')
    search_fields = ('full_name', 'mcode')
    fieldsets = (
        ('Basic Information', {
            'fields': ('full_name', 'grade', 'mcode', 'on_programme')
        }),
        ('School', {
            'fields': ('school',)
        }),
        ('Airtable Information', {
            'fields': ('airtable_id',),
            'classes': ('collapse',)
        }),
    )

@admin.register(Mentor)
class MentorAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'user__username')
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'user', 'is_active')
        }),
    )

@admin.register(MentorVisit)
class MentorVisitAdmin(admin.ModelAdmin):
    list_display = ('mentor_name', 'school_name', 'visit_date', 'quality_rating')
    list_filter = ('visit_date', 'quality_rating', 'school')
    search_fields = ('mentor__username', 'school__name', 'commentary')
    fieldsets = (
        ('Visit Details', {
            'fields': ('mentor', 'school', 'visit_date')
        }),
        ('Observations', {
            'fields': ('letter_trackers_correct', 'reading_trackers_correct', 'sessions_correct', 'admin_correct')
        }),
        ('Quality', {
            'fields': ('quality_rating', 'supplies_needed', 'commentary')
        }),
    )
    
    def mentor_name(self, obj):
        return obj.mentor.username
    mentor_name.short_description = 'Mentor'
    
    def school_name(self, obj):
        return obj.school.name
    school_name.short_description = 'School'

@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('session_id', 'youth_name', 'child_name', 'school_name', 
                   'total_weekly_sessions', 'capture_date', 'week', 'month')
    list_filter = ('sessions_met_minimum', 'month', 'week', 'school', 'mentor')
    search_fields = ('session_id', 'youth__full_name', 'child__full_name', 'school__name')
    ordering = ('-capture_date', 'session_id')
    date_hierarchy = 'capture_date'
    
    fieldsets = (
        ('Session Details', {
            'fields': ('session_id', 'youth', 'child', 'school', 'mentor')
        }),
        ('Weekly Data', {
            'fields': ('total_weekly_sessions', 'submitted_for_week', 'sessions_met_minimum')
        }),
        ('Time Information', {
            'fields': ('capture_date', 'week', 'month', 'month_year')
        }),
        ('System Information', {
            'fields': ('created_in_airtable',),
            'classes': ('collapse',)
        }),
        ('Airtable Information', {
            'fields': ('airtable_id',),
            'classes': ('collapse',)
        }),
    )
    
    def youth_name(self, obj):
        return obj.youth.full_name
    youth_name.short_description = 'Youth'
    
    def child_name(self, obj):
        return obj.child.full_name
    child_name.short_description = 'Child'
    
    def school_name(self, obj):
        return obj.school.name
    school_name.short_description = 'School'

@admin.register(AirtableSyncLog)
class AirtableSyncLogAdmin(admin.ModelAdmin):
    list_display = ('sync_type', 'started_at', 'completed_at', 'status_label', 
                   'records_processed', 'records_created', 'records_updated')
    list_filter = ('sync_type', 'success', 'started_at')
    search_fields = ('sync_type', 'error_message')
    readonly_fields = ('started_at', 'completed_at', 'records_processed', 
                      'records_created', 'records_updated', 'records_skipped', 
                      'error_message', 'success')
    ordering = ('-started_at',)
    
    def status_label(self, obj):
        if obj.success:
            return format_html('<span style="color: green;">Success</span>')
        else:
            return format_html('<span style="color: red;">Failed</span>')
    status_label.short_description = 'Status'