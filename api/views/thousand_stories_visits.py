from rest_framework import generics, permissions
from rest_framework.authentication import SessionAuthentication
from django.utils import timezone
from datetime import timedelta
from ..models import ThousandStoriesVisit
from ..serializers import ThousandStoriesVisitSerializer
from ..authentication import ClerkAuthentication


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

