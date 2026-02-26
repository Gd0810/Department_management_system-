from django.urls import path 
from .import views 
from django.views.generic import TemplateView

urlpatterns = [
    path('', views.login_page, name="login"),          # ONLY login
    path('dashboard/', views.base, name="base"),       # dashboard layout

    path('index/', views.index, name="index"),
    path('team/', views.team, name="team"),
    path('client/', views.client, name="client"),
    path('company/', views.company, name="company"),
    path('academics/', views.academics, name="academics"),
    path('internship/', views.internship, name="internship"),
    path('add-team/', views.add_team, name="add_team"),
    path('add-project/', views.add_project, name="add_project"),
    path('assign-project/', views.assign_project, name="assign_project"),
    path('project/<int:project_id>/', views.project_detail, name="project_detail"),
    path('api/projects/<str:category_key>/', views.category_projects_api, name="category_projects_api"),
    path('logout/', views.logout_view, name="logout"),
    path('test/', TemplateView.as_view(template_name='test.html'), name="test"),
 ]
