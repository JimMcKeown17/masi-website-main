from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('debug-social/', views.debug_social, name='debug_social'),
]