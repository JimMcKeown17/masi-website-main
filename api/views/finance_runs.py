"""Run history, checked publication and coherent current finance metadata."""
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import CursorPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from api.models import FinanceRun
from api.permissions import IsFinancePublisher, IsFinanceReader, finance_capabilities_for
from api.services.finance_runs import FinanceRunError, approve_run, demote_run
from api.views.finance import AUTH_CLASSES


class RunPagination(CursorPagination):
    page_size = 50
    ordering = ('-uploaded_at', '-id')


def visible_runs(user):
    capabilities = finance_capabilities_for(user)
    if not capabilities:
        raise PermissionDenied('Finance access is not granted for this account.')
    statuses = []
    if 'finance.read' in capabilities:
        statuses.extend(['approved', 'superseded'])
    if 'finance.publish' in capabilities:
        statuses.extend(['candidate', 'failed'])
    return FinanceRun.objects.filter(status__in=statuses)


class RunMetadataSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinanceRun
        fields = ('id', 'kind', 'accounting_year', 'status', 'source_name', 'source_date', 'source_sha256',
                  'source_size_bytes', 'schema_version', 'producer_version', 'payload_sha256', 'facts_sha256',
                  'uploaded_by', 'uploaded_at', 'approved_by', 'approved_at', 'previous_approved',
                  'approval_overrode_rollback', 'approval_acknowledged_findings', 'approval_note',
                  'demoted_by', 'demoted_at', 'demotion_note', 'parse_duration_ms', 'total_duration_ms',
                  'peak_memory_bytes', 'fact_row_count', 'allocation_count', 'finding_count', 'in_scope_error_count')
        read_only_fields = fields


def run_detail(run, user):
    result = dict(RunMetadataSerializer(run).data)
    result.update(manifest=run.manifest, payload=run.payload, failure=run.failure, allowed_actions=[])
    if 'finance.publish' in finance_capabilities_for(user):
        if run.status == 'candidate' or (run.status == 'superseded' and run.approved_at and run.approved_by_id):
            result['allowed_actions'].append('approve')
        if run.status == 'approved' and run.previous_approved_id:
            result['allowed_actions'].append('demote')
    return result


def year_parameter(params, *, required=False):
    value = params.get('year')
    if value is None and not required:
        return None
    try:
        year = int(value)
    except (ValueError, TypeError):
        raise ValidationError({'year': 'year must be an integer.'}) from None
    if not 1 <= year <= 32767:
        raise ValidationError({'year': 'year is outside the supported range.'})
    return year


class FinanceRunList(APIView):
    authentication_classes = AUTH_CLASSES

    def get(self, request):
        queryset = visible_runs(request.user)
        unknown = set(request.query_params) - {'kind', 'year', 'status', 'cursor'}
        if unknown:
            raise ValidationError('Unknown run filter.')
        if 'kind' in request.query_params:
            if request.query_params['kind'] != 'funders':
                raise ValidationError({'kind': 'Unsupported finance kind.'})
            queryset = queryset.filter(kind='funders')
        year = year_parameter(request.query_params)
        if year is not None:
            queryset = queryset.filter(accounting_year=year)
        if 'status' in request.query_params:
            status = request.query_params['status']
            if status not in ('candidate', 'approved', 'superseded', 'failed'):
                raise ValidationError({'status': 'Unsupported run status.'})
            queryset = queryset.filter(status=status)
        pagination = RunPagination()
        page = pagination.paginate_queryset(queryset.defer('manifest', 'payload', 'failure'), request, view=self)
        return pagination.get_paginated_response(RunMetadataSerializer(page, many=True).data)


class FinanceRunDetail(APIView):
    authentication_classes = AUTH_CLASSES

    def get(self, request, run_id):
        run = get_object_or_404(visible_runs(request.user), pk=run_id)
        return Response(run_detail(run, request.user))


class ApprovalOptionsSerializer(serializers.Serializer):
    override_anti_rollback = serializers.BooleanField(default=False)
    acknowledge_findings = serializers.BooleanField(default=False)
    note = serializers.CharField(default='', allow_blank=True, max_length=10000)

    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) - set(self.fields):
            raise ValidationError({'non_field_errors': ['Only override_anti_rollback, acknowledge_findings and note are accepted.']})
        for field in ('override_anti_rollback', 'acknowledge_findings'):
            if field in data and type(data[field]) is not bool:
                raise ValidationError({field: 'Must be a JSON boolean.'})
        if 'note' in data and not isinstance(data['note'], str):
            raise ValidationError({'note': 'Must be a string.'})
        return super().to_internal_value(data)


class FinanceRunApprove(APIView):
    authentication_classes = AUTH_CLASSES
    permission_classes = [IsFinancePublisher]
    transition = staticmethod(approve_run)

    def post(self, request, run_id):
        serializer = ApprovalOptionsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            run = self.transition(run_id, request.user, **serializer.validated_data)
        except FinanceRunError as exc:
            return Response({'code': exc.code, 'detail': exc.code}, status=exc.status)
        return Response(run_detail(run, request.user))


class FinanceRunDemote(FinanceRunApprove):
    transition = staticmethod(demote_run)


def compatibility_result(runs):
    if not runs:
        return False, {'code': 'NO_APPROVED_RUNS', 'runs': {}}
    if any(not run.get('management_accounts_sha256') for run in runs.values()):
        return False, {'code': 'DEPENDENCY_UNRESOLVED', 'runs': runs}
    if len({run['management_accounts_sha256'] for run in runs.values()}) != 1:
        return False, {'code': 'SOURCE_MISMATCH', 'runs': runs}
    return True, None


def management_accounts_sha(run):
    if run.kind == 'funders':
        return run.source_sha256
    # Future kinds must declare their source explicitly. Ambiguity fails closed.
    dependencies = run.manifest.get('dependencies', [])
    sources = {item.get('source_sha256') for item in dependencies if item.get('kind') == 'funders'}
    return next(iter(sources)) if len(sources) == 1 else None


class FinanceCurrent(APIView):
    authentication_classes = AUTH_CLASSES
    permission_classes = [IsFinanceReader]

    def get(self, request):
        if set(request.query_params) - {'year'}:
            raise ValidationError('Unknown current-run filter.')
        year = year_parameter(request.query_params, required=True)
        runs = {}
        for run in FinanceRun.objects.filter(accounting_year=year, status='approved').defer('payload', 'failure'):
            runs[run.kind] = {'id': str(run.pk), 'source_sha256': run.source_sha256,
                              'management_accounts_sha256': management_accounts_sha(run),
                              'schema_version': run.schema_version, 'approved_at': run.approved_at.isoformat()}
        compatible, reason = compatibility_result(runs)
        return Response({'accounting_year': year, 'runs': runs, 'compatible': compatible, 'compatibility_reason': reason})
