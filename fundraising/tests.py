import io
import json
from datetime import date
from decimal import Decimal
from unittest import mock

from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase
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


class PhotosParseTests(SimpleTestCase):
    def test_parse_drive_ref_cases(self):
        from fundraising.services.photos import parse_drive_ref

        self.assertEqual(parse_drive_ref("https://drive.google.com/drive/folders/1AbC_x-y?usp=sharing"), ("folder", "1AbC_x-y"))
        self.assertEqual(parse_drive_ref("https://drive.google.com/file/d/11u5Du6/view"), ("file", "11u5Du6"))
        self.assertEqual(parse_drive_ref("https://drive.google.com/uc?id=99XyZ"), ("file", "99XyZ"))
        self.assertEqual(parse_drive_ref("https://drive.google.com/open?id=42Abc"), ("file", "42Abc"))
        self.assertEqual(parse_drive_ref("https://drive.google.com/drive/search?q=Usisipho"), (None, None))
        self.assertEqual(parse_drive_ref(""), (None, None))
        self.assertEqual(parse_drive_ref("not a url"), (None, None))


class PhotosListTests(SimpleTestCase):
    def _drive_returning(self, listings):
        """listings: dict[parent_id] -> list of file dicts."""
        drive = mock.MagicMock()

        def files_list(q, fields, pageSize=None):
            parent = q.split("'")[1]
            req = mock.MagicMock()
            req.execute.return_value = {"files": listings.get(parent, [])}
            return req

        drive.files.return_value.list.side_effect = files_list
        return drive

    def test_folder_filters_non_images(self):
        from fundraising.services.photos import list_candidate_images
        drive = self._drive_returning({"F": [
            {"id": "a", "name": "a.jpg", "mimeType": "image/jpeg"},
            {"id": "v", "name": "v.mp4", "mimeType": "video/mp4"},
        ]})
        out = list_candidate_images(drive, "folder", "F")
        self.assertEqual([c["id"] for c in out], ["a"])

    def test_folder_recurses_one_level_when_no_images(self):
        from fundraising.services.photos import list_candidate_images
        drive = self._drive_returning({
            "F": [{"id": "sub", "name": "sub", "mimeType": "application/vnd.google-apps.folder"}],
            "sub": [{"id": "b", "name": "b.jpg", "mimeType": "image/jpeg"}],
        })
        out = list_candidate_images(drive, "folder", "F")
        self.assertEqual([c["id"] for c in out], ["b"])

    def test_single_image_file(self):
        from fundraising.services.photos import list_candidate_images
        drive = mock.MagicMock()
        drive.files.return_value.get.return_value.execute.return_value = {
            "id": "x", "name": "x.jpg", "mimeType": "image/jpeg"}
        self.assertEqual(len(list_candidate_images(drive, "file", "x")), 1)

    def test_single_video_file_yields_nothing(self):
        from fundraising.services.photos import list_candidate_images
        drive = mock.MagicMock()
        drive.files.return_value.get.return_value.execute.return_value = {
            "id": "x", "name": "x.mp4", "mimeType": "video/mp4"}
        self.assertEqual(list_candidate_images(drive, "file", "x"), [])

    def test_404_maps_to_drive_access_error(self):
        from googleapiclient.errors import HttpError
        from fundraising.services.photos import list_candidate_images, DriveAccessError
        resp = mock.MagicMock(); resp.status = 404
        drive = mock.MagicMock()
        drive.files.return_value.get.return_value.execute.side_effect = HttpError(resp, b"not found")
        with self.assertRaises(DriveAccessError):
            list_candidate_images(drive, "file", "x")


class PhotosDownscaleTests(SimpleTestCase):
    def _png_bytes(self, w, h):
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (w, h), (120, 80, 40)).save(buf, format="PNG")
        return buf.getvalue()

    def test_downscale_returns_jpeg_within_max(self):
        from PIL import Image
        from fundraising.services.photos import downscale_jpeg
        out = downscale_jpeg(self._png_bytes(2000, 1500), max_px=768)
        img = Image.open(io.BytesIO(out))
        self.assertEqual(img.format, "JPEG")
        self.assertLessEqual(max(img.size), 768)

    def test_downscale_rejects_unreadable(self):
        from fundraising.services.photos import downscale_jpeg, UnreadableImage
        with self.assertRaises(UnreadableImage):
            downscale_jpeg(b"not an image")

    def test_download_bytes_uses_get_media(self):
        from fundraising.services.photos import download_bytes
        drive = mock.MagicMock()
        drive.files.return_value.get_media.return_value.execute.return_value = b"RAW"
        self.assertEqual(download_bytes(drive, "fid"), b"RAW")
        drive.files.return_value.get_media.assert_called_once_with(fileId="fid")


def _resp(text):
    block = mock.MagicMock(); block.text = text
    r = mock.MagicMock(); r.content = [block]
    return r


class PickHeroTests(SimpleTestCase):
    ctx = {"feature_name": "Nomsa", "headline": "A mother graduates", "narrative": "Nomsa...", "category": ["Youth"]}

    def test_single_candidate_no_api_call(self):
        from fundraising.services.photos import pick_hero
        client = mock.MagicMock()
        out = pick_hero(client, [{"name": "a.jpg", "b64": "AAAA"}], self.ctx)
        self.assertEqual(out["chosen_index"], 0)
        self.assertTrue(out["fallback"])
        client.messages.create.assert_not_called()

    def test_valid_json_pick(self):
        from fundraising.services.photos import pick_hero
        client = mock.MagicMock()
        client.messages.create.return_value = _resp(
            '{"chosen_index":1,"reason":"woman in focus","rejected":[{"index":0,"why":"blurry"}]}')
        out = pick_hero(client, [{"name": "a", "b64": "AA"}, {"name": "b", "b64": "BB"}], self.ctx)
        self.assertEqual(out["chosen_index"], 1)
        self.assertFalse(out["fallback"])

    def test_malformed_json_falls_back(self):
        from fundraising.services.photos import pick_hero
        client = mock.MagicMock()
        client.messages.create.return_value = _resp("sorry, no json here")
        out = pick_hero(client, [{"name": "a", "b64": "AA"}, {"name": "b", "b64": "BB"}], self.ctx)
        self.assertEqual(out["chosen_index"], 0)
        self.assertTrue(out["fallback"])

    def test_out_of_range_index_falls_back(self):
        from fundraising.services.photos import pick_hero
        client = mock.MagicMock()
        client.messages.create.return_value = _resp('{"chosen_index":9,"reason":"x","rejected":[]}')
        out = pick_hero(client, [{"name": "a", "b64": "AA"}, {"name": "b", "b64": "BB"}], self.ctx)
        self.assertEqual(out["chosen_index"], 0)
        self.assertTrue(out["fallback"])


class UploadHeroTests(SimpleTestCase):
    def test_upload_uses_stable_key_and_no_acl(self):
        from fundraising.services.photos import upload_hero
        story = mock.MagicMock(source_airtable_id="recABC")
        bucket = mock.MagicMock()
        blob = bucket.blob.return_value
        url = upload_hero(bucket, story, b"JPEGDATA", "image/jpeg")
        bucket.blob.assert_called_once_with("fundraising/heroes/recABC.jpg")
        blob.upload_from_string.assert_called_once_with(b"JPEGDATA", content_type="image/jpeg")
        blob.make_public.assert_not_called()
        self.assertEqual(url, "https://storage.googleapis.com/masi-website/fundraising/heroes/recABC.jpg")

    def test_upload_png_extension(self):
        from fundraising.services.photos import upload_hero
        story = mock.MagicMock(source_airtable_id="recP")
        bucket = mock.MagicMock()
        upload_hero(bucket, story, b"X", "image/png")
        bucket.blob.assert_called_once_with("fundraising/heroes/recP.png")


class PhotoClientBuilderTests(SimpleTestCase):
    def test_anthropic_client_requires_key(self):
        from fundraising.services.photos import anthropic_client
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(ValueError):
                anthropic_client()

    def test_gcs_bucket_requires_credentials(self):
        from fundraising.services.photos import gcs_bucket
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(ValueError):
                gcs_bucket()


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
