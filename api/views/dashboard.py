from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.authentication import SessionAuthentication
from django.utils import timezone
from datetime import timedelta
from django.db.models import Avg
from ..models import MentorVisit, YeboVisit, ThousandStoriesVisit, NumeracyVisit
from ..authentication import ClerkAuthentication


@api_view(['GET'])
@authentication_classes([SessionAuthentication, ClerkAuthentication])
@permission_classes([permissions.IsAuthenticated])
def dashboard_summary(request):
    """Get summary statistics for the dashboard"""
    # Get filter parameters
    time_filter = request.query_params.get('time_filter', 'all')
    school_id = request.query_params.get('school')
    mentor_id = request.query_params.get('mentor')
    
    # Base querysets
    mentor_visits = MentorVisit.objects.all()
    yebo_visits = YeboVisit.objects.all()
    stories_visits = ThousandStoriesVisit.objects.all()
    numeracy_visits = NumeracyVisit.objects.all()
    
    # Apply time filter
    today = timezone.now().date()
    if time_filter == '7days':
        date_threshold = today - timedelta(days=7)
        mentor_visits = mentor_visits.filter(visit_date__gte=date_threshold)
        yebo_visits = yebo_visits.filter(visit_date__gte=date_threshold)
        stories_visits = stories_visits.filter(visit_date__gte=date_threshold)
        numeracy_visits = numeracy_visits.filter(visit_date__gte=date_threshold)
    elif time_filter == '30days':
        date_threshold = today - timedelta(days=30)
        mentor_visits = mentor_visits.filter(visit_date__gte=date_threshold)
        yebo_visits = yebo_visits.filter(visit_date__gte=date_threshold)
        stories_visits = stories_visits.filter(visit_date__gte=date_threshold)
        numeracy_visits = numeracy_visits.filter(visit_date__gte=date_threshold)
    elif time_filter == '90days':
        date_threshold = today - timedelta(days=90)
        mentor_visits = mentor_visits.filter(visit_date__gte=date_threshold)
        yebo_visits = yebo_visits.filter(visit_date__gte=date_threshold)
        stories_visits = stories_visits.filter(visit_date__gte=date_threshold)
        numeracy_visits = numeracy_visits.filter(visit_date__gte=date_threshold)
    elif time_filter == 'thisyear':
        year_start = today.replace(month=1, day=1)
        mentor_visits = mentor_visits.filter(visit_date__gte=year_start)
        yebo_visits = yebo_visits.filter(visit_date__gte=year_start)
        stories_visits = stories_visits.filter(visit_date__gte=year_start)
        numeracy_visits = numeracy_visits.filter(visit_date__gte=year_start)
    
    # Apply school filter
    if school_id:
        mentor_visits = mentor_visits.filter(school_id=school_id)
        yebo_visits = yebo_visits.filter(school_id=school_id)
        stories_visits = stories_visits.filter(school_id=school_id)
        numeracy_visits = numeracy_visits.filter(school_id=school_id)
    
    # Apply mentor filter
    if mentor_id:
        mentor_visits = mentor_visits.filter(mentor_id=mentor_id)
        yebo_visits = yebo_visits.filter(mentor_id=mentor_id)
        stories_visits = stories_visits.filter(mentor_id=mentor_id)
        numeracy_visits = numeracy_visits.filter(mentor_id=mentor_id)
    
    # Calculate summary stats
    thirty_days_ago = today - timedelta(days=30)
    
    # Get all school IDs that have visits
    all_school_ids = set()
    all_school_ids.update(mentor_visits.values_list('school_id', flat=True))
    all_school_ids.update(yebo_visits.values_list('school_id', flat=True))
    all_school_ids.update(stories_visits.values_list('school_id', flat=True))
    all_school_ids.update(numeracy_visits.values_list('school_id', flat=True))
    
    return Response({
        'total_visits': (
            mentor_visits.count() + 
            yebo_visits.count() + 
            stories_visits.count() + 
            numeracy_visits.count()
        ),
        'recent_visits': (
            mentor_visits.filter(visit_date__gte=thirty_days_ago).count() +
            yebo_visits.filter(visit_date__gte=thirty_days_ago).count() +
            stories_visits.filter(visit_date__gte=thirty_days_ago).count() +
            numeracy_visits.filter(visit_date__gte=thirty_days_ago).count()
        ),
        'schools_visited': len(all_school_ids),
        'avg_quality': mentor_visits.aggregate(
            avg=Avg('quality_rating')
        )['avg'] or 0,
        'literacy_visits': mentor_visits.count(),
        'literacy_recent_visits': mentor_visits.filter(
            visit_date__gte=thirty_days_ago
        ).count(),
        'yebo_visits': yebo_visits.count(),
        'yebo_recent_visits': yebo_visits.filter(
            visit_date__gte=thirty_days_ago
        ).count(),
        'stories_visits': stories_visits.count(),
        'stories_recent_visits': stories_visits.filter(
            visit_date__gte=thirty_days_ago
        ).count(),
        'numeracy_visits': numeracy_visits.count(),
        'numeracy_recent_visits': numeracy_visits.filter(
            visit_date__gte=thirty_days_ago
        ).count(),
    })

