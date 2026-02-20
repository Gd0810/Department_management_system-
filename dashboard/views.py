from django.shortcuts import render, redirect
from .models import Department
from django.contrib.auth.hashers import check_password
from collections import defaultdict
from decimal import Decimal



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
from django.shortcuts import render
from .models import Department, Worker, Project


def get_department(request):
    dept_id = request.session.get("department_id")
    return Department.objects.get(id=dept_id)


def base(request):
    return render(request, "base.html")


def index(request):
    dept = get_department(request)

    context = {
        "department": dept,
        "workers": dept.workers.count(),
        "projects": dept.projects.count(),
    }
    return render(request, "partials/index.html", context)


def team(request):
    dept = get_department(request)
    workers = dept.workers.all()

    return render(request, "partials/team.html", {"workers": workers})


def client(request):
    dept = get_department(request)
    projects = dept.projects.filter(category="client")

    return render(request, "partials/client.html", {"projects": projects})


def company(request):
    dept = get_department(request)
    projects = dept.projects.filter(category="company")

    return render(request, "partials/company.html", {"projects": projects})


def academics(request):
    dept = get_department(request)
    projects = dept.projects.filter(category="academy")

    return render(request, "partials/academics.html", {"projects": projects})


def internship(request):
    dept = get_department(request)
    projects = dept.projects.filter(category="internship")

    return render(request, "partials/internship.html", {"projects": projects})


def add_team(request):
    return render(request, "partials/add_team.html")


def add_project(request):
    return render(request, "partials/add_project.html")




# =========================
# LOGOUT
# =========================
def logout_view(request):
    request.session.flush()
    return redirect("login")

def calculate_project_payments(project):

    if not project.amount:
        return []

    members = list(project.members.select_related("worker"))

    gold = [m for m in members if m.contribution == "gold"]
    silver = [m for m in members if m.contribution == "silver"]
    copper = [m for m in members if m.contribution == "copper"]

    total_amount = Decimal(project.amount)

    payments = {}

    # Only gold → equal
    if gold and not silver and not copper:
        share = total_amount / len(gold)
        for m in gold:
            payments[m.id] = share

    # Gold + Silver
    elif gold and silver and not copper:
        gold_total = total_amount * Decimal("0.60")
        silver_total = total_amount * Decimal("0.40")

        for m in gold:
            payments[m.id] = gold_total / len(gold)

        for m in silver:
            payments[m.id] = silver_total / len(silver)

    # Gold + Copper
    elif gold and copper and not silver:
        gold_total = total_amount * Decimal("0.70")
        copper_total = total_amount * Decimal("0.30")

        for m in gold:
            payments[m.id] = gold_total / len(gold)

        for m in copper:
            payments[m.id] = copper_total / len(copper)

    # Fallback weight system
    else:
        weight_map = {"gold":3, "silver":2, "copper":1}
        total_weight = sum(weight_map[m.contribution] for m in members)

        for m in members:
            share = (Decimal(weight_map[m.contribution]) / Decimal(total_weight)) * total_amount
            payments[m.id] = share

    return payments

