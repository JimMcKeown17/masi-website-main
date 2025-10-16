from django.shortcuts import render
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from .models import MentorVisit
from .serializers import MentorVisitSerializer
from .authentication import ClerkAuthentication

# Create your views here.


# Regular API views for Django users (keep existing authentication)
class MentorVisitListAPIView(generics.ListAPIView):
    """
    API endpoint to retrieve all mentor visits.
    Uses Django's default authentication.
    """
    queryset = MentorVisit.objects.all()
    serializer_class = MentorVisitSerializer
    permission_classes = [permissions.IsAuthenticated]
    # No authentication_classes specified = uses default Django auth


class MentorVisitDetailAPIView(generics.RetrieveAPIView):
    """
    API endpoint to retrieve a specific mentor visit by ID.
    Uses Django's default authentication.
    """
    queryset = MentorVisit.objects.all()
    serializer_class = MentorVisitSerializer
    permission_classes = [permissions.IsAuthenticated]
    # No authentication_classes specified = uses default Django auth


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def api_info(request):
    """
    Simple API info endpoint - uses Django's default authentication
    """
    return Response({
        'message': 'MASI API v1.0',
        'endpoints': {
            'mentor_visits': '/api/mentor-visits/',
            'mentor_visit_detail': '/api/mentor-visits/{id}/',
            'api_info': '/api/info/',
            'me': '/api/me/'
        }
    })
    

# NextJS-specific endpoint with Clerk authentication
@api_view(["GET"])
@authentication_classes([ClerkAuthentication])  # Only this endpoint uses Clerk
@permission_classes([permissions.IsAuthenticated])
def me(request):
    user = request.user
    # Get role from UserProfile if it exists, otherwise default
    role = getattr(user.profile, 'job_title', 'viewer') if hasattr(user, 'profile') else 'viewer'
    
    return Response({
        "email": user.email,
        "role": role,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "username": user.username
    })
