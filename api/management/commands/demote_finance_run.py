"""Restore only the recorded predecessor using the shared approval guards."""
from uuid import UUID
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from api.services.finance_runs import FinanceRunError, demote_run


class Command(BaseCommand):
    help = 'Demote the current finance run by approving its recorded predecessor.'

    def add_arguments(self, parser):
        parser.add_argument('--run-id', required=True)
        parser.add_argument('--actor-user-id', type=int, required=True)
        parser.add_argument('--note', required=True)
        parser.add_argument('--override-anti-rollback', action='store_true')
        parser.add_argument('--acknowledge-findings', action='store_true')

    def handle(self, *args, **options):
        try:
            run_id = UUID(options['run_id'])
            actor = get_user_model().objects.get(pk=options['actor_user_id'], is_active=True)
            restored = demote_run(run_id, actor, note=options['note'],
                                 override_anti_rollback=options['override_anti_rollback'],
                                 acknowledge_findings=options['acknowledge_findings'])
        except get_user_model().DoesNotExist:
            raise CommandError('An active publisher actor is required.') from None
        except FinanceRunError as exc:
            raise CommandError(exc.code) from None
        except ValueError:
            raise CommandError('Invalid run ID.') from None
        self.stdout.write(f'approved_run_id={restored.pk} status={restored.status}')
