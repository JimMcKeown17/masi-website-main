import json
from datetime import datetime, timedelta
from django.db.models import Count, Avg, Sum, Case, When, IntegerField, F, OuterRef, Subquery
from django.db.models.functions import TruncMonth, TruncWeek
from api.models import MentorVisit, YeboVisit, ThousandStoriesVisit, NumeracyVisit, School
import json

def generate_combined_visit_frequency_chart(mentor_visits, yebo_visits, thousand_stories_visits, numeracy_visits, time_period='week'):
    """
    Generate chart data for combined visit frequency over time from all four visit types
    
    Args:
        mentor_visits: QuerySet of MentorVisit objects
        yebo_visits: QuerySet of YeboVisit objects  
        thousand_stories_visits: QuerySet of ThousandStoriesVisit objects
        numeracy_visits: QuerySet of NumeracyVisit objects
        time_period: 'week' or 'month'
    
    Returns:
        JSON-serialized chart data
    """
    # Combine all visits with their types
    all_periods = set()
    
    # Process each visit type
    if time_period == 'week':
        mentor_by_time = mentor_visits.annotate(period=TruncWeek('visit_date')).values('period').annotate(count=Count('id')).order_by('period')
        yebo_by_time = yebo_visits.annotate(period=TruncWeek('visit_date')).values('period').annotate(count=Count('id')).order_by('period')
        stories_by_time = thousand_stories_visits.annotate(period=TruncWeek('visit_date')).values('period').annotate(count=Count('id')).order_by('period')
        numeracy_by_time = numeracy_visits.annotate(period=TruncWeek('visit_date')).values('period').annotate(count=Count('id')).order_by('period')
        date_format = '%b %d'
    else:
        mentor_by_time = mentor_visits.annotate(period=TruncMonth('visit_date')).values('period').annotate(count=Count('id')).order_by('period')
        yebo_by_time = yebo_visits.annotate(period=TruncMonth('visit_date')).values('period').annotate(count=Count('id')).order_by('period')
        stories_by_time = thousand_stories_visits.annotate(period=TruncMonth('visit_date')).values('period').annotate(count=Count('id')).order_by('period')
        numeracy_by_time = numeracy_visits.annotate(period=TruncMonth('visit_date')).values('period').annotate(count=Count('id')).order_by('period')
        date_format = '%b %Y'
    
    # Collect all periods
    for item in mentor_by_time:
        all_periods.add(item['period'])
    for item in yebo_by_time:
        all_periods.add(item['period'])
    for item in stories_by_time:
        all_periods.add(item['period'])
    for item in numeracy_by_time:
        all_periods.add(item['period'])
    
    # Sort periods
    sorted_periods = sorted(all_periods)
    
    # Create data dictionaries for lookup
    mentor_data = {item['period']: item['count'] for item in mentor_by_time}
    yebo_data = {item['period']: item['count'] for item in yebo_by_time}
    stories_data = {item['period']: item['count'] for item in stories_by_time}
    numeracy_data = {item['period']: item['count'] for item in numeracy_by_time}
    
    # Build chart data
    labels = [period.strftime(date_format) for period in sorted_periods]
    mentor_values = [mentor_data.get(period, 0) for period in sorted_periods]
    yebo_values = [yebo_data.get(period, 0) for period in sorted_periods]
    stories_values = [stories_data.get(period, 0) for period in sorted_periods]
    numeracy_values = [numeracy_data.get(period, 0) for period in sorted_periods]
    
    chart_data = {
        'labels': labels,
        'datasets': [
            {
                'label': 'Masi Literacy Visits',
                'data': mentor_values,
                'backgroundColor': 'rgba(54, 162, 235, 0.5)',
                'borderColor': 'rgba(54, 162, 235, 1)',
                'borderWidth': 1
            },
            {
                'label': 'Yebo Visits',
                'data': yebo_values,
                'backgroundColor': 'rgba(255, 99, 132, 0.5)',
                'borderColor': 'rgba(255, 99, 132, 1)',
                'borderWidth': 1
            },
            {
                'label': '1000 Stories Visits',
                'data': stories_values,
                'backgroundColor': 'rgba(75, 192, 192, 0.5)',
                'borderColor': 'rgba(75, 192, 192, 1)',
                'borderWidth': 1
            },
            {
                'label': 'Numeracy Visits',
                'data': numeracy_values,
                'backgroundColor': 'rgba(153, 102, 255, 0.5)',
                'borderColor': 'rgba(153, 102, 255, 1)',
                'borderWidth': 1
            }
        ]
    }
    
    return json.dumps(chart_data)

def generate_visit_frequency_chart(visits, time_period='week'):
    """
    Generate chart data for visit frequency over time
    
    Args:
        visits: QuerySet of MentorVisit objects
        time_period: 'week' or 'month'
    
    Returns:
        JSON-serialized chart data
    """
    # Group visits by time period
    if time_period == 'week':
        visits_by_time = visits.annotate(
            period=TruncWeek('visit_date')
        ).values('period').annotate(count=Count('id')).order_by('period')
        
        # Format for chart display
        labels = [item['period'].strftime('%b %d') for item in visits_by_time]
    else:
        visits_by_time = visits.annotate(
            period=TruncMonth('visit_date')
        ).values('period').annotate(count=Count('id')).order_by('period')
        
        # Format for chart display
        labels = [item['period'].strftime('%b %Y') for item in visits_by_time]
    
    values = [item['count'] for item in visits_by_time]
    
    # Prepare chart data
    chart_data = {
        'labels': labels,
        'datasets': [{
            'label': 'Number of Visits',
            'data': values,
            'backgroundColor': 'rgba(54, 162, 235, 0.5)',
            'borderColor': 'rgba(54, 162, 235, 1)',
            'borderWidth': 1
        }]
    }
    
    return json.dumps(chart_data)

def generate_combined_quality_rating_chart(mentor_visits, yebo_visits, thousand_stories_visits, numeracy_visits):
    """
    Generate chart data for quality ratings distribution from all visit types
    
    Args:
        mentor_visits: QuerySet of MentorVisit objects
        yebo_visits: QuerySet of YeboVisit objects
        thousand_stories_visits: QuerySet of ThousandStoriesVisit objects
        numeracy_visits: QuerySet of NumeracyVisit objects
    
    Returns:
        JSON-serialized chart data
    """
    # Collect all ratings
    all_ratings = {}
    
    # Count literacy visits by quality rating
    literacy_ratings = mentor_visits.values('quality_rating').annotate(count=Count('id')).order_by('quality_rating')
    for item in literacy_ratings:
        rating = item['quality_rating']
        all_ratings[rating] = all_ratings.get(rating, {'literacy': 0, 'yebo': 0, 'stories': 0, 'numeracy': 0})
        all_ratings[rating]['literacy'] = item['count']
    
    # Count Yebo visits by afternoon session quality
    yebo_ratings = yebo_visits.values('afternoon_session_quality').annotate(count=Count('id')).order_by('afternoon_session_quality')
    for item in yebo_ratings:
        rating = item['afternoon_session_quality']
        all_ratings[rating] = all_ratings.get(rating, {'literacy': 0, 'yebo': 0, 'stories': 0, 'numeracy': 0})
        all_ratings[rating]['yebo'] = item['count']
    
    # Count 1000 Stories visits by story time quality
    stories_ratings = thousand_stories_visits.values('story_time_quality').annotate(count=Count('id')).order_by('story_time_quality')
    for item in stories_ratings:
        rating = item['story_time_quality']
        all_ratings[rating] = all_ratings.get(rating, {'literacy': 0, 'yebo': 0, 'stories': 0, 'numeracy': 0})
        all_ratings[rating]['stories'] = item['count']
    
    # Count Numeracy visits by quality rating
    numeracy_ratings = numeracy_visits.values('quality_rating').annotate(count=Count('id')).order_by('quality_rating')
    for item in numeracy_ratings:
        rating = item['quality_rating']
        all_ratings[rating] = all_ratings.get(rating, {'literacy': 0, 'yebo': 0, 'stories': 0, 'numeracy': 0})
        all_ratings[rating]['numeracy'] = item['count']
    
    # Sort ratings
    sorted_ratings = sorted(all_ratings.keys())
    
    # Build chart data
    labels = [f"Rating {rating}" for rating in sorted_ratings]
    literacy_values = [all_ratings[rating]['literacy'] for rating in sorted_ratings]
    yebo_values = [all_ratings[rating]['yebo'] for rating in sorted_ratings]
    stories_values = [all_ratings[rating]['stories'] for rating in sorted_ratings]
    numeracy_values = [all_ratings[rating]['numeracy'] for rating in sorted_ratings]
    
    chart_data = {
        'labels': labels,
        'datasets': [
            {
                'label': 'Masi Literacy',
                'data': literacy_values,
                'backgroundColor': 'rgba(54, 162, 235, 0.7)',
                'borderColor': 'rgba(54, 162, 235, 1)',
                'borderWidth': 1
            },
            {
                'label': 'Yebo',
                'data': yebo_values,
                'backgroundColor': 'rgba(255, 99, 132, 0.7)',
                'borderColor': 'rgba(255, 99, 132, 1)',
                'borderWidth': 1
            },
            {
                'label': '1000 Stories',
                'data': stories_values,
                'backgroundColor': 'rgba(75, 192, 192, 0.7)',
                'borderColor': 'rgba(75, 192, 192, 1)',
                'borderWidth': 1
            },
            {
                'label': 'Numeracy',
                'data': numeracy_values,
                'backgroundColor': 'rgba(153, 102, 255, 0.7)',
                'borderColor': 'rgba(153, 102, 255, 1)',
                'borderWidth': 1
            }
        ]
    }
    
    return json.dumps(chart_data)

def generate_quality_rating_chart(visits):
    """
    Generate chart data for quality ratings distribution
    
    Args:
        visits: QuerySet of MentorVisit objects
    
    Returns:
        JSON-serialized chart data
    """
    # Count visits by quality rating
    rating_counts = visits.values('quality_rating').annotate(
        count=Count('id')
    ).order_by('quality_rating')
    
    # Format for chart display
    labels = [f"Rating {item['quality_rating']}" for item in rating_counts]
    values = [item['count'] for item in rating_counts]
    
    # Generate a color gradient from red to green
    colors = []
    for i, rating in enumerate(rating_counts):
        r = max(0, int(255 * (1 - rating['quality_rating'] / 10)))
        g = max(0, int(255 * (rating['quality_rating'] / 10)))
        b = 0
        colors.append(f'rgba({r}, {g}, {b}, 0.7)')
    
    # Prepare chart data
    chart_data = {
        'labels': labels,
        'datasets': [{
            'label': 'Number of Visits',
            'data': values,
            'backgroundColor': colors,
            'borderColor': colors,
            'borderWidth': 1
        }]
    }
    
    return json.dumps(chart_data)

def generate_letter_tracker_accuracy_chart(visits):
    """
    Generate chart data for letter tracker accuracy metrics (Literacy only)
    
    Args:
        visits: QuerySet of MentorVisit objects
    
    Returns:
        JSON-serialized chart data
    """
    # Calculate percentage of correct tracker usage
    total_visits = visits.count()
    if total_visits == 0:
        return json.dumps({})  # Return empty data if no visits
    
    metrics = {
        'Letter Trackers': visits.filter(letter_trackers_correct=True).count() / total_visits * 100,
        'Reading Trackers': visits.filter(reading_trackers_correct=True).count() / total_visits * 100,
        'Session Trackers': visits.filter(sessions_correct=True).count() / total_visits * 100,
        'Admin': visits.filter(admin_correct=True).count() / total_visits * 100
    }
    
    # Format for chart display
    labels = list(metrics.keys())
    values = list(metrics.values())
    
    # Prepare chart data for radar chart
    chart_data = {
        'labels': labels,
        'datasets': [{
            'label': 'Correct Usage (%)',
            'data': values,
            'backgroundColor': 'rgba(54, 162, 235, 0.2)',
            'borderColor': 'rgba(54, 162, 235, 1)',
            'pointBackgroundColor': 'rgba(54, 162, 235, 1)',
            'pointBorderColor': '#fff',
            'pointHoverBackgroundColor': '#fff',
            'pointHoverBorderColor': 'rgba(54, 162, 235, 1)'
        }]
    }
    
    return json.dumps(chart_data)

# Keep the old function name for backward compatibility
def generate_tracker_accuracy_chart(visits):
    """Legacy function name - calls generate_letter_tracker_accuracy_chart"""
    return generate_letter_tracker_accuracy_chart(visits)

def generate_combined_school_visit_map(mentor_visits, yebo_visits, thousand_stories_visits, numeracy_visits):
    """
    Generate map data for school visit distribution from all visit types
    
    Args:
        mentor_visits: QuerySet of MentorVisit objects
        yebo_visits: QuerySet of YeboVisit objects
        thousand_stories_visits: QuerySet of ThousandStoriesVisit objects
    
    Returns:
        JSON-serialized map data
    """
    # Get schools with visit counts from all types
    schools_data = {}
    
    # Process literacy visits
    literacy_schools = School.objects.filter(visits__in=mentor_visits).annotate(
        visit_count=Count('visits'),
        avg_quality=Avg('visits__quality_rating')
    ).values('id', 'name', 'latitude', 'longitude', 'type', 'visit_count', 'avg_quality')
    
    for school in literacy_schools:
        school_id = school['id']
        schools_data[school_id] = {
            'id': school_id,
            'name': school['name'],
            'type': school['type'] or 'Unknown',
            'latitude': float(school['latitude']) if school['latitude'] else None,
            'longitude': float(school['longitude']) if school['longitude'] else None,
            'literacy_visits': school['visit_count'],
            'literacy_avg_quality': round(school['avg_quality'], 1) if school['avg_quality'] else 0,
            'yebo_visits': 0,
            'yebo_avg_quality': 0,
            'stories_visits': 0,
            'stories_avg_quality': 0,
            'numeracy_visits': 0,
            'numeracy_avg_quality': 0
        }
    
    # Process Yebo visits
    yebo_schools = School.objects.filter(yebo_visits__in=yebo_visits).annotate(
        visit_count=Count('yebo_visits'),
        avg_quality=Avg('yebo_visits__afternoon_session_quality')
    ).values('id', 'name', 'latitude', 'longitude', 'type', 'visit_count', 'avg_quality')
    
    for school in yebo_schools:
        school_id = school['id']
        if school_id not in schools_data:
            schools_data[school_id] = {
                'id': school_id,
                'name': school['name'],
                'type': school['type'] or 'Unknown',
                'latitude': float(school['latitude']) if school['latitude'] else None,
                'longitude': float(school['longitude']) if school['longitude'] else None,
                'literacy_visits': 0,
                'literacy_avg_quality': 0,
                'yebo_visits': 0,
                'yebo_avg_quality': 0,
                'stories_visits': 0,
                'stories_avg_quality': 0,
                'numeracy_visits': 0,
                'numeracy_avg_quality': 0
            }
        schools_data[school_id]['yebo_visits'] = school['visit_count']
        schools_data[school_id]['yebo_avg_quality'] = round(school['avg_quality'], 1) if school['avg_quality'] else 0
    
    # Process 1000 Stories visits
    stories_schools = School.objects.filter(thousand_stories_visits__in=thousand_stories_visits).annotate(
        visit_count=Count('thousand_stories_visits'),
        avg_quality=Avg('thousand_stories_visits__story_time_quality')
    ).values('id', 'name', 'latitude', 'longitude', 'type', 'visit_count', 'avg_quality')
    
    for school in stories_schools:
        school_id = school['id']
        if school_id not in schools_data:
            schools_data[school_id] = {
                'id': school_id,
                'name': school['name'],
                'type': school['type'] or 'Unknown',
                'latitude': float(school['latitude']) if school['latitude'] else None,
                'longitude': float(school['longitude']) if school['longitude'] else None,
                'literacy_visits': 0,
                'literacy_avg_quality': 0,
                'yebo_visits': 0,
                'yebo_avg_quality': 0,
                'stories_visits': 0,
                'stories_avg_quality': 0,
                'numeracy_visits': 0,
                'numeracy_avg_quality': 0
            }
        schools_data[school_id]['stories_visits'] = school['visit_count']
        schools_data[school_id]['stories_avg_quality'] = round(school['avg_quality'], 1) if school['avg_quality'] else 0
    
    # Process Numeracy visits
    numeracy_schools = School.objects.filter(numeracy_visits__in=numeracy_visits).annotate(
        visit_count=Count('numeracy_visits'),
        avg_quality=Avg('numeracy_visits__quality_rating')
    ).values('id', 'name', 'latitude', 'longitude', 'type', 'visit_count', 'avg_quality')
    
    for school in numeracy_schools:
        school_id = school['id']
        if school_id not in schools_data:
            schools_data[school_id] = {
                'id': school_id,
                'name': school['name'],
                'type': school['type'] or 'Unknown',
                'latitude': float(school['latitude']) if school['latitude'] else None,
                'longitude': float(school['longitude']) if school['longitude'] else None,
                'literacy_visits': 0,
                'literacy_avg_quality': 0,
                'yebo_visits': 0,
                'yebo_avg_quality': 0,
                'stories_visits': 0,
                'stories_avg_quality': 0,
                'numeracy_visits': 0,
                'numeracy_avg_quality': 0
            }
        schools_data[school_id]['numeracy_visits'] = school['visit_count']
        schools_data[school_id]['numeracy_avg_quality'] = round(school['avg_quality'], 1) if school['avg_quality'] else 0
    
    # Format for map display
    map_data = []
    for school in schools_data.values():
        # Skip schools without coordinates
        if not school['latitude'] or not school['longitude']:
            continue
        
        total_visits = school['literacy_visits'] + school['yebo_visits'] + school['stories_visits']
        
        map_data.append({
            'id': school['id'],
            'name': school['name'],
            'type': school['type'],
            'latitude': school['latitude'],
            'longitude': school['longitude'],
            'total_visits': total_visits,
            'literacy_visits': school['literacy_visits'],
            'yebo_visits': school['yebo_visits'],
            'stories_visits': school['stories_visits'],
            'literacy_avg_quality': school['literacy_avg_quality'],
            'yebo_avg_quality': school['yebo_avg_quality'],
            'stories_avg_quality': school['stories_avg_quality']
        })
    
    return json.dumps(map_data)

def generate_school_visit_map(visits):
    """
    Generate map data for school visit distribution (MentorVisit only)
    
    Args:
        visits: QuerySet of MentorVisit objects
    
    Returns:
        JSON-serialized map data
    """
    # Count visits by school and get school locations
    school_visits = School.objects.filter(
        visits__in=visits
    ).annotate(
        visit_count=Count('visits'),
        avg_quality=Avg('visits__quality_rating')
    ).values(
        'id', 'name', 'latitude', 'longitude', 'type',
        'visit_count', 'avg_quality'
    )
    
    # Format for map display
    map_data = []
    for school in school_visits:
        # Skip schools without coordinates
        if not school['latitude'] or not school['longitude']:
            continue
            
        map_data.append({
            'id': school['id'],
            'name': school['name'],
            'type': school['type'] or 'Unknown',
            'latitude': float(school['latitude']),
            'longitude': float(school['longitude']),
            'visit_count': school['visit_count'],
            'avg_quality': round(school['avg_quality'], 1) if school['avg_quality'] else 'N/A'
        })
    
    return json.dumps(map_data)

def generate_yebo_school_visit_map(yebo_visits):
    """
    Generate map data for Yebo school visit distribution
    
    Args:
        yebo_visits: QuerySet of YeboVisit objects
    
    Returns:
        JSON-serialized map data
    """
    # Count visits by school and get school locations
    school_visits = School.objects.filter(
        yebo_visits__in=yebo_visits
    ).annotate(
        visit_count=Count('yebo_visits'),
        avg_quality=Avg('yebo_visits__afternoon_session_quality')
    ).values(
        'id', 'name', 'latitude', 'longitude', 'type',
        'visit_count', 'avg_quality'
    )
    
    # Format for map display
    map_data = []
    for school in school_visits:
        # Skip schools without coordinates
        if not school['latitude'] or not school['longitude']:
            continue
            
        map_data.append({
            'id': school['id'],
            'name': school['name'],
            'type': school['type'] or 'Unknown',
            'latitude': float(school['latitude']),
            'longitude': float(school['longitude']),
            'visit_count': school['visit_count'],
            'avg_quality': round(school['avg_quality'], 1) if school['avg_quality'] else 'N/A'
        })
    
    return json.dumps(map_data)

def generate_thousand_stories_school_visit_map(thousand_stories_visits):
    """
    Generate map data for 1000 Stories school visit distribution
    
    Args:
        thousand_stories_visits: QuerySet of ThousandStoriesVisit objects
    
    Returns:
        JSON-serialized map data
    """
    # Count visits by school and get school locations
    school_visits = School.objects.filter(
        thousand_stories_visits__in=thousand_stories_visits
    ).annotate(
        visit_count=Count('thousand_stories_visits'),
        avg_quality=Avg('thousand_stories_visits__story_time_quality')
    ).values(
        'id', 'name', 'latitude', 'longitude', 'type',
        'visit_count', 'avg_quality'
    )
    
    # Format for map display
    map_data = []
    for school in school_visits:
        # Skip schools without coordinates
        if not school['latitude'] or not school['longitude']:
            continue
            
        map_data.append({
            'id': school['id'],
            'name': school['name'],
            'type': school['type'] or 'Unknown',
            'latitude': float(school['latitude']),
            'longitude': float(school['longitude']),
            'visit_count': school['visit_count'],
            'avg_quality': round(school['avg_quality'], 1) if school['avg_quality'] else 'N/A'
        })
    
    return json.dumps(map_data)

def generate_combined_dashboard_summary(mentor_visits, yebo_visits, thousand_stories_visits, numeracy_visits):
    """
    Generate combined dashboard summary statistics from all three visit types
    
    Args:
        mentor_visits: QuerySet of MentorVisit objects
        yebo_visits: QuerySet of YeboVisit objects  
        thousand_stories_visits: QuerySet of ThousandStoriesVisit objects
    
    Returns:
        Dictionary containing combined summary statistics
    """
    from datetime import datetime, timedelta
    
    thirty_days_ago = datetime.now().date() - timedelta(days=30)
    
    # Individual visit counts
    literacy_total = mentor_visits.count()
    yebo_total = yebo_visits.count()
    stories_total = thousand_stories_visits.count()
    numeracy_total = numeracy_visits.count()
    
    # Recent visit counts (last 30 days)
    literacy_recent = mentor_visits.filter(visit_date__gte=thirty_days_ago).count()
    yebo_recent = yebo_visits.filter(visit_date__gte=thirty_days_ago).count()
    stories_recent = thousand_stories_visits.filter(visit_date__gte=thirty_days_ago).count()
    numeracy_recent = numeracy_visits.filter(visit_date__gte=thirty_days_ago).count()
    
    # Combined totals
    total_visits = literacy_total + yebo_total + stories_total + numeracy_total
    total_recent = literacy_recent + yebo_recent + stories_recent + numeracy_recent
    
    # Combined schools visited
    literacy_schools = set(mentor_visits.values_list('school_id', flat=True))
    yebo_schools = set(yebo_visits.values_list('school_id', flat=True))
    stories_schools = set(thousand_stories_visits.values_list('school_id', flat=True))
    numeracy_schools = set(numeracy_visits.values_list('school_id', flat=True))
    combined_schools = literacy_schools.union(yebo_schools).union(stories_schools).union(numeracy_schools)
    
    # Calculate average quality ratings
    literacy_avg_quality = mentor_visits.aggregate(
        avg_quality=Avg('quality_rating')
    )['avg_quality'] or 0
    
    yebo_avg_quality = yebo_visits.aggregate(
        avg_quality=Avg('afternoon_session_quality')
    )['avg_quality'] or 0
    
    stories_avg_quality = thousand_stories_visits.aggregate(
        avg_quality=Avg('story_time_quality')
    )['avg_quality'] or 0
    
    numeracy_avg_quality = numeracy_visits.aggregate(
        avg_quality=Avg('quality_rating')
    )['avg_quality'] or 0
    
    # Calculate weighted average quality (weighted by number of visits)
    total_quality_points = (
        literacy_avg_quality * literacy_total +
        yebo_avg_quality * yebo_total +
        stories_avg_quality * stories_total +
        numeracy_avg_quality * numeracy_total
    )
    combined_avg_quality = total_quality_points / total_visits if total_visits > 0 else 0
    
    return {
        'total_visits': total_visits,
        'recent_visits': total_recent,
        'schools_visited': len(combined_schools),
        'avg_quality': combined_avg_quality,
        'literacy_visits': literacy_total,
        'literacy_recent_visits': literacy_recent,
        'yebo_visits': yebo_total,
        'yebo_recent_visits': yebo_recent,
        'stories_visits': stories_total,
        'stories_recent_visits': stories_recent,
        'numeracy_visits': numeracy_total,
        'numeracy_recent_visits': numeracy_recent,
    }

def generate_dashboard_summary(visits):
    """
    Generate summary statistics for the dashboard
    
    Args:
        visits: QuerySet of MentorVisit objects
    
    Returns:
        Dictionary of summary statistics
    """
    # Get visits in the last 30 days
    thirty_days_ago = datetime.now().date() - timedelta(days=30)
    recent_visits = visits.filter(visit_date__gte=thirty_days_ago)
    
    # Calculate summary statistics
    summary = {
        'total_visits': visits.count(),
        'recent_visits': recent_visits.count(),
        'schools_visited': visits.values('school').distinct().count(),
        'avg_quality': visits.aggregate(avg=Avg('quality_rating'))['avg'],
        'tracker_accuracy': {
            'letter': visits.filter(letter_trackers_correct=True).count() / max(visits.count(), 1) * 100,
            'reading': visits.filter(reading_trackers_correct=True).count() / max(visits.count(), 1) * 100,
            'sessions': visits.filter(sessions_correct=True).count() / max(visits.count(), 1) * 100,
            'admin': visits.filter(admin_correct=True).count() / max(visits.count(), 1) * 100,
        }
    }
    
    return summary

def generate_schools_last_visited(visits):
    """
    Generate data for schools last visited component
    Shows schools and when they were last visited
    """
    from datetime import datetime
    from api.models import School
    
    schools_data = []
    schools = School.objects.all()
    
    for school in schools:
        last_visit = visits.filter(school=school).order_by('-visit_date').first()
        
        if last_visit:
            days_ago = (datetime.now().date() - last_visit.visit_date).days
            schools_data.append({
                'school_name': school.name,
                'school_type': school.type if school.type else 'Unknown',
                'school_id': school.school_id if school.school_id else school.id,
                'last_visit_date': last_visit.visit_date.strftime('%Y-%m-%d'),
                'days_ago': days_ago,
                'last_mentor': f"{last_visit.mentor.first_name} {last_visit.mentor.last_name}" if last_visit.mentor.first_name else last_visit.mentor.username
            })
        else:
            schools_data.append({
                'school_name': school.name,
                'school_type': school.type if school.type else 'Unknown',
                'school_id': school.school_id if school.school_id else school.id,
                'last_visit_date': 'Never',
                'days_ago': 999,
                'last_mentor': 'N/A'
            })
    
    # Sort by days since last visit (most urgent first)
    schools_data.sort(key=lambda x: x['days_ago'], reverse=True)
    
    return schools_data

def generate_schools_last_visited_comprehensive(mentor_visits, yebo_visits, thousand_stories_visits, numeracy_visits):
    """
    Generate comprehensive data for schools last visited component
    Shows schools and when they were last visited across ALL visit types
    This provides the true most recent visit regardless of program type
    """
    from datetime import datetime
    from api.models import School
    
    schools_data = []
    schools = School.objects.all()
    
    for school in schools:
        # Find the most recent visit across all visit types
        visits_info = []
        
        # Check MentorVisit (Literacy)
        literacy_visit = mentor_visits.filter(school=school).order_by('-visit_date').first()
        if literacy_visit:
            visits_info.append({
                'visit': literacy_visit,
                'type': 'Literacy',
                'date': literacy_visit.visit_date
            })
        
        # Check YeboVisit
        yebo_visit = yebo_visits.filter(school=school).order_by('-visit_date').first()
        if yebo_visit:
            visits_info.append({
                'visit': yebo_visit,
                'type': 'Yebo',
                'date': yebo_visit.visit_date
            })
        
        # Check ThousandStoriesVisit
        stories_visit = thousand_stories_visits.filter(school=school).order_by('-visit_date').first()
        if stories_visit:
            visits_info.append({
                'visit': stories_visit,
                'type': '1000 Stories',
                'date': stories_visit.visit_date
            })
        
        # Check NumeracyVisit
        numeracy_visit = numeracy_visits.filter(school=school).order_by('-visit_date').first()
        if numeracy_visit:
            visits_info.append({
                'visit': numeracy_visit,
                'type': 'Numeracy',
                'date': numeracy_visit.visit_date
            })
        
        # Find the most recent visit across all types
        if visits_info:
            most_recent = max(visits_info, key=lambda x: x['date'])
            last_visit = most_recent['visit']
            visit_type = most_recent['type']
            days_ago = (datetime.now().date() - last_visit.visit_date).days
            
            schools_data.append({
                'school_name': school.name,
                'school_type': school.type if school.type else 'Unknown',
                'school_id': school.school_id if school.school_id else school.id,
                'last_visit_date': last_visit.visit_date.strftime('%Y-%m-%d'),
                'days_ago': days_ago,
                'last_mentor': f"{last_visit.mentor.first_name} {last_visit.mentor.last_name}" if last_visit.mentor.first_name else last_visit.mentor.username,
                'visit_type': visit_type
            })
        else:
            schools_data.append({
                'school_name': school.name,
                'school_type': school.type if school.type else 'Unknown',
                'school_id': school.school_id if school.school_id else school.id,
                'last_visit_date': 'Never',
                'days_ago': 999,
                'last_mentor': 'N/A',
                'visit_type': 'N/A'
            })
    
    # Sort by days since last visit (most urgent first)
    schools_data.sort(key=lambda x: x['days_ago'], reverse=True)
    
    return schools_data

# Numeracy-specific chart functions (using existing generic functions)
def generate_numeracy_quality_rating_chart(numeracy_visits):
    """Generate quality rating chart for numeracy visits"""
    return generate_quality_rating_chart(numeracy_visits)

def generate_numeracy_school_visit_map(numeracy_visits):
    """Generate school visit map for numeracy visits"""
    # Get schools with numeracy visit counts
    schools_data = []
    
    # Get schools that have numeracy visits
    school_visits = School.objects.filter(numeracy_visits__in=numeracy_visits).annotate(
        visit_count=Count('numeracy_visits'),
        avg_quality=Avg('numeracy_visits__quality_rating')
    ).values('id', 'name', 'latitude', 'longitude', 'type', 'visit_count', 'avg_quality')
    
    # Create map data
    map_data = []
    for school in school_visits:
        if school['latitude'] and school['longitude']:
            map_data.append({
                'id': school['id'],
                'name': school['name'],
                'type': school['type'] or 'Unknown',
                'latitude': float(school['latitude']),
                'longitude': float(school['longitude']),
                'visit_count': school['visit_count'],
                'avg_quality': round(school['avg_quality'], 1) if school['avg_quality'] else 'N/A'
            })
    
    return json.dumps(map_data)

def generate_numeracy_tracker_accuracy_chart(numeracy_visits):
    """Generate tracker accuracy chart for numeracy visits"""
    # Calculate percentage of correct usage for numeracy-specific fields
    total_visits = numeracy_visits.count()
    if total_visits == 0:
        return json.dumps({})
    
    metrics = {
        'Numeracy Tracker': numeracy_visits.filter(numeracy_tracker_correct=True).count() / total_visits * 100,
        'Teaching Counting': numeracy_visits.filter(teaching_counting=True).count() / total_visits * 100,
        'Number Concepts': numeracy_visits.filter(teaching_number_concepts=True).count() / total_visits * 100,
        'Teaching Patterns': numeracy_visits.filter(teaching_patterns=True).count() / total_visits * 100,
        'Addition/Subtraction': numeracy_visits.filter(teaching_addition_subtraction=True).count() / total_visits * 100
    }
    
    # Format for chart display
    labels = list(metrics.keys())
    values = list(metrics.values())
    
    # Prepare chart data for radar chart
    chart_data = {
        'labels': labels,
        'datasets': [{
            'label': 'Teaching Areas (%)',
            'data': values,
            'backgroundColor': 'rgba(153, 102, 255, 0.2)',
            'borderColor': 'rgba(153, 102, 255, 1)',
            'pointBackgroundColor': 'rgba(153, 102, 255, 1)',
            'pointBorderColor': '#fff',
            'pointHoverBackgroundColor': '#fff',
            'pointHoverBorderColor': 'rgba(153, 102, 255, 1)'
        }]
    }
    
    return json.dumps(chart_data)

def get_recent_numeracy_submissions(numeracy_visits, limit=50):
    """Get recent numeracy visit submissions"""
    return numeracy_visits.order_by('-created_at').select_related('mentor', 'school')[:limit]

def get_recent_literacy_submissions(mentor_visits, limit=50):
    """
    Get recent literacy visit submissions
    
    Args:
        mentor_visits: QuerySet of MentorVisit objects
        limit: Maximum number of submissions to return
    
    Returns:
        QuerySet of recent MentorVisit submissions
    """
    return mentor_visits.select_related('mentor', 'school').order_by('-created_at')[:limit]

def get_recent_yebo_submissions(yebo_visits, limit=50):
    """
    Get recent Yebo visit submissions
    
    Args:
        yebo_visits: QuerySet of YeboVisit objects
        limit: Maximum number of submissions to return
    
    Returns:
        QuerySet of recent YeboVisit submissions
    """
    return yebo_visits.select_related('mentor', 'school').order_by('-created_at')[:limit]

def get_recent_thousand_stories_submissions(thousand_stories_visits, limit=50):
    """
    Get recent 1000 Stories visit submissions
    
    Args:
        thousand_stories_visits: QuerySet of ThousandStoriesVisit objects
        limit: Maximum number of submissions to return
    
    Returns:
        QuerySet of recent ThousandStoriesVisit submissions
    """
    return thousand_stories_visits.select_related('mentor', 'school').order_by('-created_at')[:limit]

def generate_yebo_quality_rating_chart(yebo_visits):
    """
    Generate chart data for Yebo afternoon session quality ratings distribution
    
    Args:
        yebo_visits: QuerySet of YeboVisit objects
    
    Returns:
        JSON-serialized chart data
    """
    # Count visits by afternoon session quality rating
    rating_counts = yebo_visits.values('afternoon_session_quality').annotate(
        count=Count('id')
    ).order_by('afternoon_session_quality')
    
    # Format for chart display
    labels = [f"Rating {item['afternoon_session_quality']}" for item in rating_counts]
    values = [item['count'] for item in rating_counts]
    
    # Generate a color gradient from red to green
    colors = []
    for i, rating in enumerate(rating_counts):
        r = max(0, int(255 * (1 - rating['afternoon_session_quality'] / 10)))
        g = max(0, int(255 * (rating['afternoon_session_quality'] / 10)))
        b = 0
        colors.append(f'rgba({r}, {g}, {b}, 0.7)')
    
    # Prepare chart data
    chart_data = {
        'labels': labels,
        'datasets': [{
            'label': 'Number of Visits',
            'data': values,
            'backgroundColor': colors,
            'borderColor': colors,
            'borderWidth': 1
        }]
    }
    
    return json.dumps(chart_data)

def generate_thousand_stories_quality_rating_chart(thousand_stories_visits):
    """
    Generate chart data for 1000 Stories story time quality ratings distribution
    
    Args:
        thousand_stories_visits: QuerySet of ThousandStoriesVisit objects
    
    Returns:
        JSON-serialized chart data
    """
    # Count visits by story time quality rating
    rating_counts = thousand_stories_visits.values('story_time_quality').annotate(
        count=Count('id')
    ).order_by('story_time_quality')
    
    # Format for chart display
    labels = [f"Rating {item['story_time_quality']}" for item in rating_counts]
    values = [item['count'] for item in rating_counts]
    
    # Generate a color gradient from red to green
    colors = []
    for i, rating in enumerate(rating_counts):
        r = max(0, int(255 * (1 - rating['story_time_quality'] / 10)))
        g = max(0, int(255 * (rating['story_time_quality'] / 10)))
        b = 0
        colors.append(f'rgba({r}, {g}, {b}, 0.7)')
    
    # Prepare chart data
    chart_data = {
        'labels': labels,
        'datasets': [{
            'label': 'Number of Visits',
            'data': values,
            'backgroundColor': colors,
            'borderColor': colors,
            'borderWidth': 1
        }]
    }
    
    return json.dumps(chart_data)