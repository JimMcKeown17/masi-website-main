from datetime import date
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from .models import (
    Contact,
    ContactMergeLog,
    ContentStory,
    Deliverable,
    Donation,
    Draft,
    Grant,
    Interaction,
    Opportunity,
)


class FundraisingSchemaTests(TestCase):
    def test_happy_path_contact_donation_opportunity_grant_deliverable(self):
        contact = Contact.objects.create(
            kind='foundation',
            name='Example Foundation',
            primary_email='programs@example.org',
        )
        donation = Donation.objects.create(
            contact=contact,
            receiving_entity='us',
            amount=Decimal('2500.00'),
            currency='USD',
            date=date(2026, 7, 1),
            method='eft',
        )
        opportunity = Opportunity.objects.create(
            contact=contact,
            name='2026 literacy grant',
            amount_requested=Decimal('50000.00'),
            currency='USD',
        )

        opportunity.stage = 'won'
        opportunity.closed_at = date(2026, 7, 2)
        opportunity.save()

        grant = Grant.objects.create(
            opportunity=opportunity,
            contact=contact,
            name='2026 literacy grant',
            amount=Decimal('50000.00'),
            currency='USD',
            receiving_entity='us',
        )
        deliverable = Deliverable.objects.create(
            grant=grant,
            kind='report',
            title='Final report',
            due_date=date(2026, 12, 31),
        )

        donation.grant = grant
        donation.save()

        self.assertEqual(contact.donations.get(), donation)
        self.assertEqual(opportunity.grant, grant)
        self.assertEqual(grant.deliverables.get(), deliverable)

    def test_deliverable_requires_exactly_one_parent(self):
        contact = Contact.objects.create(kind='foundation', name='Example Foundation')
        opportunity = Opportunity.objects.create(contact=contact, name='Application')
        grant = Grant.objects.create(
            contact=contact,
            name='Existing grant',
            amount=Decimal('1000.00'),
            currency='USD',
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Deliverable.objects.create(kind='report', title='No parent')

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Deliverable.objects.create(
                    opportunity=opportunity,
                    grant=grant,
                    kind='report',
                    title='Two parents',
                )

        opportunity_deliverable = Deliverable.objects.create(
            opportunity=opportunity,
            kind='application_step',
            title='Submit LOI',
        )
        grant_deliverable = Deliverable.objects.create(
            grant=grant,
            kind='report',
            title='Submit report',
        )

        self.assertEqual(opportunity_deliverable.opportunity, opportunity)
        self.assertEqual(grant_deliverable.grant, grant)

    def test_interaction_external_id_unique_only_when_present(self):
        contact = Contact.objects.create(kind='individual', name='Jane Donor')

        Interaction.objects.create(
            contact=contact,
            channel='email_received',
            occurred_at=timezone.now(),
        )
        Interaction.objects.create(
            contact=contact,
            channel='note',
            occurred_at=timezone.now(),
        )

        Interaction.objects.create(
            contact=contact,
            channel='email_sent',
            occurred_at=timezone.now(),
            external_id='gmail-message-1',
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Interaction.objects.create(
                    contact=contact,
                    channel='email_sent',
                    occurred_at=timezone.now(),
                    external_id='gmail-message-1',
                )

    def test_draft_retains_draft_and_final_body(self):
        draft = Draft.objects.create(
            kind='personal_send',
            contact=Contact.objects.create(kind='individual', name='Jane Donor'),
            subject='Thank you',
            draft_body='Initial agent draft',
        )

        draft.final_body = 'Final human-approved message'
        draft.status = 'sent'
        draft.sent_at = timezone.now()
        draft.save()
        draft.refresh_from_db()

        self.assertEqual(draft.draft_body, 'Initial agent draft')
        self.assertEqual(draft.final_body, 'Final human-approved message')

    def test_contact_merge_self_link_and_log_snapshot_can_be_created(self):
        winner = Contact.objects.create(kind='individual', name='Jane Donor')
        loser = Contact.objects.create(
            kind='individual',
            name='J. Donor',
            primary_email='jane@example.org',
        )

        loser.merged_into = winner
        loser.save()

        merge_log = ContactMergeLog.objects.create(
            winner=winner,
            loser=loser,
            loser_snapshot={
                'id': loser.id,
                'name': loser.name,
                'primary_email': loser.primary_email,
            },
            reason='Duplicate import row',
        )

        self.assertEqual(loser.merged_into, winner)
        self.assertEqual(merge_log.loser_snapshot['primary_email'], 'jane@example.org')


class ContentStoryTests(TestCase):
    def test_content_story_can_store_airtable_success_story_snapshot(self):
        story = ContentStory.objects.create(
            source_airtable_id='recSuccessStory1',
            feature_name='Akhona',
            title='Akhona finds her voice',
            headline='A child begins reading with confidence',
            narrative='Akhona now asks to read first in her group.',
            quote='I can read the story myself.',
            stats_text='Completed 12 sessions.',
            category=['Literacy', 'Confidence'],
            school=['Masi Primary'],
            date_published=date(2026, 6, 15),
            photo_urls=[{'url': 'https://example.com/photo.jpg', 'filename': 'photo.jpg'}],
            has_consent=True,
            drive_link='https://drive.google.com/example',
            social_published='Published',
        )

        story.refresh_from_db()

        self.assertEqual(story.source_airtable_id, 'recSuccessStory1')
        self.assertEqual(story.category, ['Literacy', 'Confidence'])
        self.assertEqual(story.school, ['Masi Primary'])
        self.assertTrue(story.has_consent)
        self.assertEqual(str(story), 'Akhona finds her voice')

    def test_success_story_extract_row_maps_airtable_fields(self):
        from fundraising.management.commands.sync_airtable_success_stories import Command

        record = {
            'id': 'recSuccessStory2',
            'fields': {
                'Full Name of Feature': 'Sipho',
                'Title': 'Sipho keeps going',
                'Headline': 'A mentor helps Sipho stay confident',
                'Story Descriptive / Narrative': 'Sipho kept practising after school.',
                'Quote': 'My mentor helps me try again.',
                'Stats': 'Attended 9 sessions.',
                'Category': ['Mentorship', 'Persistence'],
                "Child's School": ['Masi Primary'],
                'Date Published': '2026-06-20',
                'Attachments': [
                    {
                        'url': 'https://example.com/photo-1.jpg',
                        'filename': 'photo-1.jpg',
                    },
                    {
                        'url': 'https://example.com/photo-2.jpg',
                    },
                ],
                "Child's Consent Form": [
                    {
                        'url': 'https://example.com/consent.pdf',
                        'filename': 'consent.pdf',
                    }
                ],
                'Google Drive Link': 'https://drive.google.com/story',
                'Social Media Published': 'Ready',
            },
        }

        row = Command().extract_row(record)

        self.assertEqual(row['source_airtable_id'], 'recSuccessStory2')
        self.assertEqual(row['feature_name'], 'Sipho')
        self.assertEqual(row['category'], ['Mentorship', 'Persistence'])
        self.assertEqual(row['school'], ['Masi Primary'])
        self.assertEqual(row['date_published'], date(2026, 6, 20))
        self.assertEqual(
            row['photo_urls'],
            [
                {'url': 'https://example.com/photo-1.jpg', 'filename': 'photo-1.jpg'},
                {'url': 'https://example.com/photo-2.jpg', 'filename': ''},
            ],
        )
        self.assertTrue(row['has_consent'])
        self.assertEqual(row['social_published'], 'Ready')

    def test_success_story_extract_row_marks_missing_consent_false(self):
        from fundraising.management.commands.sync_airtable_success_stories import Command

        row = Command().extract_row({'id': 'recNoConsent', 'fields': {}})

        self.assertFalse(row['has_consent'])


class HeroImageFieldTests(TestCase):
    def test_hero_image_url_defaults_blank_and_is_settable(self):
        from fundraising.models import ContentStory

        s = ContentStory.objects.create(source_airtable_id="recHERO1")
        self.assertEqual(s.hero_image_url, "")
        s.hero_image_url = "https://storage.googleapis.com/masi-website/fundraising/heroes/recHERO1.jpg"
        s.save(update_fields=["hero_image_url"])
        s.refresh_from_db()
        self.assertTrue(s.hero_image_url.endswith("recHERO1.jpg"))


class MailchimpServiceTests(TestCase):
    def test_mailchimp_server_prefix_and_urls_come_from_api_key_suffix(self):
        from fundraising.services.mailchimp import (
            api_base_url,
            campaign_edit_url,
            server_prefix_from_api_key,
        )

        prefix = server_prefix_from_api_key('abc123-us21')

        self.assertEqual(prefix, 'us21')
        self.assertEqual(api_base_url('abc123-us21'), 'https://us21.api.mailchimp.com/3.0')
        self.assertEqual(
            campaign_edit_url(prefix, 123456),
            'https://us21.admin.mailchimp.com/campaigns/edit?id=123456',
        )
