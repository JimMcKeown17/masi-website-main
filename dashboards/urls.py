from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_main, name='dashboard_main'),
    path('mentor-visits/', views.mentor_dashboard, name='mentor_dashboard'),
    path('mentor-visits/add/', views.mentor_visit_form, name='mentor_visit_form'),
]