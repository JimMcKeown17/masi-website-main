from django.urls import path
from . import views

app_name = 'api'

urlpatterns = [
    path('info/', views.api_info, name='api_info'),
    path('mentor-visits/', views.MentorVisitListAPIView.as_view(), name='mentor_visits_list'),
    path('mentor-visits/<int:pk>/', views.MentorVisitDetailAPIView.as_view(), name='mentor_visit_detail'),
    path("me/", views.me, name="me"),
] 