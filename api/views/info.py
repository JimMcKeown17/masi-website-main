from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from ..authentication import ClerkAuthentication


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

