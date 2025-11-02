from rest_framework import generics, permissions
from rest_framework.authentication import SessionAuthentication
from django.contrib.auth.models import User
from ..models import MentorVisit, YeboVisit, ThousandStoriesVisit, NumeracyVisit, School
from ..serializers import SchoolSerializer, UserSerializer
from ..authentication import ClerkAuthentication


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

