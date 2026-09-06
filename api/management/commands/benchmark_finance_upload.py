"""Measure the actual upload service, including transactional facts insertion."""
import json
from pathlib import Path
import resource
import sys
import tracemalloc
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from api.parsers.finance_workbook import MIME
from api.services.finance_runs import FinanceRunError, require_publisher, upload_workbook


class Command(BaseCommand):
    help = 'Benchmark a finance workbook through the full upload service (writes a run).'

    def add_arguments(self, parser):
        parser.add_argument('path')
        parser.add_argument('--actor-user-id', type=int, required=True)
        parser.add_argument('--year', type=int, required=True)
        parser.add_argument('--trace-allocations', action='store_true',
                            help='Measure scoped Python allocations separately; adds substantial overhead.')

    def handle(self, *args, **options):
        try:
            actor = get_user_model().objects.get(pk=options['actor_user_id'], is_active=True)
            require_publisher(actor)
        except (get_user_model().DoesNotExist, FinanceRunError):
            raise CommandError('PUBLISH_FORBIDDEN') from None
        path = Path(options['path'])
        trace = options['trace_allocations']
        if trace and tracemalloc.is_tracing():
            raise CommandError('ALLOCATION_TRACING_ALREADY_ACTIVE')
        python_peak = None
        if trace:
            tracemalloc.start()
        try:
            with path.open('rb') as stream:
                run, status = upload_workbook(stream, actor, kind='funders', year=options['year'],
                                              source_name=path.name, content_type=MIME)
        except FinanceRunError as error:
            raise CommandError(error.code) from None
        except OSError:
            raise CommandError('WORKBOOK_READ_FAILED') from None
        finally:
            if trace:
                python_peak = tracemalloc.get_traced_memory()[1]
                tracemalloc.stop()
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        record = dict(basename=run.source_name, bytes=run.source_size_bytes, sha256=run.source_sha256,
                      producer_version=run.producer_version, producer_tag='v' + run.producer_version,
                      schema=run.schema_version, run_id=str(run.pk), status=run.status,
                      service_status=status, parse_duration_ms=run.parse_duration_ms,
                      total_duration_ms=run.total_duration_ms, peak_memory_bytes=run.peak_memory_bytes,
                      process_peak_rss_bytes=int(rss if sys.platform == 'darwin' else rss * 1024),
                      row_count=run.fact_row_count, allocation_count=run.allocation_count,
                      database_engine=connection.settings_dict['ENGINE'],
                      measurement='idempotent_replay' if status == 200 else 'new_run')
        record['memory_measurement'] = 'sampled_process_rss_10ms_or_resource_high_water'
        if trace:
            record['python_peak_allocation_bytes'] = python_peak
        self.stdout.write(json.dumps(record, sort_keys=True))
