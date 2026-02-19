from django.contrib import admin
from django.contrib.auth.hashers import make_password
from .models import Department, Worker, Project, ProjectMember



@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "email")

    def save_model(self, request, obj, form, change):
        # hash password only when changed or created
        if not change or "password" in form.changed_data:
            obj.password = make_password(obj.password)
        super().save_model(request, obj, form, change)


@admin.register(Worker)
class WorkerAdmin(admin.ModelAdmin):
    list_display = ("name", "worker_type", "department", "posting")
    list_filter = ("worker_type", "department")
    search_fields = ("name",)

class ProjectMemberInline(admin.TabularInline):
    model = ProjectMember
    extra = 1



class ProjectMemberInline(admin.TabularInline):
    model = ProjectMember
    extra = 1

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "worker":
            if request.resolver_match.kwargs.get("object_id"):
                project_id = request.resolver_match.kwargs.get("object_id")
                project = Project.objects.filter(id=project_id).first()
                if project:
                    kwargs["queryset"] = Worker.objects.filter(department=project.department)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):

    list_display = ("title", "department", "category", "status", "work_type", "amount")
    list_filter = ("category", "status", "work_type", "department")
    search_fields = ("title",)

    inlines = [ProjectMemberInline]


@admin.register(ProjectMember)
class ProjectMemberAdmin(admin.ModelAdmin):
    list_display = ("project", "worker", "contribution")
    list_filter = ("contribution",)
