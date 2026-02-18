from django.shortcuts import render, redirect
from .models import Department
from django.contrib.auth.hashers import check_password


# =========================
# LOGIN PAGE
# =========================
def login_page(request):

    if request.session.get("department_id"):
        return redirect("dashboard")

    error = None

    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        try:
            dept = Department.objects.get(email=email)

            if check_password(password, dept.password):
                request.session["department_id"] = dept.id
                return redirect("dashboard")
            else:
                error = "Invalid password"

        except Department.DoesNotExist:
            error = "Department not found"

    return render(request, "login.html", {"error": error})


# =========================
# DASHBOARD
# =========================
def dashboard(request):

    dept_id = request.session.get("department_id")

    if not dept_id:
        return redirect("login")

    dept = Department.objects.get(id=dept_id)

    workers = dept.workers.all().order_by("worker_type", "name")
    projects = dept.projects.prefetch_related("members__worker").all().order_by("-start_date")

    context = {
        "department": dept,
        "worker_count": workers.count(),
        "project_count": projects.count(),
        "workers": workers,
        "projects": projects,
    }

    return render(request, "index.html", context)



# =========================
# LOGOUT
# =========================
def logout_view(request):
    request.session.flush()
    return redirect("login")
