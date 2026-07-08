from django.contrib import admin

from .models import (
    Campaign,
    Contact,
    ContactMergeLog,
    ContentStory,
    Deliverable,
    Donation,
    Draft,
    Expectation,
    Grant,
    Interaction,
    Opportunity,
)


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('name', 'kind', 'tier', 'segment', 'primary_email', 'newsletter_consent')
    list_filter = ('kind', 'tier', 'segment', 'newsletter_consent')
    search_fields = ('name', 'primary_email')


@admin.register(Donation)
class DonationAdmin(admin.ModelAdmin):
    list_display = ('contact', 'amount', 'currency', 'receiving_entity', 'date')
    list_filter = ('receiving_entity', 'currency')
    date_hierarchy = 'date'
    search_fields = ('contact__name',)


@admin.register(Opportunity)
class OpportunityAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact', 'stage', 'amount_requested', 'deadline')
    list_filter = ('stage',)
    search_fields = ('name', 'contact__name')


@admin.register(Grant)
class GrantAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact', 'amount', 'currency', 'period_start', 'period_end')
    search_fields = ('name', 'contact__name')


@admin.register(Deliverable)
class DeliverableAdmin(admin.ModelAdmin):
    list_display = ('title', 'kind', 'status', 'due_date')
    list_filter = ('kind', 'status')
    date_hierarchy = 'due_date'


@admin.register(Interaction)
class InteractionAdmin(admin.ModelAdmin):
    list_display = ('contact', 'channel', 'direction', 'occurred_at')
    list_filter = ('channel', 'direction')
    date_hierarchy = 'occurred_at'
    search_fields = ('contact__name', 'summary')


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ('name', 'theme', 'start_date', 'end_date')


@admin.register(ContentStory)
class ContentStoryAdmin(admin.ModelAdmin):
    list_display = ('title', 'feature_name', 'date_published', 'has_hero', 'has_consent', 'is_active')
    list_filter = ('has_consent', 'is_active', 'social_published')
    search_fields = ('title', 'feature_name', 'headline')

    def has_hero(self, obj):
        return bool(obj.hero_image_url)
    has_hero.boolean = True


@admin.register(Draft)
class DraftAdmin(admin.ModelAdmin):
    list_display = ('kind', 'status', 'created_by_agent', 'contact', 'sent_at', 'created_at')
    list_filter = ('kind', 'status', 'created_by_agent')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ContactMergeLog)
class ContactMergeLogAdmin(admin.ModelAdmin):
    list_display = ('winner', 'loser', 'active', 'created_at')
    list_filter = ('active',)
    readonly_fields = ('loser_snapshot', 'created_at', 'updated_at')


@admin.register(Expectation)
class ExpectationAdmin(admin.ModelAdmin):
    list_display = ('contact', 'kind', 'cadence', 'amount', 'next_expected_date', 'active')
    list_filter = ('kind', 'cadence', 'active')
