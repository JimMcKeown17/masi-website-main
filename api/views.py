from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from .models import MentorVisit, YeboVisit, ThousandStoriesVisit, NumeracyVisit
from .serializers import MentorVisitSerializer, YeboVisitSerializer, ThousandStoriesVisitSerializer, NumeracyVisitSerializer
from .authentication import ClerkAuthentication
from rest_framework.authentication import SessionAuthentication

# MASI Literacy Visits
class MentorVisitListCreateAPIView(generics.ListCreateAPIView):
    """
    GET: List all mentor visits
    POST: Create new mentor visit
    """
    queryset = MentorVisit.objects.all()
    serializer_class = MentorVisitSerializer
    authentication_classes = [SessionAuthentication, ClerkAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
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
    queryset = YeboVisit.objects.all()
    serializer_class = YeboVisitSerializer
    authentication_classes = [SessionAuthentication, ClerkAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    def perform_create(self, serializer):
        serializer.save(mentor=self.request.user)


class YeboVisitDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = YeboVisit.objects.all()
    serializer_class = YeboVisitSerializer
    authentication_classes = [SessionAuthentication, ClerkAuthentication]
    permission_classes = [permissions.IsAuthenticated]


# 1000 Stories Visits
class ThousandStoriesVisitListCreateAPIView(generics.ListCreateAPIView):
    queryset = ThousandStoriesVisit.objects.all()
    serializer_class = ThousandStoriesVisitSerializer
    authentication_classes = [SessionAuthentication, ClerkAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    def perform_create(self, serializer):
        serializer.save(mentor=self.request.user)


class ThousandStoriesVisitDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ThousandStoriesVisit.objects.all()
    serializer_class = ThousandStoriesVisitSerializer
    authentication_classes = [SessionAuthentication, ClerkAuthentication]
    permission_classes = [permissions.IsAuthenticated]


# Numeracy Visits
class NumeracyVisitListCreateAPIView(generics.ListCreateAPIView):
    queryset = NumeracyVisit.objects.all()
    serializer_class = NumeracyVisitSerializer
    authentication_classes = [SessionAuthentication, ClerkAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    
    def perform_create(self, serializer):
        serializer.save(mentor=self.request.user)


class NumeracyVisitDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = NumeracyVisit.objects.all()
    serializer_class = NumeracyVisitSerializer
    authentication_classes = [SessionAuthentication, ClerkAuthentication]
    permission_classes = [permissions.IsAuthenticated]


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