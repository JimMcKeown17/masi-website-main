from django.contrib import admin
from .models import UserProfile

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('get_full_name', 'job_title', 'project')
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name', 'job_title', 'project')
    list_filter = ('project',)
    raw_id_fields = ('user',)

    def get_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip() or obj.user.username
    get_full_name.short_description = 'Name'
