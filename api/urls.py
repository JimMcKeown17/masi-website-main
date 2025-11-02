from django.urls import path
from . import views

app_name = 'api'

urlpatterns = [
    path('info/', views.api_info, name='api_info'),
    
    # MASI Literacy
    path('mentor-visits/', views.MentorVisitListCreateAPIView.as_view(), name='mentor_visits'),
    path('mentor-visits/<int:pk>/', views.MentorVisitDetailAPIView.as_view(), name='mentor_visit_detail'),
    
    # Yebo
    path('yebo-visits/', views.YeboVisitListCreateAPIView.as_view(), name='yebo_visits'),
    path('yebo-visits/<int:pk>/', views.YeboVisitDetailAPIView.as_view(), name='yebo_visit_detail'),
    
    # 1000 Stories
    path('thousand-stories-visits/', views.ThousandStoriesVisitListCreateAPIView.as_view(), name='thousand_stories_visits'),
    path('thousand-stories-visits/<int:pk>/', views.ThousandStoriesVisitDetailAPIView.as_view(), name='thousand_stories_visit_detail'),
    
    # Numeracy
    path('numeracy-visits/', views.NumeracyVisitListCreateAPIView.as_view(), name='numeracy_visits'),
    path('numeracy-visits/<int:pk>/', views.NumeracyVisitDetailAPIView.as_view(), name='numeracy_visit_detail'),
    
    # Helper endpoints
    path('mentors/', views.MentorListAPIView.as_view(), name='mentors_list'),
    path('schools/', views.SchoolListAPIView.as_view(), name='schools_list'),
    path('dashboard-summary/', views.dashboard_summary, name='dashboard_summary'),
    
    path("me/", views.me, name="me"),
]