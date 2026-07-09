import io
import json
import os
import tempfile
from datetime import date
from decimal import Decimal
from unittest import mock

from django.core.management import call_command
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

    def test_optimize_for_email_shrinks_to_email_size(self):
        import io
        from PIL import Image
        from fundraising.services.photos import optimize_for_email
        big = self._png_bytes(3000, 2200)
        out = optimize_for_email(big)
        img = Image.open(io.BytesIO(out))
        self.assertEqual(img.format, "JPEG")        # PNG normalized to JPEG
        self.assertLessEqual(max(img.size), 1600)   # capped for an email header
        self.assertLess(len(out), 500_000)          # email-safe size, not multi-MB


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


class ContactSheetTests(SimpleTestCase):
    def _records(self):
        return [
            {"title": "Nomsa Dlamini", "meta": "Youth - 2026", "status": "stored", "fallback": False,
             "chosen_index": 0, "reason": "woman in sharp focus",
             "hero_url": "https://storage.googleapis.com/masi-website/fundraising/heroes/rec1.jpg",
             "candidates": [{"name": "a.jpg", "b64": "AAAA", "rejected_why": None},
                            {"name": "b.jpg", "b64": "BBBB", "rejected_why": "blurry"}],
             "problem_reason": None},
            {"title": "Usisipho Mehlo", "meta": "", "status": "problem", "fallback": False,
             "chosen_index": None, "reason": "", "hero_url": None, "candidates": [],
             "problem_reason": "no usable link (search URL)"},
        ]

    def test_renders_hero_and_problem(self):
        from fundraising.services.photos_report import render_contact_sheet
        html = render_contact_sheet(self._records())
        self.assertIn("<html", html.lower())
        self.assertIn("Nomsa Dlamini", html)
        self.assertIn("HERO", html)
        self.assertIn("data:image/jpeg;base64,AAAA", html)
        self.assertIn("no usable link (search URL)", html)
        self.assertIn("1 stored", html)  # summary chip


class BackfillCommandTests(TestCase):
    def setUp(self):
        self.report = os.path.join(tempfile.mkdtemp(), "sheet.html")

    def _run(self, **kw):
        call_command("backfill_story_heroes", report=self.report, **kw)

    @mock.patch("fundraising.services.photos.upload_hero", return_value="https://storage.googleapis.com/masi-website/fundraising/heroes/recF.jpg")
    @mock.patch("fundraising.services.photos.pick_hero", return_value={"chosen_index": 0, "reason": "ok", "rejected": [], "fallback": False})
    @mock.patch("fundraising.services.photos.downscale_jpeg", return_value=b"THUMB")
    @mock.patch("fundraising.services.photos.download_bytes", return_value=b"RAW")
    @mock.patch("fundraising.services.photos.list_candidate_images", return_value=[{"id": "a", "name": "a.jpg", "mimeType": "image/jpeg"}])
    @mock.patch("fundraising.services.photos.gcs_bucket")
    @mock.patch("fundraising.services.photos.anthropic_client")
    @mock.patch("fundraising.services.photos.drive_client")
    def test_folder_story_gets_hero(self, *_):
        s = ContentStory.objects.create(source_airtable_id="recF", title="Nomsa",
            drive_link="https://drive.google.com/drive/folders/FID")
        self._run()
        s.refresh_from_db()
        self.assertTrue(s.hero_image_url.endswith("recF.jpg"))
        self.assertTrue(os.path.exists(self.report))

    @mock.patch("fundraising.services.photos.gcs_bucket")
    @mock.patch("fundraising.services.photos.anthropic_client")
    @mock.patch("fundraising.services.photos.drive_client")
    def test_search_url_is_a_problem_not_a_crash(self, *_):
        s = ContentStory.objects.create(source_airtable_id="recS", title="Usisipho",
            drive_link="https://drive.google.com/drive/search?q=Usisipho")
        self._run()
        s.refresh_from_db()
        self.assertEqual(s.hero_image_url, "")

    @mock.patch("fundraising.services.photos.upload_hero", return_value="https://x/recF.jpg")
    @mock.patch("fundraising.services.photos.pick_hero", return_value={"chosen_index": 0, "reason": "ok", "rejected": [], "fallback": False})
    @mock.patch("fundraising.services.photos.downscale_jpeg", return_value=b"T")
    @mock.patch("fundraising.services.photos.download_bytes", return_value=b"R")
    @mock.patch("fundraising.services.photos.list_candidate_images", return_value=[{"id": "a", "name": "a.jpg", "mimeType": "image/jpeg"}])
    @mock.patch("fundraising.services.photos.gcs_bucket")
    @mock.patch("fundraising.services.photos.anthropic_client")
    @mock.patch("fundraising.services.photos.drive_client")
    def test_dry_run_does_not_save(self, *_):
        s = ContentStory.objects.create(source_airtable_id="recF", title="Nomsa",
            drive_link="https://drive.google.com/drive/folders/FID")
        self._run(dry_run=True)
        s.refresh_from_db()
        self.assertEqual(s.hero_image_url, "")
        self.assertTrue(os.path.exists(self.report))

    @mock.patch("fundraising.services.photos.upload_hero")
    @mock.patch("fundraising.services.photos.pick_hero", return_value={"chosen_index": 0, "reason": "no parseable choice", "rejected": [], "fallback": True})
    @mock.patch("fundraising.services.photos.downscale_jpeg", return_value=b"T")
    @mock.patch("fundraising.services.photos.download_bytes", return_value=b"R")
    @mock.patch("fundraising.services.photos.list_candidate_images", return_value=[
        {"id": "a", "name": "a.jpg", "mimeType": "image/jpeg"},
        {"id": "b", "name": "b.jpg", "mimeType": "image/jpeg"}])
    @mock.patch("fundraising.services.photos.gcs_bucket")
    @mock.patch("fundraising.services.photos.anthropic_client")
    @mock.patch("fundraising.services.photos.drive_client")
    def test_multi_candidate_model_failure_is_problem_not_published(
            self, m_drive, m_anthropic, m_bucket, m_list, m_download, m_downscale, m_pick, m_upload):
        # Two images + a fallback pick means the model could not choose -> no upload, no save.
        s = ContentStory.objects.create(source_airtable_id="recM", title="Two Photos",
            drive_link="https://drive.google.com/drive/folders/FID")
        self._run()
        s.refresh_from_db()
        self.assertEqual(s.hero_image_url, "")
        m_upload.assert_not_called()


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


class EmailTemplateTests(SimpleTestCase):
    def test_render_email_has_logo_lead_body_cta_and_socials(self):
        from fundraising.services.email_template import render_email, LOGO_URL, SOCIAL_LINKS
        html = render_email(
            body_html="<p>Dear Masi Friends</p>",
            lead_hero_url="https://storage.googleapis.com/masi-website/fundraising/heroes/recX.jpg",
            cta_text="Holiday Match",
            cta_url="https://masinyusane.org/donate",
        )
        self.assertIn(LOGO_URL, html)                          # logo header
        self.assertIn("/heroes/recX.jpg", html)               # lead hero image
        self.assertIn("Dear Masi Friends", html)              # model-written body
        self.assertIn("Holiday Match", html)                  # CTA button text
        self.assertIn("https://masinyusane.org/donate", html)  # CTA target
        for _name, url in SOCIAL_LINKS:                        # social footer
            self.assertIn(url, html)

    def test_render_email_without_lead_hero_omits_hero_image(self):
        from fundraising.services.email_template import render_email, LOGO_URL
        html = render_email("<p>Body text</p>", lead_hero_url="", cta_text="Donate",
                            cta_url="https://masinyusane.org/donate")
        self.assertIn(LOGO_URL, html)
        self.assertIn("Body text", html)
        self.assertIn("Donate", html)
        self.assertNotIn("/heroes/", html)  # no lead hero when none provided


def _story(hero=""):
    from types import SimpleNamespace
    return SimpleNamespace(headline="h", title="t", narrative="n", quote="q",
                           feature_name="f", school=[], category=[], hero_image_url=hero)


class ComposePayloadTests(SimpleTestCase):
    def test_story_payload_includes_hero_image_url_and_lead_flag(self):
        from fundraising.services.compose import _story_payload
        p = _story_payload(_story("https://x/heroes/rec1.jpg"), is_lead=True)
        self.assertEqual(p["hero_image_url"], "https://x/heroes/rec1.jpg")
        self.assertTrue(p["is_lead"])


class ComposeSystemPromptTests(SimpleTestCase):
    def test_prompt_forbids_surnames_and_requests_inline_images(self):
        from fundraising.services.compose import _system_prompt
        p = _system_prompt("VOICE GUIDE TEXT").lower()
        self.assertIn("voice guide text", p)
        self.assertIn("first name", p)
        self.assertTrue("surname" in p or "last name" in p)
        self.assertIn("inline", p)


class LeadHeroTests(SimpleTestCase):
    def test_lead_is_first_story_with_a_photo(self):
        from fundraising.services.compose import _lead_hero_url
        self.assertEqual(_lead_hero_url([_story(""), _story("https://x/heroes/rec2.jpg")]),
                         "https://x/heroes/rec2.jpg")
        self.assertEqual(_lead_hero_url([_story("")]), "")


class MissingInlineImagesTests(SimpleTestCase):
    def test_flags_dropped_non_lead_photos_only(self):
        from fundraising.services.compose import _missing_inline_images
        lead = "https://x/heroes/rec1.jpg"
        stories = [_story(lead), _story("https://x/heroes/rec2.jpg"), _story("")]
        present = "<p>body https://x/heroes/rec2.jpg</p>"
        self.assertEqual(_missing_inline_images(present, stories, lead), [])
        self.assertEqual(_missing_inline_images("<p>no imgs</p>", stories, lead),
                         ["https://x/heroes/rec2.jpg"])


class ComposeNewsletterWrapTests(SimpleTestCase):
    @mock.patch("fundraising.services.compose.anthropic.Anthropic")
    def test_wraps_body_with_chrome_and_lead_hero(self, m_anthropic):
        import os
        from fundraising.services.compose import compose_newsletter
        from fundraising.services.email_template import LOGO_URL
        block = mock.MagicMock()
        block.text = '{"subject":"Hello","html":"<p>Dear Masi Friends https://x/heroes/rec2.jpg</p>"}'
        resp = mock.MagicMock(); resp.content = [block]
        m_anthropic.return_value.messages.create.return_value = resp
        stories = [_story("https://x/heroes/rec1.jpg"), _story("https://x/heroes/rec2.jpg")]
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
            result = compose_newsletter(stories, None, "GUIDE",
                                        cta_text="Give Now", cta_url="https://x/donate")
        self.assertEqual(result["subject"], "Hello")
        html = result["html"]
        self.assertIn(LOGO_URL, html)              # deterministic chrome
        self.assertIn("/heroes/rec1.jpg", html)    # lead hero = first story
        self.assertIn("Dear Masi Friends", html)   # model body preserved
        self.assertIn("Give Now", html)            # CTA text
        self.assertIn("https://x/donate", html)


class DraftNewsletterCtaTests(TestCase):
    @mock.patch("fundraising.management.commands.draft_newsletter.compose_newsletter",
                return_value={"subject": "S", "html": "<p>body</p>"})
    def test_cta_args_are_passed_to_compose(self, m_compose):
        from django.core.management import call_command
        from fundraising.models import ContentStory
        ContentStory.objects.create(source_airtable_id="recD1", title="t",
                                    narrative="n", is_active=True)
        call_command("draft_newsletter", "--count", "1", "--n", "1", "--dry-run",
                     "--cta-text", "Holiday Match", "--cta-url", "https://x/give")
        _args, kwargs = m_compose.call_args
        self.assertEqual(kwargs.get("cta_text"), "Holiday Match")
        self.assertEqual(kwargs.get("cta_url"), "https://x/give")
