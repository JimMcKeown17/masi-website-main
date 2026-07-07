import os

import requests
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date
from dotenv import load_dotenv

from api.models import AirtableSyncLog
from fundraising.models import ContentStory


class Command(BaseCommand):
    """
    Sync Airtable Success Stories into the fundraising content mirror.

    Grain: one Airtable record = one ContentStory row.
    Upsert key: source_airtable_id.
    """
    help = "Sync Airtable Success Stories into fundraising ContentStory"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Preview without saving')
        parser.add_argument('--verbose', action='store_true', help='Show first few records fetched')

    def handle(self, *args, **options):
        load_dotenv()
        base_id = os.getenv("AIRTABLE_MARKETING_BASE_ID")
        table_id = os.getenv("AIRTABLE_SUCCESS_STORIES_TABLE_ID")
        token = os.getenv("AIRTABLE_TOKEN") or os.getenv("AIRTABLE_API_KEY")
        is_dry_run = options['dry_run']

        if not all([base_id, table_id, token]):
            self.stdout.write(self.style.ERROR(
                "Missing env vars. Required:\n"
                f"  AIRTABLE_MARKETING_BASE_ID: {bool(base_id)}\n"
                f"  AIRTABLE_SUCCESS_STORIES_TABLE_ID: {bool(table_id)}\n"
                f"  AIRTABLE_TOKEN or AIRTABLE_API_KEY: {bool(token)}"
            ))
            return

        if is_dry_run:
            self.stdout.write(self.style.WARNING("=== DRY RUN MODE - no changes will be saved ===\n"))

        sync_log = None
        if not is_dry_run:
            sync_log = AirtableSyncLog.objects.create(sync_type='success_stories')
            self.stdout.write(f"Sync log started (ID: {sync_log.id})")

        try:
            records = self.fetch_from_airtable(base_id, table_id, token)
            self.stdout.write(self.style.SUCCESS(f"Fetched {len(records)} records from Airtable"))

            if options['verbose']:
                for record in records[:3]:
                    fields = record.get('fields', {})
                    consent_count = len(fields.get("Child's Consent Form", []))
                    self.stdout.write(
                        f"  Sample: {record.get('id')} | "
                        f"{fields.get('Title', '')} | "
                        f"{fields.get('Date Published', '')} | "
                        f"consent={consent_count > 0}"
                    )

            if is_dry_run:
                self.stdout.write(f"DRY RUN: would process {len(records)} records")
                self.stdout.write(f"Current ContentStory count in DB: {ContentStory.objects.count()}")
                return

            stats = self.bulk_upsert(records)

            if sync_log:
                sync_log.records_processed = len(records)
                sync_log.records_created = stats['created']
                sync_log.records_updated = stats['updated']
                sync_log.records_skipped = stats['skipped']
                sync_log.mark_complete(success=True)

            self.stdout.write(self.style.SUCCESS(
                f"\nSync complete - "
                f"Airtable records: {len(records)}, "
                f"created: {stats['created']}, "
                f"updated: {stats['updated']}, "
                f"skipped: {stats['skipped']}"
            ))

        except Exception as exc:
            if sync_log:
                try:
                    sync_log.mark_complete(success=False, error_message=str(exc))
                except Exception:
                    pass
            self.stdout.write(self.style.ERROR(f"Sync failed: {exc}"))
            raise

    def bulk_upsert(self, records):
        existing = {
            row['source_airtable_id']: row['id']
            for row in ContentStory.objects.values('id', 'source_airtable_id')
        }

        now = timezone.now()
        new_objs = []
        update_objs = []
        skipped = 0

        for record in records:
            if not record.get('id'):
                skipped += 1
                continue

            row_data = self.extract_row(record)
            airtable_id = row_data.get('source_airtable_id')
            if not airtable_id:
                skipped += 1
                continue

            row_data['last_seen_at'] = now
            row_data['is_active'] = True

            if airtable_id in existing:
                obj = ContentStory(id=existing[airtable_id], **row_data)
                obj.updated_at = now
                update_objs.append(obj)
            else:
                new_objs.append(ContentStory(**row_data))

        update_fields = [
            'feature_name',
            'title',
            'headline',
            'narrative',
            'quote',
            'stats_text',
            'category',
            'school',
            'date_published',
            'photo_urls',
            'has_consent',
            'drive_link',
            'social_published',
            'is_active',
            'last_seen_at',
            'updated_at',
        ]

        with transaction.atomic():
            if new_objs:
                ContentStory.objects.bulk_create(new_objs, batch_size=500)
            if update_objs:
                ContentStory.objects.bulk_update(update_objs, update_fields, batch_size=500)

        return {'created': len(new_objs), 'updated': len(update_objs), 'skipped': skipped}

    def extract_row(self, record):
        fields = record.get('fields', {})

        def text(name):
            return fields.get(name, "") or ""

        attachments = fields.get('Attachments', []) or []
        consent_attachments = fields.get("Child's Consent Form", []) or []

        return {
            'source_airtable_id': record.get('id', ''),
            'feature_name': text('Full Name of Feature'),
            'title': text('Title'),
            'headline': text('Headline'),
            'narrative': text('Story Descriptive / Narrative'),
            'quote': text('Quote'),
            'stats_text': text('Stats'),
            'category': fields.get('Category'),
            'school': fields.get("Child's School"),
            'date_published': parse_date(text('Date Published')),
            'photo_urls': [
                {
                    'url': attachment['url'],
                    'filename': attachment.get('filename', ''),
                }
                for attachment in attachments
                if attachment.get('url')
            ],
            'has_consent': len(consent_attachments) > 0,
            'drive_link': text('Google Drive Link'),
            'social_published': text('Social Media Published'),
        }

    def fetch_from_airtable(self, base_id, table_id, token):
        url = f"https://api.airtable.com/v0/{base_id}/{table_id}"
        headers = {"Authorization": f"Bearer {token}"}
        params = {}
        records = []

        while True:
            response = requests.get(url, headers=headers, params=params, timeout=30)
            if response.status_code != 200:
                raise ValueError(f"Airtable API error {response.status_code}: {response.text[:200]}")
            data = response.json()
            records.extend(data.get('records', []))
            offset = data.get('offset')
            if not offset:
                break
            params = {'offset': offset}

        return records
