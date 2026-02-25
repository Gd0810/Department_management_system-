from django.shortcuts import render, redirect
from .models import Department
from django.contrib.auth.hashers import check_password
from django.views.decorators.http import require_http_methods
from collections import defaultdict
from decimal import Decimal
from datetime import date
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Count, Sum, Value, DecimalField
from django.db.models.functions import Coalesce, TruncMonth
from django.contrib import messages



# =========================
# LOGIN PAGE
# =========================



@require_http_methods(["GET", "POST"])
def login_page(request):

    # Already logged in → go dashboard
    if request.session.get("department_id"):
        return redirect("base")

    error = None

    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "").strip()

        # basic validation
        if not email or not password:
            error = "Please enter email and password"
        else:
            dept = Department.objects.filter(email=email).first()

            if not dept:
                error = "Department not found"
            elif not check_password(password, dept.password):
                error = "Invalid password"
            else:
                # create secure session
                request.session.flush()  # remove old session
                request.session["department_id"] = dept.id
                request.session.set_expiry(60 * 60 * 8)  # 8 hours login

                return redirect("base")

    return render(request, "login.html", {"error": error})


# =========================
# DASHBOARD
# =========================
from django.shortcuts import render
from .models import Department, Worker, Project, ProjectMember


def get_department(request):
    dept_id = request.session.get("department_id")
    return Department.objects.get(id=dept_id)


def base(request):
     if not request.session.get("department_id"):
        return redirect("login")
     dept = get_department(request)
     initials = "".join([part[0] for part in dept.name.split()[:2]]).upper() if dept.name else "D"
     context = {
         "department": dept,
         "department_initials": initials,
     }
     return render(request, "base.html", context)


def index(request):
    if not request.session.get("department_id"):
        return redirect("login")
    dept = get_department(request)

    context = {
        "department": dept,
        "workers": dept.workers.count(),
        "projects": dept.projects.count(),
    }
    return render(request, "partials/index.html", context)


def team(request):
    if not request.session.get("department_id"):
        return redirect("login")
    dept = get_department(request)
    workers = dept.workers.all()

    return render(request, "partials/team.html", {"workers": workers})


def client(request):
    return _render_project_category_dashboard(request, "client", "partials/client.html")


def company(request):
    return _render_project_category_dashboard(request, "company", "partials/company.html")


def academics(request):
    return _render_project_category_dashboard(request, "academy", "partials/academics.html")


def internship(request):
    return _render_project_category_dashboard(request, "internship", "partials/internship.html")


def _build_project_category_dashboard_context(dept, category_key):
    category_lookup = dict(Project.PROJECT_CATEGORY)
    category_label = category_lookup.get(category_key, category_key.title())
    category_label_plural = f"{category_label}s"

    projects = (
        dept.projects.filter(category=category_key)
        .prefetch_related("members__worker")
        .order_by("-start_date", "-id")
    )
    all_projects = dept.projects.all()

    category_income_total = (
        projects.aggregate(
            total=Coalesce(
                Sum("amount"),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )["total"]
        or Decimal("0.00")
    )
    overall_income_total = (
        all_projects.aggregate(
            total=Coalesce(
                Sum("amount"),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )["total"]
        or Decimal("0.00")
    )
    category_project_total = projects.count()
    overall_project_total = all_projects.count()

    income_percentage = (
        float((category_income_total / overall_income_total) * Decimal("100"))
        if overall_income_total > 0
        else 0.0
    )
    project_percentage = (
        (category_project_total / overall_project_total) * 100.0
        if overall_project_total > 0
        else 0.0
    )

    today = date.today()
    month_keys = []
    year, month = today.year, today.month
    for _ in range(12):
        month_keys.append((year, month))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    month_keys.reverse()

    monthly_labels = [date(y, m, 1).strftime("%b %Y") for y, m in month_keys]
    monthly_income = [0.0] * len(month_keys)
    monthly_project_count = [0] * len(month_keys)

    monthly_rows = (
        projects.annotate(month_bucket=TruncMonth("start_date"))
        .values("month_bucket")
        .annotate(
            total_income=Coalesce(
                Sum("amount"),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
            total_projects=Count("id"),
        )
        .order_by("month_bucket")
    )
    monthly_lookup = {
        (row["month_bucket"].year, row["month_bucket"].month): row for row in monthly_rows
    }
    for idx, key in enumerate(month_keys):
        row = monthly_lookup.get(key)
        if row:
            monthly_income[idx] = float(row["total_income"] or 0)
            monthly_project_count[idx] = int(row["total_projects"] or 0)

    top_projects_qs = (
        projects.annotate(
            income_value=Coalesce(
                "amount",
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )
        .order_by("-income_value", "title")
        .values("title", "income_value")[:5]
    )
    top_project_labels = [row["title"] for row in top_projects_qs]
    top_project_income = [float(row["income_value"] or 0) for row in top_projects_qs]

    top_members_count_qs = (
        ProjectMember.objects.filter(project__department=dept, project__category=category_key)
        .values("worker_id", "worker__name")
        .annotate(project_count=Count("project_id", distinct=True))
        .order_by("-project_count", "worker__name")[:5]
    )
    top_member_project_labels = [row["worker__name"] for row in top_members_count_qs]
    top_member_project_values = [int(row["project_count"]) for row in top_members_count_qs]

    member_income_map = defaultdict(Decimal)
    for project in projects:
        payments = calculate_project_payments(project)
        for member in project.members.all():
            member_income_map[member.worker.name] += payments.get(member.id, Decimal("0.00"))

    top_member_income_pairs = sorted(
        member_income_map.items(),
        key=lambda entry: entry[1],
        reverse=True,
    )[:5]
    top_member_income_labels = [item[0] for item in top_member_income_pairs]
    top_member_income_values = [float(item[1]) for item in top_member_income_pairs]

    context = {
        "category_key": category_key,
        "category_label": category_label,
        "category_label_plural": category_label_plural,
        "projects": projects,
        "category_income_total": float(category_income_total),
        "category_project_total": category_project_total,
        "income_percentage": round(income_percentage, 2),
        "project_percentage": round(project_percentage, 2),
        "monthly_labels": monthly_labels,
        "monthly_income": monthly_income,
        "monthly_project_count": monthly_project_count,
        "top_project_labels": top_project_labels,
        "top_project_income": top_project_income,
        "top_member_project_labels": top_member_project_labels,
        "top_member_project_values": top_member_project_values,
        "top_member_income_labels": top_member_income_labels,
        "top_member_income_values": top_member_income_values,
    }
    return context


def _render_project_category_dashboard(request, category_key, template_name):
    if not request.session.get("department_id"):
        return redirect("login")
    dept = get_department(request)
    context = _build_project_category_dashboard_context(dept, category_key)
    return render(request, template_name, context)


def add_team(request):
    if not request.session.get("department_id"):
        return redirect("login")
    dept = get_department(request)
    context = {"form_data": {}}

    if request.method == "POST":
        worker_type = request.POST.get("worker_type", "").strip()
        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip().lower()
        date_of_join = request.POST.get("date_of_join", "").strip()
        posting = request.POST.get("posting", "").strip()
        department_role = request.POST.get("department_role", "").strip()
        image = request.FILES.get("image")
        context["form_data"] = {
            "worker_type": worker_type,
            "name": name,
            "email": email,
            "date_of_join": date_of_join,
            "posting": posting,
            "department_role": department_role,
        }

        valid_worker_types = {choice[0] for choice in Worker.WORKER_TYPE}

        if not all([worker_type, name, date_of_join, posting, department_role]):
            messages.error(request, "Please fill all required fields.")
            return render(request, "partials/add_team.html", context)

        if worker_type not in valid_worker_types:
            messages.error(request, "Invalid worker type selected.")
            return render(request, "partials/add_team.html", context)

        try:
            worker = Worker(
                department=dept,
                worker_type=worker_type,
                name=name,
                email=email or None,
                date_of_join=date_of_join,
                posting=posting,
                department_role=department_role,
                image=image,
            )
            worker.full_clean()
            worker.save()
            messages.success(request, "Team member added successfully.")
            context["form_data"] = {}
        except (ValidationError, IntegrityError):
            messages.error(request, "Unable to add team member. Check details and try again.")

    return render(request, "partials/add_team.html", context)


def add_project(request):
    if not request.session.get("department_id"):
        return redirect("login")
    dept = get_department(request)
    context = {"form_data": {}}

    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        category = request.POST.get("category", "").strip()
        work_type = request.POST.get("work_type", "").strip()
        start_date = request.POST.get("start_date", "").strip()
        status = request.POST.get("status", "").strip()
        amount = request.POST.get("amount", "").strip()
        github_link = request.POST.get("github_link", "").strip()

        context["form_data"] = {
            "title": title,
            "category": category,
            "work_type": work_type,
            "start_date": start_date,
            "status": status,
            "amount": amount,
            "github_link": github_link,
        }

        valid_categories = {choice[0] for choice in Project.PROJECT_CATEGORY}
        valid_work_types = {choice[0] for choice in Project.WORK_TYPE}
        valid_statuses = {choice[0] for choice in Project.PROJECT_STATUS}

        if not all([title, category, work_type, start_date, status]):
            messages.error(request, "Please fill all required fields.")
            return render(request, "partials/add_project.html", context)

        if category not in valid_categories:
            messages.error(request, "Invalid project category selected.")
            return render(request, "partials/add_project.html", context)

        if work_type not in valid_work_types:
            messages.error(request, "Invalid work type selected.")
            return render(request, "partials/add_project.html", context)

        if status not in valid_statuses:
            messages.error(request, "Invalid status selected.")
            return render(request, "partials/add_project.html", context)

        if category != "company" and not amount:
            messages.error(request, "This project type requires amount")
            return render(request, "partials/add_project.html", context)

        try:
            project = Project(
                department=dept,
                title=title,
                category=category,
                work_type=work_type,
                start_date=start_date,
                status=status,
                amount=amount or None,
                github_link=github_link or None,
            )
            project.full_clean()
            project.save()
            messages.success(request, "Project added successfully.")
            context["form_data"] = {}
        except (ValidationError, IntegrityError):
            messages.error(request, "Unable to add project. Check details and try again.")

    return render(request, "partials/add_project.html", context)


def assign_project(request):
    if not request.session.get("department_id"):
        return redirect("login")
    dept = get_department(request)
    projects = dept.projects.all().order_by("-id")
    workers = dept.workers.all().order_by("name")

    context = {
        "form_data": {},
        "projects": projects,
        "workers": workers,
    }

    if request.method == "POST":
        project_id = request.POST.get("project", "").strip()
        worker_id = request.POST.get("worker", "").strip()
        contribution = request.POST.get("contribution", "gold").strip() or "gold"

        context["form_data"] = {
            "project": project_id,
            "worker": worker_id,
            "contribution": contribution,
        }

        if not project_id or not worker_id:
            messages.error(request, "Please select project and worker.")
            return render(request, "partials/assign_project.html", context)

        valid_contributions = {choice[0] for choice in ProjectMember.CONTRIBUTION}
        if contribution not in valid_contributions:
            messages.error(request, "Invalid contribution selected.")
            return render(request, "partials/assign_project.html", context)

        project = projects.filter(id=project_id).first()
        worker = workers.filter(id=worker_id).first()

        if not project or not worker:
            messages.error(request, "Invalid project or worker selection.")
            return render(request, "partials/assign_project.html", context)

        if ProjectMember.objects.filter(project=project, worker=worker).exists():
            messages.error(request, "This worker is already assigned to this project.")
            return render(request, "partials/assign_project.html", context)

        if project.work_type == "solo" and project.members.exists():
            messages.error(request, "Solo project allows only one worker assignment.")
            return render(request, "partials/assign_project.html", context)

        try:
            assignment = ProjectMember(
                project=project,
                worker=worker,
                contribution=contribution,
            )
            assignment.full_clean()
            assignment.save()
            messages.success(request, "Worker assigned to project successfully.")
            context["form_data"] = {}
        except (ValidationError, IntegrityError):
            messages.error(request, "Unable to assign project member. Check details and try again.")

    return render(request, "partials/assign_project.html", context)




# =========================
# LOGOUT
# =========================
def logout_view(request):
    request.session.flush()
    return redirect("login")

def calculate_project_payments(project):

    if not project.amount:
        return {}

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
