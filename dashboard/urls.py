from django.urls import path 
from .import views 
from django.views.generic import TemplateView

urlpatterns = [
    path('', views.login_page, name="login"),          # ONLY login
    path('dashboard/', views.base, name="base"),       # dashboard layout

    path('index/', views.index, name="index"),
    path('team/', views.team, name="team"),
    path('worker/<int:worker_id>/', views.worker_detail, name="worker_detail"),
    path('worker/<int:worker_id>/edit/', views.edit_worker, name="edit_worker"),
    path('worker/<int:worker_id>/delete/', views.delete_worker, name="delete_worker"),
    path('client/', views.client, name="client"),
    path('company/', views.company, name="company"),
    path('academics/', views.academics, name="academics"),
    path('internship/', views.internship, name="internship"),
    path('add-team/', views.add_team, name="add_team"),
    path('add-project/', views.add_project, name="add_project"),
    path('assign-project/', views.assign_project, name="assign_project"),
    path('project/<int:project_id>/', views.project_detail, name="project_detail"),
    path('project/<int:project_id>/edit/', views.edit_project, name="edit_project"),
    path('project/<int:project_id>/delete/', views.delete_project, name="delete_project"),
    path('api/projects/<str:category_key>/', views.category_projects_api, name="category_projects_api"),
    path('reports/projects/<str:category_key>/<str:file_format>/', views.project_category_report, name="project_category_report"),
    path('reports/projects/listing/<str:category_key>/<str:file_format>/', views.project_listing_report, name="project_listing_report"),
    path('logout/', views.logout_view, name="logout"),
    path('test/', TemplateView.as_view(template_name='test.html'), name="test"),
 ]
