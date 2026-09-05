"""One-time exact-target legacy import; preview unless --apply is supplied."""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from api.services.finance_runs import FinanceRunError, import_legacy_snapshots


class Command(BaseCommand):
    help = 'Import an exact legacy finance snapshot as an immutable approved run.'

    def add_arguments(self, parser):
        parser.add_argument('--year', type=int, required=True)
        parser.add_argument('--legacy-row-id', type=int, required=True)
        parser.add_argument('--actor-user-id', type=int, required=True)
        parser.add_argument('--note', required=True)
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        try:
            actor = get_user_model().objects.get(pk=options['actor_user_id'], is_active=True)
            run = import_legacy_snapshots(actor, year=options['year'], legacy_row_id=options['legacy_row_id'],
                                         note=options['note'], apply=options['apply'])[0]
        except get_user_model().DoesNotExist:
            raise CommandError('An active publisher actor is required.') from None
        except FinanceRunError as exc:
            raise CommandError(exc.code) from None
        if not options['apply']:
            self.stdout.write(f'PREVIEW year={run.accounting_year} legacy_row_id={options["legacy_row_id"]}; no writes.')
        else:
            self.stdout.write(f'run_id={run.pk} status={run.status} year={run.accounting_year}')
