"""Fundraising spine models.

These tables hold donor PII with money attached. Exclude or sanitize them when
refreshing local snapshots from production, and keep analysis runs read-only
against production data.
"""

from django.contrib.auth.models import User
from django.db import models
from django.db.models import CheckConstraint, Q


CONTACT_KIND_CHOICES = [
    ('individual', 'Individual'),
    ('foundation', 'Foundation'),
    ('corporate', 'Corporate'),
    ('government', 'Government'),
]
TIER_CHOICES = [
    ('1_personal', 'Tier 1 - Personal'),
    ('2_warm', 'Tier 2 - Warm'),
    ('3_list', 'Tier 3 - List'),
]
SEGMENT_CHOICES = [
    ('us', 'US donors'),
    ('rsa_eu', 'RSA & EU donors'),
    ('foundations', 'Foundations'),
]
RECEIVING_ENTITY_CHOICES = [
    ('us', 'US 501(c)(3)'),
    ('sa', 'South Africa'),
]
CURRENCY_CHOICES = [
    ('USD', 'US Dollar'),
    ('ZAR', 'South African Rand'),
    ('EUR', 'Euro'),
    ('GBP', 'British Pound'),
]
OPPORTUNITY_STAGE_CHOICES = [
    ('identified', 'Identified'),
    ('cultivating', 'Cultivating'),
    ('applied', 'Applied'),
    ('won', 'Won'),
    ('declined', 'Declined'),
]
DELIVERABLE_KIND_CHOICES = [
    ('application_step', 'Application step'),
    ('report', 'Report'),
]
DELIVERABLE_STATUS_CHOICES = [
    ('open', 'Open'),
    ('submitted', 'Submitted'),
    ('done', 'Done'),
    ('waived', 'Waived'),
]
INTERACTION_CHANNEL_CHOICES = [
    ('email_sent', 'Email sent'),
    ('email_received', 'Email received'),
    ('newsletter', 'Newsletter'),
    ('meeting', 'Meeting'),
    ('call', 'Call'),
    ('note', 'Note'),
]
INTERACTION_DIRECTION_CHOICES = [
    ('outbound', 'Outbound'),
    ('inbound', 'Inbound'),
    ('internal', 'Internal'),
]
DRAFT_KIND_CHOICES = [
    ('newsletter_broadcast', 'Newsletter broadcast'),
    ('personal_send', 'Personal send'),
    ('grant_answer', 'Grant answer'),
    ('grant_application', 'Grant application'),
    ('report_narrative', 'Report narrative'),
    ('interaction_capture', 'Interaction capture'),
    ('other', 'Other'),
]
DRAFT_STATUS_CHOICES = [
    ('draft', 'Draft'),
    ('approved', 'Approved'),
    ('sent', 'Sent'),
    ('discarded', 'Discarded'),
]
EXPECTATION_KIND_CHOICES = [
    ('annual_grant', 'Annual grant contract'),
    ('monthly_donor', 'Monthly donor'),
]
EXPECTATION_CADENCE_CHOICES = [
    ('annual', 'Annual'),
    ('monthly', 'Monthly'),
]


class Contact(models.Model):
    kind = models.CharField(max_length=20, choices=CONTACT_KIND_CHOICES)
    name = models.CharField(max_length=200)
    organization = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='members',
    )
    role_title = models.CharField(max_length=120, blank=True, default="")
    tier = models.CharField(max_length=12, choices=TIER_CHOICES, blank=True, default="")
    segment = models.CharField(max_length=20, choices=SEGMENT_CHOICES, blank=True, default="")
    primary_email = models.EmailField(blank=True, default="")
    emails = models.JSONField(null=True, blank=True)
    phone = models.CharField(max_length=40, blank=True, default="")
    newsletter_consent = models.BooleanField(default=False)
    notes = models.TextField(blank=True, default="")
    private_notes = models.TextField(blank=True, default="")
    merged_into = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='merged_from',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'fundraising_contact'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_kind_display()})"


class Donation(models.Model):
    contact = models.ForeignKey(Contact, on_delete=models.PROTECT, related_name='donations')
    receiving_entity = models.CharField(max_length=4, choices=RECEIVING_ENTITY_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES)
    date = models.DateField()
    grant = models.ForeignKey(
        'Grant',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='donations',
    )
    method = models.CharField(max_length=40, blank=True, default="")
    source_reference = models.CharField(max_length=120, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'fundraising_donation'
        ordering = ['-date']

    def __str__(self):
        return f"{self.amount} {self.currency} from {self.contact.name} ({self.date})"


class Opportunity(models.Model):
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name='opportunities')
    name = models.CharField(max_length=200)
    stage = models.CharField(max_length=20, choices=OPPORTUNITY_STAGE_CHOICES, default='identified')
    amount_requested = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, blank=True, default="")
    deadline = models.DateField(null=True, blank=True)
    renews_grant = models.ForeignKey(
        'Grant',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='renewals',
    )
    opened_at = models.DateField(null=True, blank=True)
    closed_at = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'fundraising_opportunity'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} [{self.get_stage_display()}]"


class Grant(models.Model):
    opportunity = models.OneToOneField(
        Opportunity,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='grant',
    )
    contact = models.ForeignKey(Contact, on_delete=models.PROTECT, related_name='grants')
    name = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES)
    receiving_entity = models.CharField(max_length=4, choices=RECEIVING_ENTITY_CHOICES, blank=True, default="")
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    agreement_reference = models.CharField(max_length=120, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'fundraising_grant'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.amount} {self.currency}"


class Deliverable(models.Model):
    opportunity = models.ForeignKey(
        Opportunity,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='deliverables',
    )
    grant = models.ForeignKey(
        Grant,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='deliverables',
    )
    kind = models.CharField(max_length=20, choices=DELIVERABLE_KIND_CHOICES)
    title = models.CharField(max_length=200)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=DELIVERABLE_STATUS_CHOICES, default='open')
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'fundraising_deliverable'
        ordering = ['due_date']
        constraints = [
            CheckConstraint(
                condition=(
                    (Q(opportunity__isnull=False) & Q(grant__isnull=True))
                    | (Q(opportunity__isnull=True) & Q(grant__isnull=False))
                ),
                name='deliverable_exactly_one_parent',
            ),
        ]

    def __str__(self):
        return f"{self.title} (due {self.due_date})"


class Interaction(models.Model):
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name='interactions')
    channel = models.CharField(max_length=20, choices=INTERACTION_CHANNEL_CHOICES)
    direction = models.CharField(
        max_length=10,
        choices=INTERACTION_DIRECTION_CHOICES,
        blank=True,
        default="",
    )
    occurred_at = models.DateTimeField()
    summary = models.CharField(max_length=300, blank=True, default="")
    body = models.TextField(blank=True, default="")
    campaign = models.ForeignKey(
        'Campaign',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='interactions',
    )
    source_draft = models.ForeignKey(
        'Draft',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='interactions',
    )
    external_id = models.CharField(max_length=200, blank=True, default="", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'fundraising_interaction'
        ordering = ['-occurred_at']
        constraints = [
            models.UniqueConstraint(
                fields=['external_id'],
                condition=~Q(external_id=''),
                name='interaction_external_id_unique',
            ),
        ]

    def __str__(self):
        return f"{self.get_channel_display()} with {self.contact.name} @ {self.occurred_at:%Y-%m-%d}"


class Campaign(models.Model):
    name = models.CharField(max_length=200)
    theme = models.CharField(max_length=200, blank=True, default="")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'fundraising_campaign'
        ordering = ['-start_date']

    def __str__(self):
        return self.name


class ContentStory(models.Model):
    source_airtable_id = models.CharField(max_length=50, unique=True, db_index=True)
    feature_name = models.CharField(max_length=200, blank=True, default="")
    title = models.CharField(max_length=300, blank=True, default="")
    headline = models.TextField(blank=True, default="")
    narrative = models.TextField(blank=True, default="")
    quote = models.TextField(blank=True, default="")
    stats_text = models.TextField(blank=True, default="")
    category = models.JSONField(null=True, blank=True)
    school = models.JSONField(null=True, blank=True)
    date_published = models.DateField(null=True, blank=True)
    photo_urls = models.JSONField(null=True, blank=True)
    has_consent = models.BooleanField(default=False)
    drive_link = models.CharField(max_length=500, blank=True, default="")
    social_published = models.CharField(max_length=50, blank=True, default="")
    is_active = models.BooleanField(default=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'fundraising_content_story'
        ordering = ['-date_published']

    def __str__(self):
        return self.title or self.headline or self.feature_name


class Draft(models.Model):
    kind = models.CharField(max_length=30, choices=DRAFT_KIND_CHOICES)
    status = models.CharField(max_length=12, choices=DRAFT_STATUS_CHOICES, default='draft')
    contact = models.ForeignKey(
        Contact,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='drafts',
    )
    opportunity = models.ForeignKey(
        Opportunity,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='drafts',
    )
    campaign = models.ForeignKey(
        Campaign,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='drafts',
    )
    created_by_agent = models.CharField(max_length=60, blank=True, default="")
    subject = models.CharField(max_length=300, blank=True, default="")
    draft_body = models.TextField()
    final_body = models.TextField(blank=True, default="")
    edit_classification = models.JSONField(null=True, blank=True)
    external_ref = models.CharField(max_length=200, blank=True, default="", db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'fundraising_draft'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_kind_display()} draft [{self.status}]"


class ContactMergeLog(models.Model):
    winner = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name='merges_won')
    loser = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name='merges_lost')
    loser_snapshot = models.JSONField()
    reason = models.TextField(blank=True, default="")
    merged_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'fundraising_contact_merge_log'
        ordering = ['-created_at']

    def __str__(self):
        return f"merged contact {self.loser_id} -> {self.winner_id}"


class Expectation(models.Model):
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name='expectations')
    kind = models.CharField(max_length=20, choices=EXPECTATION_KIND_CHOICES)
    grant = models.ForeignKey(
        Grant,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='expectations',
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, blank=True, default="")
    cadence = models.CharField(max_length=10, choices=EXPECTATION_CADENCE_CHOICES)
    next_expected_date = models.DateField(null=True, blank=True)
    active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'fundraising_expectation'
        ordering = ['next_expected_date']

    def __str__(self):
        return f"{self.get_kind_display()} expectation for {self.contact.name}"
