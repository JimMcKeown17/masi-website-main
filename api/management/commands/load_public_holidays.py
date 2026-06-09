"""Materialise South African public holidays as global SchoolClosure rows.

Public holidays are stored as ordinary ``scope_key='global'`` closures
(``source='public_holiday'``) so they flow through the same resolver, exports,
and Zazi cache as any other closure, and can be overridden per school by a
more-specific ``is_open=True`` row.

Usage:  python manage.py load_public_holidays --year 2026

Idempotent: existing public-holiday rows are refreshed in place; manual closures
on the same date are left untouched.
"""
import holidays

from django.core.management.base import BaseCommand

from api.models import SchoolClosure


class Command(BaseCommand):
    help = "Load ZA public holidays for a year as global SchoolClosure rows."

    def add_arguments(self, parser):
        parser.add_argument('--year', type=int, required=True,
                            help='Calendar year, e.g. 2026')

    def handle(self, *args, **options):
        year = options['year']
        za = holidays.country_holidays('ZA', years=[year])
        created = updated = 0
        for day, name in sorted(za.items()):
            obj, was_created = SchoolClosure.objects.get_or_create(
                date=day, scope_key='global',
                defaults={
                    'scope_type': 'global',
                    'is_open': False,
                    'source': 'public_holiday',
                    'reason': name,
                },
            )
            if was_created:
                created += 1
            elif obj.source == 'public_holiday' and obj.reason != name:
                obj.reason = name
                obj.save(update_fields=['reason'])
                updated += 1
        self.stdout.write(self.style.SUCCESS(
            f"{year}: {created} created, {updated} updated "
            f"({len(za)} ZA public holidays total)"
        ))
