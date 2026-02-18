from django.contrib import admin
from .models import Department, Worker, Project, ProjectMember, distribute_project_payment
from django.contrib.auth.hashers import make_password



@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "email")

    def save_model(self, request, obj, form, change):
        if not change or "password" in form.changed_data:
            obj.password = make_password(obj.password)
        super().save_model(request, obj, form, change)

@admin.register(Worker)
class WorkerAdmin(admin.ModelAdmin):
    list_display = ("name", "worker_type", "department", "posting")
    list_filter = ("worker_type", "department")
    search_fields = ("name",)
