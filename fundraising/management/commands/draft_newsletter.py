from django.core.management.base import BaseCommand, CommandError
from django.db.models import F
from dotenv import load_dotenv

from api.models import PublishedStat
from fundraising.models import ContentStory, Draft
from fundraising.services import charts
from fundraising.services.compose import compose_newsletter, voice_guide
from fundraising.services.record import record_and_draft


CATEGORY_STAT_KEYS = {
    'early child': [
        'more_zero_letters', 'more_growth', 'ecd_masi_lcpm', 'hero_children', 'more_stories',
    ],
    'youth': ['hero_youth', 'grads_women', 'hero_children'],
    'top learner': ['grads_count', 'hero_children'],
}
FALLBACK_STAT_KEYS = ['hero_children', 'hero_schools', 'hero_youth']


def _normalize_category(category):
    if isinstance(category, list):
        category = ' '.join(str(value) for value in category if value)
    if not isinstance(category, str):
        return ''
    return category.strip().lower()


class Command(BaseCommand):
    help = "Compose donor newsletter drafts from consented stories and create Mailchimp draft campaigns"

    def add_arguments(self, parser):
        parser.add_argument('--count', type=int, default=1, help='Number of stories per draft')
        parser.add_argument('--stat-key', help='PublishedStat key to include')
        parser.add_argument('--dry-run', action='store_true', help='Create Draft rows but skip Mailchimp')
        parser.add_argument('--n', type=int, default=1, help='Number of drafts to create')
        parser.add_argument('--cta-text', help='Donate button text (defaults to "Donate")')
        parser.add_argument('--cta-url', help='Donate button URL (defaults to the donate page)')
        parser.add_argument('--no-chart', action='store_true', help='Do not include a curated chart')

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

        guide_text = voice_guide.read()

        for index, stories in enumerate(story_windows, start=1):
            stats = self.select_stats(options.get('stat_key'), stories)
            chart = None
            if not options.get('no_chart'):
                chart = charts.pick_chart(stories[0].category)
            result = compose_newsletter(
                stories, stats, guide_text,
                cta_text=options.get('cta_text'),
                cta_url=options.get('cta_url'),
                chart=chart,
            )
            subject = result['subject']
            html = result['html']
            try:
                recorded = record_and_draft(
                    subject,
                    html,
                    shell='cron',
                    source_type='airtable',
                    story_ids=[story.id for story in stories],
                    create_mailchimp=not is_dry_run,
                )
            except Exception as exc:
                raise CommandError(f"Mailchimp draft creation failed: {exc}") from exc

            draft = recorded['draft']

            if is_dry_run:
                self.stdout.write(self.style.SUCCESS(
                    f"Draft {index}/{draft_count}: created Draft id {draft.id}; skipped Mailchimp"
                ))
                continue

            campaign = recorded['campaign']

            self.stdout.write(self.style.SUCCESS(
                f"Draft {index}/{draft_count}: Draft id {draft.id}; Mailchimp edit_url: {campaign['edit_url']}"
            ))

    def select_stats(self, stat_key, stories):
        qs = PublishedStat.objects.filter(is_published=True)
        category = _normalize_category(stories[0].category) if stories else ''
        keys = next(
            (stat_keys for keyword, stat_keys in CATEGORY_STAT_KEYS.items() if keyword in category),
            FALLBACK_STAT_KEYS,
        )
        offset = Draft.objects.count() % len(keys)
        rotated_keys = keys[offset:] + keys[:offset]

        stats = []
        if stat_key:
            stat = qs.filter(key=stat_key).first()
            if not stat:
                self.stdout.write(self.style.WARNING(
                    f"No published PublishedStat found for --stat-key={stat_key}; composing without a stat."
                ))
            else:
                stats.append(stat)

        available = {
            stat.key: stat
            for stat in qs.filter(key__in=rotated_keys)
        }
        for key in rotated_keys:
            stat = available.get(key)
            if stat and stat not in stats:
                stats.append(stat)
            if len(stats) == 3:
                break
        return stats
