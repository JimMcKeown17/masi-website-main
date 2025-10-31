from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from .models import MentorVisit, YeboVisit, ThousandStoriesVisit, NumeracyVisit, School
from .serializers import MentorVisitSerializer, YeboVisitSerializer, ThousandStoriesVisitSerializer, NumeracyVisitSerializer, MentorSerializer, SchoolSerializer, UserSerializer
from .authentication import ClerkAuthentication
from rest_framework.authentication import SessionAuthentication
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User

# MASI Literacy Visits
class MentorVisitListCreateAPIView(generics.ListCreateAPIView):
    """
    GET: List all mentor visits
    POST: Create new mentor visit
    
    Query Parameters:
    - time_filter: 7days, 30days, 90days, thisyear, all (default: all)
    - school: school ID
    - mentor: mentor user ID
    """
    queryset = MentorVisit.objects.all()
    serializer_class = MentorVisitSerializer
    authentication_classes = [SessionAuthentication, ClerkAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Apply filters based on query parameters"""
        queryset = MentorVisit.objects.all()
        
        # Time filter
        time_filter = self.request.query_params.get('time_filter', 'all')
        if time_filter == '7days':
            date_threshold = timezone.now().date() - timedelta(days=7)
            queryset = queryset.filter(visit_date__gte=date_threshold)
        elif time_filter == '30days':
            date_threshold = timezone.now().date() - timedelta(days=30)
            queryset = queryset.filter(visit_date__gte=date_threshold)
        elif time_filter == '90days':
            date_threshold = timezone.now().date() - timedelta(days=90)
            queryset = queryset.filter(visit_date__gte=date_threshold)
        elif time_filter == 'thisyear':
            year_start = timezone.now().date().replace(month=1, day=1)
            queryset = queryset.filter(visit_date__gte=year_start)
        
        # School filter
        school_id = self.request.query_params.get('school')
        if school_id:
            queryset = queryset.filter(school_id=school_id)
        
        # Mentor filter
        mentor_id = self.request.query_params.get('mentor')
        if mentor_id:
            queryset = queryset.filter(mentor_id=mentor_id)
        
        return queryset.order_by('-visit_date')

    def perform_create(self, serializer):
        # Automatically set the mentor to the authenticated user
        serializer.save(mentor=self.request.user)


class MentorVisitDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET: Retrieve a specific mentor visit
    PUT/PATCH: Update a mentor visit
    DELETE: Delete a mentor visit
    """
    queryset = MentorVisit.objects.all()
    serializer_class = MentorVisitSerializer
    authentication_classes = [SessionAuthentication, ClerkAuthentication]
    permission_classes = [permissions.IsAuthenticated]


# Yebo Visits
class YeboVisitListCreateAPIView(generics.ListCreateAPIView):
    
    """
    GET: List all Yebo mentor visits
    POST: Create new Yebo mentor visit
    
    Query Parameters:
    - time_filter: 7days, 30days, 90days, thisyear, all (default: all)
    - school: school ID
    - mentor: mentor user ID
    """
    
    queryset = YeboVisit.objects.all()
    serializer_class = YeboVisitSerializer
    authentication_classes = [SessionAuthentication, ClerkAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Apply filters based on query parameters"""
        queryset = YeboVisit.objects.all()
        
        # Time filter
        time_filter = self.request.query_params.get('time_filter', 'all')
        if time_filter == '7days':
            date_threshold = timezone.now().date() - timedelta(days=7)
            queryset = queryset.filter(visit_date__gte=date_threshold)
        elif time_filter == '30days':
            date_threshold = timezone.now().date() - timedelta(days=30)
            queryset = queryset.filter(visit_date__gte=date_threshold)
        elif time_filter == '90days':
            date_threshold = timezone.now().date() - timedelta(days=90)
            queryset = queryset.filter(visit_date__gte=date_threshold)
        elif time_filter == 'thisyear':
            year_start = timezone.now().date().replace(month=1, day=1)
            queryset = queryset.filter(visit_date__gte=year_start)
        
        # School filter
        school_id = self.request.query_params.get('school')
        if school_id:
            queryset = queryset.filter(school_id=school_id)
        
        # Mentor filter
        mentor_id = self.request.query_params.get('mentor')
        if mentor_id:
            queryset = queryset.filter(mentor_id=mentor_id)
        
        return queryset.order_by('-visit_date')
    
    def perform_create(self, serializer):
        serializer.save(mentor=self.request.user)


class YeboVisitDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = YeboVisit.objects.all()
    serializer_class = YeboVisitSerializer
    authentication_classes = [SessionAuthentication, ClerkAuthentication]
    permission_classes = [permissions.IsAuthenticated]


# 1000 Stories Visits
class ThousandStoriesVisitListCreateAPIView(generics.ListCreateAPIView):
    
    """
    GET: List all Thousand Stories mentor visits
    POST: Create new Thousand Stories mentor visit
    
    Query Parameters:
    - time_filter: 7days, 30days, 90days, thisyear, all (default: all)
    - school: school ID
    - mentor: mentor user ID
    """
    
    queryset = ThousandStoriesVisit.objects.all()
    serializer_class = ThousandStoriesVisitSerializer
    authentication_classes = [SessionAuthentication, ClerkAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Apply filters based on query parameters"""
        queryset = ThousandStoriesVisit.objects.all()
        
        # Time filter
        time_filter = self.request.query_params.get('time_filter', 'all')
        if time_filter == '7days':
            date_threshold = timezone.now().date() - timedelta(days=7)
            queryset = queryset.filter(visit_date__gte=date_threshold)
        elif time_filter == '30days':
            date_threshold = timezone.now().date() - timedelta(days=30)
            queryset = queryset.filter(visit_date__gte=date_threshold)
        elif time_filter == '90days':
            date_threshold = timezone.now().date() - timedelta(days=90)
            queryset = queryset.filter(visit_date__gte=date_threshold)
        elif time_filter == 'thisyear':
            year_start = timezone.now().date().replace(month=1, day=1)
            queryset = queryset.filter(visit_date__gte=year_start)
        
        # School filter
        school_id = self.request.query_params.get('school')
        if school_id:
            queryset = queryset.filter(school_id=school_id)
        
        # Mentor filter
        mentor_id = self.request.query_params.get('mentor')
        if mentor_id:
            queryset = queryset.filter(mentor_id=mentor_id)
        
        return queryset.order_by('-visit_date')
    
    def perform_create(self, serializer):
        serializer.save(mentor=self.request.user)


class ThousandStoriesVisitDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ThousandStoriesVisit.objects.all()
    serializer_class = ThousandStoriesVisitSerializer
    authentication_classes = [SessionAuthentication, ClerkAuthentication]
    permission_classes = [permissions.IsAuthenticated]


# Numeracy Visits
class NumeracyVisitListCreateAPIView(generics.ListCreateAPIView):
    
    """
    GET: List all Numeracy mentor visits
    POST: Create new Numeracy mentor visit
    
    Query Parameters:
    - time_filter: 7days, 30days, 90days, thisyear, all (default: all)
    - school: school ID
    - mentor: mentor user ID
    """
    
    queryset = NumeracyVisit.objects.all()
    serializer_class = NumeracyVisitSerializer
    authentication_classes = [SessionAuthentication, ClerkAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Apply filters based on query parameters"""
        queryset = NumeracyVisit.objects.all()
        
        # Time filter
        time_filter = self.request.query_params.get('time_filter', 'all')
        if time_filter == '7days':
            date_threshold = timezone.now().date() - timedelta(days=7)
            queryset = queryset.filter(visit_date__gte=date_threshold)
        elif time_filter == '30days':
            date_threshold = timezone.now().date() - timedelta(days=30)
            queryset = queryset.filter(visit_date__gte=date_threshold)
        elif time_filter == '90days':
            date_threshold = timezone.now().date() - timedelta(days=90)
            queryset = queryset.filter(visit_date__gte=date_threshold)
        elif time_filter == 'thisyear':
            year_start = timezone.now().date().replace(month=1, day=1)
            queryset = queryset.filter(visit_date__gte=year_start)
        
        # School filter
        school_id = self.request.query_params.get('school')
        if school_id:
            queryset = queryset.filter(school_id=school_id)
        
        # Mentor filter
        mentor_id = self.request.query_params.get('mentor')
        if mentor_id:
            queryset = queryset.filter(mentor_id=mentor_id)
        
        return queryset.order_by('-visit_date')
    
    def perform_create(self, serializer):
        serializer.save(mentor=self.request.user)


class NumeracyVisitDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = NumeracyVisit.objects.all()
    serializer_class = NumeracyVisitSerializer
    authentication_classes = [SessionAuthentication, ClerkAuthentication]
    permission_classes = [permissions.IsAuthenticated]

class SchoolListAPIView(generics.ListAPIView):
    """
    Get list of all active schools.
    """
    queryset = School.objects.all().order_by('name')
    serializer_class = SchoolSerializer
    authentication_classes = [SessionAuthentication, ClerkAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
class MentorListAPIView(generics.ListAPIView):
    """
    Get list of all mentors who have submitted visits.
    Returns users who have submitted any type of visit (Literacy, Yebo, 1000 Stories, or Numeracy).
    """
    serializer_class = UserSerializer
    authentication_classes = [SessionAuthentication, ClerkAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Get all users who have submitted at least one visit"""
        # Collect all mentor IDs from all visit types
        mentor_ids = set()
        mentor_ids.update(MentorVisit.objects.values_list('mentor_id', flat=True))
        mentor_ids.update(YeboVisit.objects.values_list('mentor_id', flat=True))
        mentor_ids.update(ThousandStoriesVisit.objects.values_list('mentor_id', flat=True))
        mentor_ids.update(NumeracyVisit.objects.values_list('mentor_id', flat=True))
        
        # Return users ordered by name
        return User.objects.filter(id__in=mentor_ids).distinct().order_by('first_name', 'last_name')


@api_view(['GET'])
@authentication_classes([ClerkAuthentication])
@permission_classes([permissions.IsAuthenticated])
def api_info(request):
    return Response({
        'message': 'MASI API v1.0',
        'endpoints': {
            'mentor_visits': '/api/mentor-visits/',
            'mentor_visit_detail': '/api/mentor-visits/{id}/',
            'yebo_visits': '/api/yebo-visits/',
            'yebo_visit_detail': '/api/yebo-visits/{id}/',
            'thousand_stories_visits': '/api/thousand-stories-visits/',
            'thousand_stories_visit_detail': '/api/thousand-stories-visits/{id}/',
            'numeracy_visits': '/api/numeracy-visits/',
            'numeracy_visit_detail': '/api/numeracy-visits/{id}/',
            'api_info': '/api/info/',
            'me': '/api/me/'
        }
    })

@api_view(["GET"])
@authentication_classes([ClerkAuthentication])
@permission_classes([permissions.IsAuthenticated])
def me(request):
    user = request.user
    role = getattr(user.profile, 'role', 'VIEWER') if hasattr(user, 'profile') else 'VIEWER'
    
    return Response({
        "email": user.email,
        "role": role,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "username": user.username,
    })
    
