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
def dashboard(request):

    dept_id = request.session.get("department_id")
    if not dept_id:
        return redirect("login")

    dept = Department.objects.get(id=dept_id)

    workers = dept.workers.all().order_by("worker_type", "name")
    projects = dept.projects.prefetch_related("members__worker").all().order_by("-start_date")

    project_data = []

    for project in projects:
        payments = calculate_project_payments(project)

        member_list = []
        for m in project.members.all():
            member_list.append({
                "name": m.worker.name,
                "role": m.get_contribution_display(),
                "payment": payments.get(m.id) if project.amount else None
            })

        project_data.append({
            "project": project,
            "members": member_list
        })

    context = {
        "department": dept,
        "worker_count": workers.count(),
        "project_count": projects.count(),
        "workers": workers,
        "projects": project_data,
    }

    return render(request, "dashboard.html", context)




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

