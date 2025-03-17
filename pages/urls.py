from django.urls import path
from . import views

app_name = 'pages'

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('children/', views.children, name='children'),
    path('youth/', views.youth, name='youth'),
    path('impact/', views.impact, name='impact'),
    path('data/', views.data, name='data'),
    path('donate/', views.donate, name='donate'),
    path('top-learner/', views.top_learner, name='top_learner'),
    path('apply/', views.apply, name='apply'),
    path('where/', views.where, name='where'),
    path('masi_map_satellite/', views.masi_map_satellite, name='masi_map_satellite'),
]