from decimal import Decimal
from io import BytesIO
import os

from django.http import HttpResponse, JsonResponse
from django.db.models import Sum
from django.utils import timezone

from ..models import Project, ProjectMember


def _calculate_project_payments(project):
    if not project.amount:
        return {}

    members = list(project.members.select_related("worker"))
    gold = [m for m in members if m.contribution == "gold"]
    silver = [m for m in members if m.contribution == "silver"]
    copper = [m for m in members if m.contribution == "copper"]
    total_amount = Decimal(project.amount)
    payments = {}

    if gold and not silver and not copper:
        share = total_amount / len(gold)
        for member in gold:
            payments[member.id] = share
    elif gold and silver and not copper:
        gold_total = total_amount * Decimal("0.60")
        silver_total = total_amount * Decimal("0.40")
        for member in gold:
            payments[member.id] = gold_total / len(gold)
        for member in silver:
            payments[member.id] = silver_total / len(silver)
    elif gold and copper and not silver:
        gold_total = total_amount * Decimal("0.70")
        copper_total = total_amount * Decimal("0.30")
        for member in gold:
            payments[member.id] = gold_total / len(gold)
        for member in copper:
            payments[member.id] = copper_total / len(copper)
    else:
        weight_map = {"gold": 3, "silver": 2, "copper": 1}
        total_weight = sum(weight_map[member.contribution] for member in members)
        for member in members:
            share = (Decimal(weight_map[member.contribution]) / Decimal(total_weight)) * total_amount
            payments[member.id] = share

    return payments


def build_team_report_data(dept):
    workers = dept.workers.all().order_by("name")
    projects = dept.projects.all().prefetch_related("members__worker")

    staff_count = workers.filter(worker_type="staff").count()
    intern_count = workers.filter(worker_type="intern").count()
    total_workers = workers.count()
    total_income = (
        projects.aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )
    revenue_per_worker = (
        (Decimal(total_income) / Decimal(total_workers))
        if total_workers > 0
        else Decimal("0.00")
    )

    worker_income_map = {worker.id: Decimal("0.00") for worker in workers}
    for project in projects:
        payments = _calculate_project_payments(project)
        for member in project.members.all():
            worker_income_map[member.worker_id] = worker_income_map.get(member.worker_id, Decimal("0.00")) + payments.get(member.id, Decimal("0.00"))

    rows = []
    for worker in workers:
        rows.append(
            {
                "name": worker.name,
                "email": worker.email or "-",
                "date_of_join": worker.date_of_join.strftime("%Y-%m-%d"),
                "posting": worker.posting,
                "income_by_user": worker_income_map.get(worker.id, Decimal("0.00")),
            }
        )

    return {
        "department_name": dept.name,
        "total_staff_count": staff_count,
        "total_intern_count": intern_count,
        "revenue_per_worker": revenue_per_worker,
        "rows": rows,
        "generated_at": timezone.localtime().strftime("%Y-%m-%d %H:%M:%S"),
    }


def generate_team_csv_report(dept):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment
        has_openpyxl = True
    except ImportError:
        has_openpyxl = False

    if not has_openpyxl:
        return JsonResponse(
            {"detail": "Excel generation dependency missing. Install openpyxl."},
            status=500,
        )

    report = build_team_report_data(dept)

    wb = Workbook()
    ws = wb.active
    ws.title = "Team Report"

    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 34
    ws.column_dimensions["C"].width = 14
    ws.column_dimensions["D"].width = 20
    ws.column_dimensions["E"].width = 16

    summary_rows = [
        ("Department Name", report["department_name"]),
        ("Total Staff Count", str(report["total_staff_count"])),
        ("Total Intern Count", str(report["total_intern_count"])),
        ("Revenue per Worker", f"Rs {report['revenue_per_worker']:,.2f}"),
        ("Generated At", report["generated_at"]),
    ]

    row_idx = 1
    for label, value in summary_rows:
        ws.cell(row=row_idx, column=1, value=label).font = Font(bold=True)
        ws.cell(row=row_idx, column=2, value=value)
        row_idx += 1

    row_idx += 1
    headers = ["Name", "Email", "Date Of Join", "Posting", "Income By User"]
    for col_idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=row_idx, column=col_idx, value=header)
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="left", vertical="center")
    row_idx += 1

    for item in report["rows"]:
        ws.cell(row=row_idx, column=1, value=item["name"])
        ws.cell(row=row_idx, column=2, value=item["email"])
        ws.cell(row=row_idx, column=3, value=item["date_of_join"])
        ws.cell(row=row_idx, column=4, value=item["posting"])
        ws.cell(row=row_idx, column=5, value=f"Rs {Decimal(item['income_by_user']):,.2f}")
        for col_idx in range(1, 6):
            ws.cell(row=row_idx, column=col_idx).alignment = Alignment(horizontal="left", vertical="center", wrap_text=(col_idx == 2))
        row_idx += 1

    ws.freeze_panes = "A7"

    filename = "team_overall_report.xlsx"
    output = BytesIO()
    wb.save(output)
    payload = output.getvalue()
    output.close()

    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.write(payload)
    return response


def generate_team_pdf_report(dept):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.enums import TA_LEFT
    except ImportError:
        return HttpResponse(
            "PDF generation dependency is missing. Install reportlab.",
            status=500,
            content_type="text/plain",
        )

    report = build_team_report_data(dept)

    font_name = "Helvetica"
    for path in [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont("TeamSans", path))
                font_name = "TeamSans"
                break
            except Exception:
                pass

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
        title="Team Overall Report",
        author=report["department_name"],
    )

    title_style = ParagraphStyle("title", fontName=font_name, fontSize=16, textColor=colors.HexColor("#1A2B4A"))
    text_style = ParagraphStyle("text", fontName=font_name, fontSize=9, textColor=colors.HexColor("#334155"), alignment=TA_LEFT)
    header_style = ParagraphStyle("th", fontName=font_name, fontSize=9, textColor=colors.white, alignment=TA_LEFT)
    cell_style = ParagraphStyle("td", fontName=font_name, fontSize=8.5, textColor=colors.HexColor("#1f2937"), alignment=TA_LEFT)

    summary_table = Table(
        [[
            Paragraph("<b>Total Staff Count</b>", text_style), Paragraph(str(report["total_staff_count"]), text_style),
            Paragraph("<b>Total Intern Count</b>", text_style), Paragraph(str(report["total_intern_count"]), text_style),
            Paragraph("<b>Revenue per Worker</b>", text_style), Paragraph(f"Rs {report['revenue_per_worker']:,.2f}", text_style),
        ]],
        colWidths=[34 * mm, 18 * mm, 34 * mm, 18 * mm, 40 * mm, 30 * mm],
    )
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#E8F0FB")),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d1d5db")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    data = [[
        Paragraph("Name", header_style),
        Paragraph("Email", header_style),
        Paragraph("Date Of Join", header_style),
        Paragraph("Posting", header_style),
        Paragraph("Income By User", header_style),
    ]]
    for item in report["rows"]:
        data.append([
            Paragraph(item["name"], cell_style),
            Paragraph(item["email"], cell_style),
            Paragraph(item["date_of_join"], cell_style),
            Paragraph(item["posting"], cell_style),
            Paragraph(f"Rs {Decimal(item['income_by_user']):,.2f}", cell_style),
        ])

    usable_width = A4[0] - (20 * mm)
    table = Table(
        data,
        colWidths=[
            usable_width * 0.19,
            usable_width * 0.29,
            usable_width * 0.14,
            usable_width * 0.20,
            usable_width * 0.18,
        ],
        repeatRows=1,
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2E5FA3")),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#d1d5db")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    story = [
        Paragraph(f"<b>{report['department_name']} Team Report</b>", title_style),
        Spacer(1, 6),
        summary_table,
        Spacer(1, 10),
        table,
    ]
    doc.build(story)

    payload = buffer.getvalue()
    buffer.close()

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="team_overall_report.pdf"'
    response.write(payload)
    return response
