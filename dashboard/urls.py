from django.urls import path 
from .import views 
from django.views.generic import TemplateView

urlpatterns = [
    path('', views.login_page, name="login"),
    path('login/', views.login_page, name="login"),
    
    path('', views.base, name="base"),

    path('index/', views.index, name="index"),
    path('team/', views.team, name="team"),
    path('client/', views.client, name="client"),
    path('company/', views.company, name="company"),
    path('academics/', views.academics, name="academics"),
    path('internship/', views.internship, name="internship"),
    path('add-team/', views.add_team, name="add_team"),
    path('add-project/', views.add_project, name="add_project"),
 ]