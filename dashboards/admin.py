from django.contrib import admin
from .models import School, MentorVisit

@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'is_active')
    list_filter = ('is_active', 'type')
    search_fields = ('name', 'address')
    ordering = ('name',)

@admin.register(MentorVisit)
class MentorVisitAdmin(admin.ModelAdmin):
    list_display = ('mentor', 'school', 'visit_date', 'quality_rating')
    list_filter = ('letter_trackers_correct', 'reading_trackers_correct', 'sessions_correct', 'admin_correct', 'visit_date')
    search_fields = ('school__name', 'mentor__username', 'commentary')
    date_hierarchy = 'visit_date'