from django.urls import path 
from .import views 
from django.views.generic import TemplateView

urlpatterns = [
    path('', views.login_page, name="login"),
    path('login/', views.login_page, name="login"),
    path('dashboard/', views.dashboard, name="dashboard"),
    path('logout/', views.logout_view, name="logout"),
    path('demo/',TemplateView.as_view(template_name="base.html"), name="demo"),
 ]