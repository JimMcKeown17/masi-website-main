"""Checked finance transitions and fact persistence, shared by HTTP and commands.

PostgreSQL tuple locks also serialize creation when no row exists. SQLite supports
functional tests only; it makes no concurrency guarantee for these services.
"""
from copy import deepcopy
from datetime import date
import hashlib
from time import perf_counter

import jsonschema
from django.db import connection, transaction
from django.utils import timezone
from masi_finance.publish.invariants import assert_invariants, payload_digest as flat_digest
from masi_finance.publish.run_artifact import validate_facts
from masi_finance.publish.run_schema import load_schema, FORMAT_CHECKER

from api.finance_snapshot import parse_timestamp
from api.models import FinanceRun, FinanceSnapshot, LedgerRow, LedgerAllocation
from api.permissions import finance_capabilities_for

# Cumulative stored-version support, independent of future upload pins.
SUPPORTED_PAIRS = {('2.0.0', '0.2.0'): '2.0.0', ('1.0.0', None): '1.0.0'}
ROW_FIELDS = ('row_key', 'sheet_row', 'date', 'year', 'description', 'paid_by',
              'category_1', 'category_2', 'category_3', 'bc', 'amount', 'coverage_amount')
ALLOCATION_FIELDS = ('ordinal', 'amount_column_letter', 'key_column_letter', 'key_value',
                     'contract_code', 'budget_line_id', 'amount')


class FinanceRunError(ValueError):
    """Stable safe code; never echo validation diagnostics containing finance data."""

    def __init__(self, code, *, status=409):
        self.code = code
        self.status = status
        super().__init__(code)


def require_publisher(actor):
    if 'finance.publish' not in finance_capabilities_for(actor):
        raise FinanceRunError('PUBLISH_FORBIDDEN', status=403)


def acquire_tuple_lock(kind, year):
    if not connection.in_atomic_block:
        raise RuntimeError('Finance tuple locks require transaction.atomic().')
    if connection.vendor == 'sqlite':
        return
    if connection.vendor != 'postgresql':
        raise FinanceRunError('DATABASE_UNSUPPORTED')
    key = int.from_bytes(hashlib.sha256(f'masi.finance.run:{kind}:{year}'.encode()).digest()[:8], 'big', signed=True)
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_try_advisory_xact_lock(%s)', [key])
        if not cursor.fetchone()[0]:
            raise FinanceRunError('UPLOAD_IN_PROGRESS')


def _transition_checkpoint(stage):
    """Failure-injection seam at transaction boundaries (no production side effects)."""


def _require(condition, code='RUN_INTEGRITY_INVALID'):
    if not condition:
        raise FinanceRunError(code)


def _validate_schema(document, name, *, producer_version=None):
    schema = load_schema(name)
    if producer_version is not None:
        # Caller has checked the cumulative pair registry. Reuse this schema shape
        # for explicitly registered compatible producers, never the upload pin.
        schema['properties']['manifest']['properties']['producer']['properties']['version']['const'] = producer_version
    validator = jsonschema.Draft202012Validator(schema, format_checker=FORMAT_CHECKER)
    _require(next(validator.iter_errors(document), None) is None, 'SCHEMA_INVALID')


def _source_matches(run):
    source = run.manifest['source']
    return (source['name'] == run.source_name and source['date'] == run.source_date.isoformat()
            and source['sha256'] == run.source_sha256 and source['size_bytes'] == run.source_size_bytes
            and run.manifest['accounting_year'] == run.accounting_year
            and run.manifest['producer'] == {'name': 'masi-finance', 'version': run.producer_version})


def _finding_counts(payload):
    findings = payload['findings']
    return len(findings), sum(f['severity'] == 'error' and f['in_scope_year'] for f in findings)


def _validate_artifact(run, artifact):
    _require((run.schema_version, run.producer_version) in SUPPORTED_PAIRS, 'UNSUPPORTED_VERSION')
    _require(run.schema_version == '2.0.0' and artifact['schema_version'] == run.schema_version)
    _validate_schema(artifact, f'finance-run-{SUPPORTED_PAIRS[(run.schema_version, run.producer_version)]}.json', producer_version=run.producer_version)
    _require(artifact['manifest'] == run.manifest and artifact['derived'] == run.payload)
    _require(_source_matches(run))
    _validate_source_name(run.source_name, run.source_date)
    _require((len(artifact['ledger']['rows']), len(artifact['ledger']['allocations'])) == (run.fact_row_count, run.allocation_count), 'FACT_COUNTS_INVALID')
    _require(_finding_counts(run.payload) == (run.finding_count, run.in_scope_error_count), 'FINDING_COUNTS_INVALID')
    validate_facts(artifact, expected_payload_sha256=run.payload_sha256, expected_facts_sha256=run.facts_sha256)
    figures = dict(run.payload)
    figures['payload_sha256'] = flat_digest(figures)
    assert_invariants(figures)


def reconstruct_ledger(run):
    rows = list(run.ledger_rows.order_by('sheet_row').values(*ROW_FIELDS))
    for row in rows:
        row['date'] = row['date'].isoformat()
        for field in ('amount', 'coverage_amount'):
            row[field] = format(row[field], '.2f')
    allocations = list(LedgerAllocation.objects.filter(ledger_row__run=run)
                       .order_by('ledger_row__sheet_row', 'ordinal')
                       .values('ledger_row__row_key', *ALLOCATION_FIELDS))
    for allocation in allocations:
        allocation['row_key'] = allocation.pop('ledger_row__row_key')
        allocation['amount'] = format(allocation['amount'], '.2f')
    return {'rows': rows, 'allocations': allocations}


@transaction.atomic
def materialise_facts(run, artifact):
    _require(run.status == 'candidate' and run.schema_version == '2.0.0', 'FACTS_NOT_ALLOWED')
    _require(not run.ledger_rows.exists(), 'FACTS_ALREADY_EXIST')
    try:
        _validate_artifact(run, artifact)
        rows = LedgerRow.objects.bulk_create([LedgerRow(run=run, **row) for row in artifact['ledger']['rows']])
        by_key = {row.row_key: row for row in rows}
        LedgerAllocation.objects.bulk_create([
            LedgerAllocation(ledger_row=by_key[a['row_key']], **{k: a[k] for k in ALLOCATION_FIELDS})
            for a in artifact['ledger']['allocations']
        ])
        # Validate the persisted representation, including Decimal/date round trips.
        _validate_artifact(run, {**artifact, 'ledger': reconstruct_ledger(run)})
    except (ValueError, KeyError, TypeError) as exc:
        if isinstance(exc, FinanceRunError):
            raise
        raise FinanceRunError('FACTS_INVALID') from None


def _validate_source_name(name, source_date):
    _require(isinstance(name, str) and '/' not in name and '\\' not in name, 'SOURCE_INVALID')
    _require(len(name) >= 8 and name[:8] == source_date.strftime('%Y%m%d'), 'SOURCE_INVALID')


def _validate_legacy_payload(payload):
    _validate_schema(payload, 'finance-snapshot-1.0.0.json')
    assert_invariants(payload)
    _validate_source_name(payload['source']['workbook_name'], date.fromisoformat(payload['source']['workbook_date']))
    parse_timestamp(payload['published_at'])
    parse_timestamp(payload['source']['modified_at'])


def validate_stored_run(run):
    try:
        _require((run.schema_version, run.producer_version) in SUPPORTED_PAIRS, 'UNSUPPORTED_VERSION')
        _require(run.failure is None and _source_matches(run))
        if run.schema_version == '2.0.0':
            _validate_artifact(run, {'schema_version': run.schema_version, 'manifest': run.manifest,
                                     'derived': run.payload, 'ledger': reconstruct_ledger(run)})
        else:
            _require(run.status in ('approved', 'superseded'))
            _validate_legacy_payload(run.payload)
            source = run.payload['source']
            provenance = run.manifest['import']
            _require(run.payload_sha256 == run.payload['payload_sha256'] and run.facts_sha256 is None)
            _require(run.fact_row_count == run.allocation_count == 0 and not run.ledger_rows.exists())
            _require(run.payload['accounting_year'] == run.accounting_year
                     and source == {'workbook_name': run.source_name, 'workbook_date': run.source_date.isoformat(),
                                    'sha256': run.source_sha256, 'size_bytes': run.source_size_bytes,
                                    'modified_at': provenance['workbook_modified_at']}
                     and run.payload['run_id'] == provenance['legacy_run_id']
                     and run.payload['published_at'] == provenance['published_at'])
            _require(_finding_counts(run.payload) == (run.finding_count, run.in_scope_error_count))
    except (ValueError, KeyError, TypeError) as exc:
        if isinstance(exc, FinanceRunError):
            raise
        raise FinanceRunError('RUN_INTEGRITY_INVALID') from None


def _chain(start, rows):
    ids = set()
    node = start
    while node is not None:
        _require(node.pk not in ids, 'INVALID_PREDECESSOR_CHAIN')
        ids.add(node.pk)
        if node.previous_approved_id is None:
            break
        predecessor = rows.get(node.previous_approved_id)
        _require(predecessor is not None and predecessor.approved_at is not None
                 and predecessor.approved_by_id is not None
                 and predecessor.status in ('approved', 'superseded'), 'INVALID_PREDECESSOR_CHAIN')
        node = predecessor
    return ids


def _lock_transition(run_id):
    try:
        reference = FinanceRun.objects.only('kind', 'accounting_year').get(pk=run_id)
    except (FinanceRun.DoesNotExist, ValueError):
        raise FinanceRunError('RUN_NOT_FOUND', status=404) from None
    acquire_tuple_lock(reference.kind, reference.accounting_year)
    rows = {run.pk: run for run in FinanceRun.objects.select_for_update()
            .filter(kind=reference.kind, accounting_year=reference.accounting_year).order_by('pk')}
    _transition_checkpoint('after_lock')
    target = rows.get(reference.pk)
    _require(target is not None, 'RUN_NOT_FOUND')
    current = next((run for run in rows.values() if run.status == 'approved'), None)
    _chain(target, rows)
    if current:
        _chain(current, rows)
    return target, current, rows


def _check_options(override_anti_rollback, acknowledge_findings, note):
    _require(type(override_anti_rollback) is bool and type(acknowledge_findings) is bool
             and isinstance(note, str), 'INVALID_OPTIONS')
    if override_anti_rollback or acknowledge_findings:
        _require(bool(note.strip()), 'NOTE_REQUIRED')


def _approve_locked(target, current, rows, actor, *, override_anti_rollback, acknowledge_findings, note):
    _check_options(override_anti_rollback, acknowledge_findings, note)
    _require(target.status == 'candidate' or (target.status == 'superseded' and target.approved_by_id and target.approved_at), 'INVALID_TRANSITION')
    validate_stored_run(target)
    if current:
        same_date = target.source_date == current.source_date
        same_sha = target.source_sha256 == current.source_sha256
        rollback = (target.source_date < current.source_date
                    or (same_date and not same_sha)
                    or (same_date and same_sha and target.schema_version.split('.')[0] == current.schema_version.split('.')[0]
                        and target.payload_sha256 != current.payload_sha256))
        _require(not rollback or override_anti_rollback, 'ANTI_ROLLBACK')
    _require(not target.in_scope_error_count or acknowledge_findings, 'FINDINGS_ACKNOWLEDGEMENT_REQUIRED')
    if current and target.pk not in _chain(current, rows):
        target.previous_approved = current
    _chain(target, rows)
    if current:
        current.status = 'superseded'
        current.save(update_fields=['status'])
    _transition_checkpoint('after_supersede')
    target.status = 'approved'
    target.approved_by = actor
    target.approved_at = timezone.now()
    target.approval_overrode_rollback = override_anti_rollback
    target.approval_acknowledged_findings = acknowledge_findings
    target.approval_note = note.strip()
    _transition_checkpoint('before_promote')
    target.save(update_fields=['status', 'previous_approved', 'approved_by', 'approved_at',
                               'approval_overrode_rollback', 'approval_acknowledged_findings', 'approval_note'])
    return target


@transaction.atomic
def approve_run(run_id, actor, *, override_anti_rollback=False, acknowledge_findings=False, note=''):
    require_publisher(actor)
    target, current, rows = _lock_transition(run_id)
    return _approve_locked(target, current, rows, actor, override_anti_rollback=override_anti_rollback,
                           acknowledge_findings=acknowledge_findings, note=note)


@transaction.atomic
def demote_run(run_id, actor, *, override_anti_rollback=False, acknowledge_findings=False, note=''):
    require_publisher(actor)
    _require(isinstance(note, str) and bool(note.strip()), 'NOTE_REQUIRED')
    target, current, rows = _lock_transition(run_id)
    _require(current is not None and current.pk == target.pk and target.previous_approved_id is not None, 'INVALID_TRANSITION')
    restored = _approve_locked(rows[target.previous_approved_id], current, rows, actor,
                               override_anti_rollback=override_anti_rollback,
                               acknowledge_findings=acknowledge_findings, note=note)
    target.demoted_by = actor
    target.demoted_at = timezone.now()
    target.demotion_note = note.strip()
    target.save(update_fields=['demoted_by', 'demoted_at', 'demotion_note'])
    return restored


@transaction.atomic
def import_legacy_snapshots(actor, *, year=None, legacy_row_id=None, note='Legacy snapshot import', apply=True):
    """Import or replay one exact identity; replay never reads FinanceSnapshot."""
    require_publisher(actor)
    _require(isinstance(note, str) and bool(note.strip()), 'NOTE_REQUIRED')
    _require(type(year) is int and 2000 <= year <= 2100 and type(legacy_row_id) is int and legacy_row_id > 0, 'IMPORT_TARGET_INVALID')
    started = perf_counter()
    acquire_tuple_lock('funders', year)
    existing = FinanceRun.objects.filter(manifest__import__legacy_row_id=legacy_row_id).first()
    if existing:
        _require(existing.kind == 'funders' and existing.accounting_year == year, 'IMPORT_TARGET_MISMATCH')
        return [existing]
    _require(not FinanceRun.objects.filter(kind='funders', accounting_year=year).exists(), 'RUN_EXISTS')
    try:
        row = FinanceSnapshot.objects.select_for_update().get(pk=legacy_row_id, accounting_year=year)
    except FinanceSnapshot.DoesNotExist:
        raise FinanceRunError('LEGACY_ROW_NOT_FOUND', status=404) from None
    try:
        payload = deepcopy(row.payload)
        _validate_legacy_payload(payload)
        source = payload['source']
        _require(row.schema_version == payload['schema_version'] == '1.0.0'
                 and row.accounting_year == payload['accounting_year']
                 and row.run_id == payload['run_id'] and row.payload_sha256 == payload['payload_sha256']
                 and row.workbook_name == source['workbook_name']
                 and row.workbook_date.isoformat() == source['workbook_date']
                 and row.workbook_sha256 == source['sha256']
                 and row.workbook_modified_at == parse_timestamp(source['modified_at'])
                 and row.published_at == parse_timestamp(payload['published_at']), 'LEGACY_PROVENANCE_INVALID')
    except (ValueError, KeyError, TypeError) as exc:
        if isinstance(exc, FinanceRunError):
            raise
        raise FinanceRunError('LEGACY_INVALID') from None
    now = timezone.now()
    finding_count, error_count = _finding_counts(payload)
    fields = dict(kind='funders', accounting_year=year, status='approved', source_name=row.workbook_name,
                  source_date=row.workbook_date, source_sha256=row.workbook_sha256, source_size_bytes=source['size_bytes'],
                  schema_version='1.0.0', producer_version=None, payload_sha256=row.payload_sha256,
                  payload=payload, uploaded_by=actor, uploaded_at=now, approved_by=actor, approved_at=now,
                  approval_note=note.strip(), finding_count=finding_count, in_scope_error_count=error_count,
                  total_duration_ms=int((perf_counter() - started) * 1000),
                  manifest={'producer': {'name': 'masi-finance', 'version': None},
                            'source': {'name': row.workbook_name, 'date': source['workbook_date'], 'sha256': row.workbook_sha256,
                                       'size_bytes': source['size_bytes'], 'client_modified_at': None},
                            'accounting_year': year, 'rule_config_sha256': None, 'dependencies': [],
                            'import': {'legacy_row_id': row.pk, 'legacy_run_id': row.run_id,
                                       'published_at': payload['published_at'], 'loaded_at': row.loaded_at.isoformat(),
                                       'workbook_modified_at': source['modified_at'], 'actor_user_id': actor.pk,
                                       'imported_at': now.isoformat()}})
    return [FinanceRun.objects.create(**fields) if apply else FinanceRun(**fields)]
