import os

from django.db import transaction

from fundraising.models import Draft
from fundraising.services import mailchimp


def record_and_draft(
    subject,
    html,
    kind='newsletter_broadcast',
    shell='studio',
    source_type='',
    story_ids=None,
    title=None,
    create_mailchimp=True,
    audience_id=None,
):
    """Record a spine Draft and optionally create its Mailchimp draft."""
    with transaction.atomic():
        draft = Draft.objects.create(
            kind=kind,
            status='draft',
            created_by_agent=shell,
            subject=subject,
            draft_body=html,
            source_meta={
                'shell': shell,
                'source_type': source_type,
                'story_ids': story_ids or [],
            },
        )
        campaign = None
        if create_mailchimp:
            audience_id = audience_id or os.getenv('MAILCHIMP_AUDIENCE_ID_ALL_DONORS')
            campaign = mailchimp.create_draft_campaign(
                subject,
                html,
                audience_id,
                title=title or f"[AI draft] {subject}",
            )
            draft.external_ref = campaign['campaign_id']
            draft.save(update_fields=['external_ref', 'updated_at'])

    return {'draft': draft, 'campaign': campaign}
