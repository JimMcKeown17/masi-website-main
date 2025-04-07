from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_main, name='dashboard_main'),
    path('youth-dashboard/', views.youth_dashboard, name='youth_dashboard'),
    path('mentor-dashboard/', views.mentor_dashboard, name='mentor_dashboard'),
    path('mentor-visit-form/', views.mentor_visit_form, name='mentor_visit_form'),
    path('airtable-debug/', views.airtable_debug, name='airtable_debug'),  # Debug tool

]