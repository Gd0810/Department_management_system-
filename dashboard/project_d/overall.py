import csv
from decimal import Decimal
from io import BytesIO

from django.http import HttpResponse
from django.db.models import Sum
from django.utils import timezone

from ..models import Project


def _category_label(category_key):
    return dict(Project.PROJECT_CATEGORY).get(category_key, category_key.title())


def build_category_report_data(dept, category_key):
    category_label = _category_label(category_key)
    projects = (
        dept.projects.filter(category=category_key)
        .prefetch_related("members__worker")
        .order_by("-start_date", "-id")
    )
    overall_income = (
        projects.aggregate(total_income=Sum("amount"))["total_income"]
        or Decimal("0.00")
    )
    overall_project_count = projects.count()

    rows = []
    for project in projects:
        worker_names = ", ".join(
            project.members.all()
            .values_list("worker__name", flat=True)
        ) or "No workers assigned"
        rows.append(
            {
                "project_name": project.title,
                "start_date": project.start_date.strftime("%Y-%m-%d"),
                "status": project.get_status_display(),
                "worker_names": worker_names,
            }
        )

    return {
        "department_name": dept.name,
        "category_key": category_key,
        "category_label": category_label,
        "overall_income": overall_income,
        "overall_project_count": overall_project_count,
        "projects": rows,
        "generated_at": timezone.localtime().strftime("%Y-%m-%d %H:%M:%S"),
    }


def generate_category_csv_report(dept, category_key):
    report = build_category_report_data(dept, category_key)
    filename = f"{category_key}_projects_report.csv"
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow(["Department Name", report["department_name"]])
    writer.writerow(["Category", report["category_label"]])
    writer.writerow(["Overall Income for Category", f'{report["overall_income"]:.2f}'])
    writer.writerow(["Overall Projects for Category", report["overall_project_count"]])
    writer.writerow(["Generated At", report["generated_at"]])
    writer.writerow([])
    writer.writerow(["Project Name", "Start Date", "Status", "Worker Name for Project"])

    for row in report["projects"]:
        writer.writerow(
            [
                row["project_name"],
                row["start_date"],
                row["status"],
                row["worker_names"],
            ]
        )
    return response


def generate_category_pdf_report(dept, category_key):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except Exception:
        return HttpResponse(
            "PDF generation dependency is missing. Install reportlab.",
            status=500,
            content_type="text/plain",
        )

    report = build_category_report_data(dept, category_key)
    filename = f"{category_key}_projects_report.pdf"
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    page_width, page_height = A4
    left = 36
    y = page_height - 42

    def ensure_page(space_needed=18):
        nonlocal y
        if y < 42 + space_needed:
            pdf.showPage()
            y = page_height - 42
            pdf.setFont("Helvetica", 10)

    pdf.setTitle(f"{report['category_label']} Projects Report")
    pdf.setFont("Helvetica-Bold", 15)
    pdf.drawString(left, y, f"{report['category_label']} Projects Report")
    y -= 22

    pdf.setFont("Helvetica", 10)
    summary_lines = [
        f"Department Name: {report['department_name']}",
        f"Overall Income for Category: {report['overall_income']:.2f}",
        f"Overall Projects for Category: {report['overall_project_count']}",
        f"Generated At: {report['generated_at']}",
    ]
    for line in summary_lines:
        ensure_page(14)
        pdf.drawString(left, y, line)
        y -= 14

    y -= 8
    headers = ["Project Name", "Start Date", "Status", "Worker Name for Project"]
    col_x = [left, 230, 310, 390]
    pdf.setFont("Helvetica-Bold", 9)
    for idx, header in enumerate(headers):
        pdf.drawString(col_x[idx], y, header)
    y -= 14
    pdf.line(left, y + 4, page_width - left, y + 4)
    pdf.setFont("Helvetica", 9)

    for item in report["projects"]:
        ensure_page(28)
        worker_text = item["worker_names"][:65]
        pdf.drawString(col_x[0], y, item["project_name"][:30])
        pdf.drawString(col_x[1], y, item["start_date"])
        pdf.drawString(col_x[2], y, item["status"][:14])
        pdf.drawString(col_x[3], y, worker_text)
        y -= 14

    pdf.save()
    pdf_bytes = buffer.getvalue()
    buffer.close()

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write(pdf_bytes)
    return response
