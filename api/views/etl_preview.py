from django.db.models import Max
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from api.authentication import ClerkAuthentication

from api.models import (
    School, Youth, CanonicalChild, Staff,
    LiteracySession2026, NumeracySession2026,
    AirtableSyncLog,
)

# Map of table names to (model, sync_type) pairs
TABLE_CONFIG = {
    'schools': (School, 'schools'),
    'youth': (Youth, 'youth'),
    'children': (CanonicalChild, 'canonical_children'),
    'staff': (Staff, 'staff'),
    'literacy-2026': (LiteracySession2026, 'literacy_sessions_2026'),
    'numeracy-2026': (NumeracySession2026, 'numeracy_sessions_2026'),
}


@api_view(['GET'])
@authentication_classes([SessionAuthentication, ClerkAuthentication])
@permission_classes([IsAuthenticated])
def etl_status(request):
    """Sync health summary for all ETL tables."""
    # Get latest successful sync per sync_type
    latest_syncs = {}
    for log in AirtableSyncLog.objects.filter(success=True).order_by('-completed_at'):
        if log.sync_type not in latest_syncs:
            latest_syncs[log.sync_type] = log

    tables = []
    for name, (model, sync_type) in TABLE_CONFIG.items():
        log = latest_syncs.get(sync_type)
        tables.append({
            'name': name,
            'record_count': model.objects.count(),
            'last_sync': log.completed_at.isoformat() if log and log.completed_at else None,
            'last_sync_records': log.records_processed if log else None,
        })

    return Response({'tables': tables})


@api_view(['GET'])
@authentication_classes([SessionAuthentication, ClerkAuthentication])
@permission_classes([IsAuthenticated])
def etl_preview(request, table_name):
    """Sample rows + FK resolution stats for one ETL table."""
    if table_name not in TABLE_CONFIG:
        return Response({'error': f'Unknown table: {table_name}'}, status=400)

    model, sync_type = TABLE_CONFIG[table_name]
    record_count = model.objects.count()

    result = {
        'table_name': table_name,
        'record_count': record_count,
    }

    if table_name == 'literacy-2026':
        result['orphan_stats'] = _literacy_orphan_stats()
        result['sample_rows'] = _literacy_sample_rows()
    elif table_name == 'numeracy-2026':
        result['orphan_stats'] = _numeracy_orphan_stats()
        result['sample_rows'] = _numeracy_sample_rows()
    elif table_name == 'schools':
        result['sample_rows'] = _school_sample_rows()
    elif table_name == 'youth':
        result['sample_rows'] = _youth_sample_rows()
    elif table_name == 'children':
        result['sample_rows'] = _child_sample_rows()
    elif table_name == 'staff':
        result['sample_rows'] = _staff_sample_rows()

    return Response(result)


def _literacy_orphan_stats():
    total = LiteracySession2026.objects.count()
    if total == 0:
        return {}
    youth_resolved = LiteracySession2026.objects.filter(youth__isnull=False).count()
    school_resolved = LiteracySession2026.objects.filter(school__isnull=False).count()
    child1_resolved = LiteracySession2026.objects.filter(child_1__isnull=False).count()
    child2_resolved = LiteracySession2026.objects.filter(child_2__isnull=False).count()
    return {
        'youth_resolved': youth_resolved,
        'youth_orphaned': total - youth_resolved,
        'school_resolved': school_resolved,
        'school_orphaned': total - school_resolved,
        'child1_resolved': child1_resolved,
        'child1_orphaned': total - child1_resolved,
        'child2_resolved': child2_resolved,
        'child2_orphaned': total - child2_resolved,
    }


def _numeracy_orphan_stats():
    total = NumeracySession2026.objects.count()
    if total == 0:
        return {}
    youth_resolved = NumeracySession2026.objects.filter(youth__isnull=False).count()
    school_resolved = NumeracySession2026.objects.filter(school__isnull=False).count()
    return {
        'youth_resolved': youth_resolved,
        'youth_orphaned': total - youth_resolved,
        'school_resolved': school_resolved,
        'school_orphaned': total - school_resolved,
    }


def _literacy_sample_rows():
    qs = LiteracySession2026.objects.select_related(
        'youth', 'school', 'child_1', 'child_2'
    ).order_by('-session_date')[:20]
    return [
        {
            'id': s.id,
            'session_uid': s.session_uid,
            'session_date': str(s.session_date) if s.session_date else None,
            'youth_uid': s.youth_uid,
            'youth_name': s.youth.full_name if s.youth else None,
            'school_uid': s.school_uid,
            'school_name': s.school.name if s.school else None,
            'child_uid_1': s.child_uid_1,
            'child_1_name': s.child_1.full_name if s.child_1 else None,
            'child_uid_2': s.child_uid_2,
            'child_2_name': s.child_2.full_name if s.child_2 else None,
            'sounds_covered_clean': s.sounds_covered_clean,
            'blending_level': s.blending_level,
            'duplicate_status': s.duplicate_status,
            'overall_session_status': s.overall_session_status,
        }
        for s in qs
    ]


def _numeracy_sample_rows():
    qs = NumeracySession2026.objects.select_related(
        'youth', 'school'
    ).order_by('-session_date')[:20]
    return [
        {
            'id': s.id,
            'session_uid': s.session_uid,
            'session_date': str(s.session_date) if s.session_date else None,
            'youth_uid': s.youth_uid,
            'youth_name': s.youth.full_name if s.youth else None,
            'school_uid': s.school_uid,
            'school_name': s.school.name if s.school else None,
            'child_uids': s.child_uids,
            'children_count': s.children_count,
            'group_count_level': s.group_count_level,
            'group_number_recognition': s.group_number_recognition,
            'duplicate_status': s.duplicate_status,
        }
        for s in qs
    ]


def _school_sample_rows():
    return list(
        School.objects.values(
            'id', 'name', 'school_uid', 'suburb', 'school_number'
        ).order_by('name')[:20]
    )


def _youth_sample_rows():
    return list(
        Youth.objects.values(
            'id', 'full_name', 'youth_uid', 'employee_id', 'employment_status', 'job_title'
        ).order_by('last_name')[:20]
    )


def _child_sample_rows():
    return list(
        CanonicalChild.objects.values(
            'id', 'full_name', 'child_uid', 'mcode', 'gender', 'school_2025', 'grade_2025'
        ).order_by('mcode')[:20]
    )


def _staff_sample_rows():
    return list(
        Staff.objects.values(
            'id', 'name', 'employee_number', 'gender', 'email'
        ).order_by('name')[:20]
    )
