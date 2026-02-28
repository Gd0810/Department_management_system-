from django.shortcuts import render, redirect
from django.http import JsonResponse
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
from django.urls import reverse
from .project_d.overall import generate_category_csv_report, generate_category_pdf_report
from .project_d.listing import generate_project_listing_excel_report, generate_project_listing_pdf_report



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
    all_workers = dept.workers.all().order_by("name")
    all_projects = dept.projects.all().prefetch_related("members__worker")

    staff_count = all_workers.filter(worker_type="staff").count()
    intern_count = all_workers.filter(worker_type="intern").count()
    total_workers = staff_count + intern_count
    total_projects = all_projects.count()
    total_income = (
        all_projects.aggregate(
            total=Coalesce(
                Sum("amount"),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )["total"]
        or Decimal("0.00")
    )

    workers_project_avg_pct = (total_workers / total_projects) * 100 if total_projects > 0 else 0
    workers_income_avg_pct = (Decimal(total_workers) / total_income) * Decimal("100") if total_income > 0 else Decimal("0")

    worker_project_count_map = defaultdict(int)
    membership_rows = (
        ProjectMember.objects
        .filter(worker__in=all_workers, project__department=dept)
        .values("worker_id")
        .annotate(project_count=Count("project_id", distinct=True))
    )
    for row in membership_rows:
        worker_project_count_map[row["worker_id"]] = int(row["project_count"] or 0)

    worker_income_map = defaultdict(Decimal)
    all_worker_ids = set(all_workers.values_list("id", flat=True))
    for project in all_projects:
        payments = calculate_project_payments(project)
        for member in project.members.all():
            if member.worker_id in all_worker_ids:
                worker_income_map[member.worker_id] += payments.get(member.id, Decimal("0.00"))

    worker_status_map = defaultdict(lambda: {
        "finished": 0,
        "ongoing": 0,
        "on_hold": 0,
        "canceled": 0,
    })
    worker_status_rows = (
        ProjectMember.objects
        .filter(worker__in=all_workers, project__department=dept)
        .values("worker_id", "project__status")
        .annotate(project_count=Count("project_id", distinct=True))
    )
    for row in worker_status_rows:
        worker_id = row["worker_id"]
        status_key = row["project__status"]
        if status_key in worker_status_map[worker_id]:
            worker_status_map[worker_id][status_key] = int(row["project_count"] or 0)

    today = date.today()
    worker_labels = []
    worker_income_values = []
    worker_project_values = []
    worker_experience_values = []
    worker_type_values = []
    worker_image_urls = []
    worker_initials = []
    worker_finished_values = []
    worker_ongoing_values = []
    worker_on_hold_values = []
    worker_canceled_values = []
    worker_rows = []

    for worker in all_workers:
        parts = [part for part in worker.name.split() if part]
        if len(parts) >= 2:
            initials = (parts[0][0] + parts[1][0]).upper()
        elif parts:
            initials = parts[0][:2].upper()
        else:
            initials = "NA"

        worker_labels.append(worker.name)
        worker_income_values.append(float(worker_income_map.get(worker.id, Decimal("0.00"))))
        worker_project_values.append(worker_project_count_map.get(worker.id, 0))
        worker_experience_values.append(max((today - worker.date_of_join).days, 0))
        worker_type_values.append(worker.worker_type)
        worker_image_urls.append(worker.image.url if worker.image else "")
        worker_initials.append(initials)
        status_counts = worker_status_map[worker.id]
        worker_finished_values.append(status_counts["finished"])
        worker_ongoing_values.append(status_counts["ongoing"])
        worker_on_hold_values.append(status_counts["on_hold"])
        worker_canceled_values.append(status_counts["canceled"])
        worker_rows.append(
            {
                "id": worker.id,
                "name": worker.name,
                "email": worker.email,
                "date_of_join": worker.date_of_join,
                "posting": worker.posting,
                "image_url": worker.image.url if worker.image else "",
                "initials": initials,
                "working_status": worker.working_status,
            }
        )

    context = {
        "staff_count": staff_count,
        "intern_count": intern_count,
        "total_workers": total_workers,
        "total_projects": total_projects,
        "workers_project_avg_pct": round(workers_project_avg_pct, 2),
        "workers_income_avg_pct": round(float(workers_income_avg_pct), 6),
        "worker_labels": worker_labels,
        "worker_income_values": worker_income_values,
        "worker_project_values": worker_project_values,
        "worker_experience_values": worker_experience_values,
        "worker_type_values": worker_type_values,
        "worker_image_urls": worker_image_urls,
        "worker_initials": worker_initials,
        "worker_finished_values": worker_finished_values,
        "worker_ongoing_values": worker_ongoing_values,
        "worker_on_hold_values": worker_on_hold_values,
        "worker_canceled_values": worker_canceled_values,
        "workers": worker_rows,
    }
    return render(request, "partials/team.html", context)


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


def _category_template_name(category_key):
    return {
        "client": "partials/client.html",
        "company": "partials/company.html",
        "academy": "partials/academics.html",
        "internship": "partials/internship.html",
    }.get(category_key)


def _render_category_dashboard_by_key(request, category_key):
    template_name = _category_template_name(category_key)
    if not template_name:
        dept = get_department(request)
        return render(
            request,
            "partials/index.html",
            {
                "department": dept,
                "workers": dept.workers.count(),
                "projects": dept.projects.count(),
            },
        )
    return _render_project_category_dashboard(request, category_key, template_name)


def category_projects_api(request, category_key):
    if not request.session.get("department_id"):
        return JsonResponse({"detail": "Unauthorized"}, status=401)

    valid_categories = {choice[0] for choice in Project.PROJECT_CATEGORY}
    if category_key not in valid_categories:
        return JsonResponse({"detail": "Invalid category"}, status=400)

    try:
        offset = max(int(request.GET.get("offset", 0)), 0)
    except (TypeError, ValueError):
        offset = 0
    try:
        limit = int(request.GET.get("limit", 7))
    except (TypeError, ValueError):
        limit = 7
    limit = max(1, min(limit, 25))

    dept = get_department(request)
    base_queryset = dept.projects.filter(category=category_key)
    queryset = base_queryset

    search_query = request.GET.get("q", "").strip()
    month_value = request.GET.get("month", "").strip()
    year_value = request.GET.get("year", "").strip()
    status_value = request.GET.get("status", "").strip()

    if search_query:
        queryset = queryset.filter(title__icontains=search_query)

    if month_value:
        try:
            month_year, month_num = month_value.split("-")
            queryset = queryset.filter(
                start_date__year=int(month_year),
                start_date__month=int(month_num),
            )
        except (TypeError, ValueError):
            pass

    if year_value:
        try:
            queryset = queryset.filter(start_date__year=int(year_value))
        except (TypeError, ValueError):
            pass

    valid_statuses = {choice[0] for choice in Project.PROJECT_STATUS}
    if status_value in valid_statuses:
        queryset = queryset.filter(status=status_value)

    queryset = queryset.order_by("-start_date", "-id")
    total_count = queryset.count()
    rows = list(queryset[offset:offset + limit])
    available_years = [d.year for d in base_queryset.dates("start_date", "year", order="DESC")]

    payload = []
    for project in rows:
        payload.append(
            {
                "id": project.id,
                "title": project.title,
                "status": project.status,
                "status_display": project.get_status_display(),
                "start_date": project.start_date.strftime("%Y-%m-%d"),
                "view_url": reverse("project_detail", args=[project.id]),
                "update_url": reverse("edit_project", args=[project.id]),
                "delete_url": reverse("delete_project", args=[project.id]),
            }
        )

    next_offset = offset + len(rows)
    has_more = next_offset < total_count
    return JsonResponse(
        {
            "projects": payload,
            "next_offset": next_offset,
            "has_more": has_more,
            "available_years": available_years,
        }
    )


@require_http_methods(["GET"])
def project_category_report(request, category_key, file_format):
    if not request.session.get("department_id"):
        return redirect("login")

    valid_categories = {choice[0] for choice in Project.PROJECT_CATEGORY}
    if category_key not in valid_categories:
        return JsonResponse({"detail": "Invalid category"}, status=400)

    dept = get_department(request)
    file_format = (file_format or "").lower()
    if file_format == "csv":
        return generate_category_csv_report(dept, category_key)
    if file_format == "pdf":
        return generate_category_pdf_report(dept, category_key)

    return JsonResponse({"detail": "Unsupported format"}, status=400)


@require_http_methods(["GET"])
def project_listing_report(request, category_key, file_format):
    if not request.session.get("department_id"):
        return redirect("login")

    valid_categories = {choice[0] for choice in Project.PROJECT_CATEGORY}
    if category_key not in valid_categories:
        return JsonResponse({"detail": "Invalid category"}, status=400)

    dept = get_department(request)
    file_format = (file_format or "").lower()
    if file_format == "csv":
        return generate_project_listing_excel_report(dept, category_key, request.GET)
    if file_format == "pdf":
        return generate_project_listing_pdf_report(dept, category_key, request.GET)

    return JsonResponse({"detail": "Unsupported format"}, status=400)


def project_detail(request, project_id):
    if not request.session.get("department_id"):
        return redirect("login")

    dept = get_department(request)
    project = (
        dept.projects.filter(id=project_id)
        .prefetch_related("members__worker")
        .first()
    )
    if not project:
        messages.error(request, "Project not found.")
        return redirect("index")

    category_lookup = dict(Project.PROJECT_CATEGORY)
    category_label = category_lookup.get(project.category, project.category.title())
    back_route = {
        "client": "client",
        "company": "company",
        "academy": "academics",
        "internship": "internship",
    }.get(project.category, "index")

    status_meta = {
        "started": {"badge_class": "status-started", "icon": "rocket_launch"},
        "ongoing": {"badge_class": "status-ongoing", "icon": "play_circle"},
        "on_hold": {"badge_class": "status-hold", "icon": "pause_circle"},
        "canceled": {"badge_class": "status-canceled", "icon": "cancel"},
        "finished": {"badge_class": "status-finished", "icon": "task_alt"},
    }.get(project.status, {"badge_class": "status-default", "icon": "info"})

    member_rows = []
    payments = calculate_project_payments(project)
    for member in project.members.select_related("worker").all():
        amount = payments.get(member.id, Decimal("0.00"))
        member_rows.append(
            {
                "name": member.worker.name,
                "worker_type": member.worker.get_worker_type_display(),
                "department_role": member.worker.department_role,
                "contribution": member.get_contribution_display(),
                "income": float(amount),
            }
        )

    project_income = Decimal(project.amount or Decimal("0.00"))
    category_income_total = (
        dept.projects.filter(category=project.category).aggregate(
            total=Coalesce(
                Sum("amount"),
                Value(Decimal("0.00")),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            )
        )["total"]
        or Decimal("0.00")
    )

    project_income_percentage = (
        float((project_income / category_income_total) * Decimal("100"))
        if category_income_total > 0
        else 0.0
    )
    category_remaining_percentage = max(0.0, 100.0 - project_income_percentage)

    context = {
        "project": project,
        "category_label": category_label,
        "back_url": reverse(back_route),
        "status_badge_class": status_meta["badge_class"],
        "status_icon": status_meta["icon"],
        "member_rows": member_rows,
        "project_income": float(project_income),
        "category_income_total": float(category_income_total),
        "project_income_percentage": round(project_income_percentage, 2),
        "category_remaining_percentage": round(category_remaining_percentage, 2),
    }
    return render(request, "partials/project_detail.html", context)


@require_http_methods(["GET", "POST"])
def edit_project(request, project_id):
    if not request.session.get("department_id"):
        return redirect("login")

    dept = get_department(request)
    project = dept.projects.filter(id=project_id).first()
    if not project:
        messages.error(request, "Project not found.")
        return redirect("index")

    back_route = {
        "client": "client",
        "company": "company",
        "academy": "academics",
        "internship": "internship",
    }.get(project.category, "index")

    context = {
        "project": project,
        "back_url": reverse(back_route),
        "form_data": {
            "title": project.title,
            "category": project.category,
            "work_type": project.work_type,
            "start_date": project.start_date.strftime("%Y-%m-%d"),
            "status": project.status,
            "amount": project.amount if project.amount is not None else "",
            "github_link": project.github_link or "",
        },
    }

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
            return render(request, "partials/edit_project.html", context)

        if category not in valid_categories:
            messages.error(request, "Invalid project category selected.")
            return render(request, "partials/edit_project.html", context)

        if work_type not in valid_work_types:
            messages.error(request, "Invalid work type selected.")
            return render(request, "partials/edit_project.html", context)

        if status not in valid_statuses:
            messages.error(request, "Invalid status selected.")
            return render(request, "partials/edit_project.html", context)

        if category != "company" and not amount:
            messages.error(request, "This project type requires amount")
            return render(request, "partials/edit_project.html", context)

        try:
            project.title = title
            project.category = category
            project.work_type = work_type
            project.start_date = start_date
            project.status = status
            project.amount = amount or None
            project.github_link = github_link or None
            project.full_clean()
            project.save()
            messages.success(request, "Project updated successfully.")
            return _render_category_dashboard_by_key(request, project.category)
        except (ValidationError, IntegrityError):
            messages.error(request, "Unable to update project. Check details and try again.")

    return render(request, "partials/edit_project.html", context)


@require_http_methods(["POST"])
def delete_project(request, project_id):
    if not request.session.get("department_id"):
        return redirect("login")

    dept = get_department(request)
    project = dept.projects.filter(id=project_id).first()
    if not project:
        messages.error(request, "Project not found.")
        return redirect("index")

    category_key = project.category
    try:
        project.delete()
        messages.success(request, "Project deleted successfully.")
    except Exception:
        messages.error(request, "Unable to delete project.")

    return _render_category_dashboard_by_key(request, category_key)


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
        "project_categories": Project.PROJECT_CATEGORY,
    }

    if request.method == "POST":
        project_category = request.POST.get("project_category", "").strip()
        project_id = request.POST.get("project", "").strip()
        worker_id = request.POST.get("worker", "").strip()
        contribution = request.POST.get("contribution", "gold").strip() or "gold"

        context["form_data"] = {
            "project_category": project_category,
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
