"""Project immutable runs into the existing dashboard snapshot contract."""
from copy import deepcopy
from datetime import datetime, timezone

import jsonschema
from masi_finance.publish.invariants import assert_invariants, payload_digest
from masi_finance.publish.run_schema import load_schema, FORMAT_CHECKER


def utc_seconds(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    return value.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def project_snapshot(run):
    if run.schema_version == '1.0.0':
        return deepcopy(run.payload)
    if run.schema_version != '2.0.0' or run.approved_at is None:
        raise ValueError('SNAPSHOT_VERSION_UNAVAILABLE')
    document = deepcopy(run.payload)
    contracts = document['funder_contracts']
    contract_ids = {c['id']: c['binding_digest'] for c in contracts}
    line_ids = {line['line_id']: f"{c['binding_digest']}-{line['sheet_row']}"
                for c in contracts for line in c['lines']}

    def remap(value):
        if isinstance(value, list):
            return [remap(item) for item in value]
        if not isinstance(value, dict):
            return value
        result = {}
        for key, item in value.items():
            if key == 'contract_id':
                result[key] = contract_ids.get(item)
            elif key == 'line_id':
                result[key] = line_ids.get(item)
            elif key == 'by_contract':
                result[key] = {contract_ids[k]: amount for k, amount in item.items()}
            else:
                result[key] = remap(item)
        return result

    document = remap(document)
    for contract in document['funder_contracts']:
        contract['id'] = contract_ids[contract['id']]
        for field in ('binding_digest', 'funder', 'start_date', 'end_date', 'description'):
            contract.pop(field)
    published = utc_seconds(run.approved_at)
    document.update(schema_version='1.1.0', accounting_year=run.accounting_year,
                    run_id=f'{published}-{run.source_sha256[:6]}', published_at=published,
                    source={'workbook_name': run.source_name, 'workbook_date': run.source_date.isoformat(),
                            'sha256': run.source_sha256, 'size_bytes': run.source_size_bytes,
                            'modified_at': utc_seconds(run.manifest['source']['client_modified_at'] or run.uploaded_at)})
    document['payload_sha256'] = payload_digest(document)
    validator = jsonschema.Draft202012Validator(load_schema('finance-snapshot-1.1.0.json'), format_checker=FORMAT_CHECKER)
    if next(validator.iter_errors(document), None) is not None:
        raise ValueError('SNAPSHOT_PROJECTION_INVALID')
    assert_invariants(document)
    return document


def snapshot_response(run, years):
    snapshot = project_snapshot(run)
    source = snapshot['source']
    loaded = (run.manifest['import']['loaded_at'] if run.schema_version == '1.0.0'
              else utc_seconds(run.approved_at))
    return {'accounting_year': run.accounting_year, 'run_id': snapshot['run_id'],
            'workbook_name': source['workbook_name'], 'workbook_date': source['workbook_date'],
            'workbook_modified_at': source['modified_at'], 'workbook_sha256': source['sha256'],
            'published_at': snapshot['published_at'], 'loaded_at': loaded,
            'available_years': years, 'snapshot': snapshot}
