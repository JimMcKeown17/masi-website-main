from django.urls import path
from . import views

app_name = 'dashboards'

urlpatterns = [
    path('', views.dashboard_home, name='home'),
    path('mentor-visit/', views.mentor_visit, name='mentor_visit'),
    # Add more dashboard paths as needed
]