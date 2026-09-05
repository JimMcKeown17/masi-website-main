"""Retired writer. Legacy table writes no longer affect finance serving."""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'retired; use the Upload page'
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument('path', nargs='?')
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--force', action='store_true')

    def handle(self, *args, **options):
        raise CommandError('load_finance_snapshot is retired; use the Upload page')
