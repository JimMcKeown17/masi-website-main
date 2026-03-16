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
    path('recent-visits/', views.recent_visits, name='recent_visits'),

    path("me/", views.me, name="me"),

    # ETL preview
    path('etl-status/', views.etl_status, name='etl_status'),
    path('etl-preview/<str:table_name>/', views.etl_preview, name='etl_preview'),

    # Youth sessions dashboard
    path('youth-sessions/summary/', views.youth_sessions_summary, name='youth_sessions_summary'),
    path('youth-sessions/daily-activity/', views.youth_sessions_daily_activity, name='youth_sessions_daily_activity'),
    path('youth-sessions/youth-heatmap/', views.youth_sessions_heatmap, name='youth_sessions_heatmap'),
    path('youth-sessions/inactive-youth/', views.youth_sessions_inactive, name='youth_sessions_inactive'),
    path('youth-sessions/school-coverage/', views.youth_sessions_school_coverage, name='youth_sessions_school_coverage'),
    path('youth-sessions/youth-detail/<str:youth_uid>/', views.youth_sessions_detail, name='youth_sessions_detail'),
    path('youth-sessions/lookups/', views.youth_sessions_lookups, name='youth_sessions_lookups'),
]