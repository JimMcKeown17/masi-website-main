from django.shortcuts import render
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from .models import MentorVisit
from .serializers import MentorVisitSerializer


# Create your views here.


class MentorVisitListAPIView(generics.ListAPIView):
    """
    API endpoint to retrieve all mentor visits.
    Requires authentication.
    """
    queryset = MentorVisit.objects.all()
    serializer_class = MentorVisitSerializer
    permission_classes = [permissions.IsAuthenticated]


class MentorVisitDetailAPIView(generics.RetrieveAPIView):
    """
    API endpoint to retrieve a specific mentor visit by ID.
    Requires authentication.
    """
    queryset = MentorVisit.objects.all()
    serializer_class = MentorVisitSerializer
    permission_classes = [permissions.IsAuthenticated]


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def api_info(request):
    """
    Simple API info endpoint
    """
    return Response({
        'message': 'MASI API v1.0',
        'endpoints': {
            'mentor_visits': '/api/mentor-visits/',
            'mentor_visit_detail': '/api/mentor-visits/{id}/',
            'api_info': '/api/info/'
        }
    })
