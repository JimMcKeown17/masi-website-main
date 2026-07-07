import os

from django.core.management.base import BaseCommand, CommandError
from django.db.models import F
from dotenv import load_dotenv

from api.models import PublishedStat
from fundraising.models import ContentStory, Draft
from fundraising.services import mailchimp
from fundraising.services.compose import compose_newsletter, voice_guide


class Command(BaseCommand):
    help = "Compose donor newsletter drafts from consented stories and create Mailchimp draft campaigns"

    def add_arguments(self, parser):
        parser.add_argument('--count', type=int, default=3, help='Number of stories per draft')
        parser.add_argument('--stat-key', help='PublishedStat key to include')
        parser.add_argument('--dry-run', action='store_true', help='Create Draft rows but skip Mailchimp')
        parser.add_argument('--n', type=int, default=1, help='Number of drafts to create')

    def handle(self, *args, **options):
        load_dotenv()
        count = options['count']
        draft_count = options['n']
        is_dry_run = options['dry_run']

        if count < 1:
            raise CommandError("--count must be at least 1")
        if draft_count < 1:
            raise CommandError("--n must be at least 1")

        if is_dry_run:
            self.stdout.write(self.style.WARNING(
                "=== DRY RUN MODE - Draft rows will be created, Mailchimp will be skipped ==="
            ))

        story_limit = count * draft_count
        # Consent gate removed 2026-07-07 (Jim): consent forms aren't tracked in this
        # table yet, so assume consent for all children/youth and revisit later.
        # Only stories with real narrative content; nulls_last keeps undated stubs from winning.
        story_pool = list(
            ContentStory.objects
            .filter(is_active=True)
            .exclude(narrative='')
            .order_by(F('date_published').desc(nulls_last=True), '-id')[:story_limit]
        )
        if not story_pool:
            raise CommandError("No active ContentStory rows with narrative available for newsletter drafting.")

        story_windows = [
            story_pool[index * count:(index + 1) * count]
            for index in range(draft_count)
        ]
        empty_window = next((index for index, window in enumerate(story_windows, start=1) if not window), None)
        if empty_window:
            raise CommandError(
                f"No active ContentStory rows available for newsletter draft window {empty_window}."
            )

        stat = self.select_stat(options.get('stat_key'))
        guide_text = voice_guide.read()

        for index, stories in enumerate(story_windows, start=1):
            result = compose_newsletter(stories, stat, guide_text)
            subject = result['subject']
            html = result['html']
            draft = Draft.objects.create(
                kind='newsletter_broadcast',
                status='draft',
                created_by_agent='newsletter_assembler',
                subject=subject,
                draft_body=html,
            )

            if is_dry_run:
                self.stdout.write(self.style.SUCCESS(
                    f"Draft {index}/{draft_count}: created Draft id {draft.id}; skipped Mailchimp"
                ))
                continue

            audience_id = os.getenv('MAILCHIMP_AUDIENCE_ID_ALL_DONORS')
            try:
                campaign = mailchimp.create_draft_campaign(
                    subject,
                    html,
                    audience_id,
                    title=f"[AI draft] {subject}",
                )
            except Exception as exc:
                raise CommandError(f"Mailchimp draft creation failed for Draft {draft.id}: {exc}")

            draft.external_ref = campaign['campaign_id']
            draft.save(update_fields=['external_ref', 'updated_at'])

            self.stdout.write(self.style.SUCCESS(
                f"Draft {index}/{draft_count}: Draft id {draft.id}; Mailchimp edit_url: {campaign['edit_url']}"
            ))

    def select_stat(self, stat_key):
        qs = PublishedStat.objects.filter(is_published=True)
        if stat_key:
            stat = qs.filter(key=stat_key).first()
            if not stat:
                self.stdout.write(self.style.WARNING(
                    f"No published PublishedStat found for --stat-key={stat_key}; composing without a stat."
                ))
            return stat
        return qs.order_by('sort_order', 'id').first()
