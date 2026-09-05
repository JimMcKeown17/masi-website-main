"""Synthetic fixtures shared by the finance foundation tests."""
import json
from copy import deepcopy
from datetime import date
from pathlib import Path
from django.contrib.auth.models import User
from masi_finance.publish.run_artifact import payload_digest, facts_digest


def actor(name='publisher', role='ADMIN'):
    user = User.objects.create_user(username=name)
    user.profile.role = role
    user.profile.save()
    return user


def golden():
    return json.loads((Path(__file__).parent / 'tests_data/finance-run-2.0.0.json').read_text())


def candidate(user, *, sha=None, source_date=None, year=None, artifact=None, facts=True):
    from api.models import FinanceRun
    from api.services.finance_runs import materialise_facts
    a = deepcopy(artifact or golden())
    source = a['manifest']['source']
    if sha:
        source['sha256'] = sha
    if source_date:
        source['date'] = source_date
        source['name'] = source_date.replace('-', '') + ' - Fixture.xlsx'
    if year:
        a['manifest']['accounting_year'] = year
    findings = a['derived']['findings']
    run = FinanceRun.objects.create(
        kind='funders', accounting_year=a['manifest']['accounting_year'], status='candidate',
        source_name=source['name'], source_date=date.fromisoformat(source['date']),
        source_sha256=source['sha256'], source_size_bytes=source['size_bytes'],
        schema_version='2.0.0', producer_version='0.2.0', manifest=a['manifest'],
        payload=a['derived'], payload_sha256=payload_digest(a), facts_sha256=facts_digest(a['ledger']),
        uploaded_by=user, fact_row_count=len(a['ledger']['rows']), allocation_count=len(a['ledger']['allocations']),
        finding_count=len(findings), in_scope_error_count=sum(f['severity']=='error' and f['in_scope_year'] for f in findings),
    )
    if facts:
        materialise_facts(run, a)
    return run


def approve(run, user, **kwargs):
    from api.services.finance_runs import approve_run
    return approve_run(run.pk, user, acknowledge_findings=True, note='Reviewed synthetic findings', **kwargs)


def legacy(year=2026):
    from api.models import FinanceSnapshot
    from api.tests_finance_snapshot import fixture
    from api.finance_snapshot import parse_timestamp, payload_digest
    p = fixture()
    p['accounting_year'] = year
    p['payload_sha256'] = payload_digest(p)
    s = p['source']
    return FinanceSnapshot.objects.create(accounting_year=year, schema_version='1.0.0', run_id=p['run_id'],
        workbook_name=s['workbook_name'], workbook_date=s['workbook_date'],
        workbook_modified_at=parse_timestamp(s['modified_at']), workbook_sha256=s['sha256'],
        payload_sha256=p['payload_sha256'], published_at=parse_timestamp(p['published_at']), payload=p)
