from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.authentication import SessionAuthentication
from django.utils import timezone
from datetime import timedelta
from ..models import MentorVisit, YeboVisit, ThousandStoriesVisit, NumeracyVisit
from ..authentication import ClerkAuthentication


@api_view(['GET'])
@authentication_classes([SessionAuthentication, ClerkAuthentication])
@permission_classes([permissions.IsAuthenticated])
def recent_visits(request):
    """
    Get the most recent visits across all programs (up to 100)
    Returns a unified list of visits with program type, school, date, quality, and comments

    Query Parameters:
    - time_filter: 7days, 30days, 90days, thisyear, all (default)
    - school: Filter by school ID
    - mentor: Filter by mentor user ID
    - limit: Maximum number of visits to return (default: 100, max: 500)
    """
    # Get filter parameters
    time_filter = request.query_params.get('time_filter', 'all')
    school_id = request.query_params.get('school')
    mentor_id = request.query_params.get('mentor')
    limit = min(int(request.query_params.get('limit', 100)), 500)  # Cap at 500 for safety

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

    # Select related to optimize queries
    mentor_visits = mentor_visits.select_related('school', 'mentor')
    yebo_visits = yebo_visits.select_related('school', 'mentor')
    stories_visits = stories_visits.select_related('school', 'mentor')
    numeracy_visits = numeracy_visits.select_related('school', 'mentor')

    # Collect all visits in a unified format
    all_visits = []

    # MASI Literacy visits
    for visit in mentor_visits:
        all_visits.append({
            'id': f'literacy-{visit.id}',
            'program_name': 'MASI Literacy',
            'program_type': 'literacy',
            'school_name': visit.school.name,
            'visit_date': visit.visit_date.isoformat(),
            'session_quality': visit.quality_rating,
            'comments': visit.commentary or '',
            'mentor_name': f'{visit.mentor.first_name} {visit.mentor.last_name}',
        })

    # Yebo visits
    for visit in yebo_visits:
        all_visits.append({
            'id': f'yebo-{visit.id}',
            'program_name': 'Yebo',
            'program_type': 'yebo',
            'school_name': visit.school.name,
            'visit_date': visit.visit_date.isoformat(),
            'session_quality': visit.afternoon_session_quality,
            'comments': visit.commentary or '',
            'mentor_name': f'{visit.mentor.first_name} {visit.mentor.last_name}',
        })

    # 1000 Stories visits
    for visit in stories_visits:
        all_visits.append({
            'id': f'stories-{visit.id}',
            'program_name': '1000 Stories',
            'program_type': 'stories',
            'school_name': visit.school.name,
            'visit_date': visit.visit_date.isoformat(),
            'session_quality': visit.story_time_quality,
            'comments': visit.other_comments or '',
            'mentor_name': f'{visit.mentor.first_name} {visit.mentor.last_name}',
        })

    # Numeracy visits
    for visit in numeracy_visits:
        all_visits.append({
            'id': f'numeracy-{visit.id}',
            'program_name': 'Numeracy',
            'program_type': 'numeracy',
            'school_name': visit.school.name,
            'visit_date': visit.visit_date.isoformat(),
            'session_quality': visit.quality_rating,
            'comments': visit.commentary or '',
            'mentor_name': f'{visit.mentor.first_name} {visit.mentor.last_name}',
        })

    # Sort by visit date (most recent first) and limit results
    all_visits.sort(key=lambda x: x['visit_date'], reverse=True)
    all_visits = all_visits[:limit]

    return Response({
        'visits': all_visits,
        'total_count': len(all_visits),
    })
