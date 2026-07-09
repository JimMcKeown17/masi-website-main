from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from dotenv import load_dotenv

from fundraising.models import DRAFT_KIND_CHOICES
from fundraising.services.record import record_and_draft


class Command(BaseCommand):
    help = "Record composed HTML as a Draft and optionally create a Mailchimp campaign"

    def add_arguments(self, parser):
        parser.add_argument('--subject', required=True)
        parser.add_argument('--body-file', required=True, help='Path to full composed HTML')
        parser.add_argument(
            '--kind',
            default='newsletter_broadcast',
            choices=[value for value, _label in DRAFT_KIND_CHOICES],
        )
        parser.add_argument('--shell', default='studio')
        parser.add_argument('--source-type', default='')
        parser.add_argument('--story-ids', nargs='*', type=int, default=[])
        parser.add_argument('--title')
        parser.add_argument('--audience-id')
        parser.add_argument('--no-mailchimp', action='store_true')

    def handle(self, *args, **options):
        load_dotenv()
        try:
            html = Path(options['body_file']).read_text(encoding='utf-8')
        except OSError as exc:
            raise CommandError(f"Could not read --body-file: {exc}") from exc

        try:
            result = record_and_draft(
                options['subject'],
                html,
                kind=options['kind'],
                shell=options['shell'],
                source_type=options['source_type'],
                story_ids=options['story_ids'],
                title=options.get('title'),
                create_mailchimp=not options['no_mailchimp'],
                audience_id=options.get('audience_id'),
            )
        except Exception as exc:
            raise CommandError(f"Draft creation failed: {exc}") from exc

        draft = result['draft']
        self.stdout.write(self.style.SUCCESS(f"Draft id {draft.id}"))
        if result['campaign']:
            self.stdout.write(self.style.SUCCESS(
                f"Mailchimp edit_url: {result['campaign']['edit_url']}"
            ))
