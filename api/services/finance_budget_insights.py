"""Read-only presentation of validated budget-run 1.0.0 retained operands.

Rounded published amounts and residuals are never inputs to new budget math.
The BC totals are exact because their source ledger facts already have cents.
"""
from decimal import Decimal, ROUND_HALF_UP, localcontext

from masi_finance.publish.excel import excel_equal
from masi_finance.publish.org_budget_projection import METRICS, additive, decode_exact, project, q

from api.services.finance_runs import FinanceRunError


def budget_insights(run):
    """Caller must validate the stored run and authorize its pinned dependency."""
    data = run.payload
    with localcontext() as context:
        context.prec = max(data['projection']['calculation_precision'], 38)
        return _insights(run, data)


def _insights(run, data):
    lines, hierarchy = data['lines'], data['hierarchy']
    month = data['projection']['month_count']
    actuals = {line_id: Decimal(group['ledger_actual'])
               for group in data['lines_by_bc'] for line_id in group['line_ids']}
    values = {}
    excluded = set()
    for line in lines:
        budget = decode_exact(line['calculation_inputs']['budget_assertion'])
        actual = actuals.get(line['id'])
        if actual is not None and line['actual_share'] == '1/2':
            actual *= Decimal('0.5')
        projected = project(budget, actual, month, line['calc'])
        variance = None if projected is None or budget is None else projected - budget
        if excel_equal(line['wf'], 'X'):
            excluded.add(line['id'])
        values[line['id']] = dict(budget=budget, actual=actual, projected=projected,
            variance_all=variance, variance_masi=None if line['id'] in excluded else variance)

    for node in reversed(hierarchy):
        values[node['id']] = {}
        for metric in METRICS:
            parts = [values[child][metric] for child in node['child_ids']
                     if not (metric == 'variance_masi' and child in excluded)]
            values[node['id']][metric] = (None if any(value is None for value in parts)
                                         else sum(parts, Decimal(0)))

    roots = [(index, node) for index, node in enumerate(hierarchy) if node['parent_id'] is None]
    organisation = {}
    for metric in METRICS:
        parts = [(f'/derived/hierarchy/{index}/{metric}', values[node['id']][metric], 1)
                 for index, node in roots]
        projection = additive(parts)
        known = sum((values[line['id']][metric] for line in lines
                     if values[line['id']][metric] is not None), Decimal(0))
        organisation[metric] = dict(**projection, known_subtotal=q(known),
                                    complete=projection['total'] is not None)

    bucket_values = [(node['id'], node['label'], values[node['id']]['actual']) for _, node in roots]
    if data['orphan_actuals']:
        orphan = sum((Decimal(group['actual']) for group in data['orphan_actuals']), Decimal(0))
        bucket_values.append(('unbudgeted', 'Unbudgeted / unmapped expenditure', orphan))
    annual = Decimal(data['summary']['year_actual'])
    reasons = []
    if any(amount is None for _, _, amount in bucket_values):
        reasons.append('incomplete_actuals')
    if any(amount is not None and amount < 0 for _, _, amount in bucket_values) or annual < 0:
        reasons.append('negative_amounts')
    if annual == 0:
        reasons.append('zero_total')
    residual = None
    if 'incomplete_actuals' not in reasons:
        if sum((amount for _, _, amount in bucket_values), Decimal(0)) != annual:
            raise FinanceRunError('BUDGET_RUN_INTEGRITY_INVALID')
        residual = q(annual - sum((Decimal(q(amount)) for _, _, amount in bucket_values), Decimal(0)))
    available = not reasons
    buckets = [dict(id=identifier, label=label, amount=q(amount),
                    percentage=format((amount / annual * 100).quantize(Decimal('0.000001'),
                        rounding=ROUND_HALF_UP), '.6f') if available else None)
               for identifier, label, amount in bucket_values]
    return dict(version='1.0.0', run_id=str(run.pk), ledger_run_id=str(run.dependency_run_id),
        accounting_year=run.accounting_year, sheet_as_of=data['projection']['sheet_as_of'],
        organisation=organisation, composition=dict(total=data['summary']['year_actual'],
            available=available, reasons=reasons, buckets=buckets, residual=residual))
