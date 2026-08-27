"""The HR-facing side of the internal job application system.

Where `views.py` lets an employee see their own submissions, this module is
for whoever reviews them: list everything (with filters), pull the full
record for one applicant into a popup, download a single application as a
PDF, or export a filtered batch as a ZIP of PDFs.
"""

import io
import re
import zipfile
from datetime import datetime

from django.core.paginator import Paginator
from django.http import FileResponse, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .models import InternalJobApplication
from .reports_permissions import require_applications_viewer

# A ZIP this size is already a multi-minute request; past this, the caller
# should narrow the filters instead of exporting everything at once.
MAX_ZIP_APPLICATIONS = 300

DEFAULT_PAGE_SIZE = 50


# ---------------------------------------------------------------------------
# Shared query helpers
# ---------------------------------------------------------------------------

def _base_queryset():
    return (
        InternalJobApplication.objects.select_related("target_job_req")
        .prefetch_related("education", "experience", "skills")
        .order_by("-created_at")
    )


def _apply_filters(request, queryset):
    """Status / vacancy / free-text / date-range filters, shared by the list
    endpoint and the ZIP export so "export what I'm looking at" is exact."""
    status = request.GET.get("status")
    if status:
        queryset = queryset.filter(status=status)

    vacancy_id = request.GET.get("target_job_req_id")
    if vacancy_id:
        queryset = queryset.filter(target_job_req_id=vacancy_id)

    search = (request.GET.get("search") or "").strip()
    if search:
        queryset = queryset.filter(
            emp_full_name__icontains=search
        ) | queryset.filter(corporate_email__icontains=search) | queryset.filter(
            emp_id__icontains=search
        ) | queryset.filter(cnic__icontains=search)

    date_from = request.GET.get("date_from")
    if date_from:
        queryset = queryset.filter(created_at__date__gte=date_from)

    date_to = request.GET.get("date_to")
    if date_to:
        queryset = queryset.filter(created_at__date__lte=date_to)

    return queryset.distinct()


def _summary(application: InternalJobApplication) -> dict:
    return {
        "id": application.id,
        "vacancy": application.target_job_req.title,
        "target_job_req_id": application.target_job_req_id,
        "emp_full_name": application.emp_full_name,
        "emp_id": application.emp_id,
        "current_dept_code": application.current_dept_code,
        "current_job_title": application.current_job_title,
        "corporate_email": application.corporate_email,
        "contact_phone_no": application.contact_phone_no,
        "status": application.status,
        "created_at": application.created_at.strftime("%Y-%m-%d %H:%M"),
        "education_count": application.education.count(),
        "experience_count": application.experience.count(),
        "skill_count": application.skills.count(),
    }


def _detail(application: InternalJobApplication) -> dict:
    education = [
        {
            "edu_degree_title": row.edu_degree_title,
            "edu_institution_name": row.edu_institution_name,
            "edu_major_specialization": row.edu_major_specialization,
            "edu_graduation_year": row.edu_graduation_year,
            "edu_grade_score": row.edu_grade_score,
        }
        for row in application.education.all().order_by("row_order")
    ]
    experience = [
        {
            "exp_job_title": row.exp_job_title,
            "exp_company_name": row.exp_company_name,
            "exp_start_date": row.exp_start_date.isoformat() if row.exp_start_date else None,
            "exp_end_date": row.exp_end_date.isoformat() if row.exp_end_date else None,
            "exp_is_current": row.exp_is_current,
            "exp_key_responsibilities": row.exp_key_responsibilities,
            "exp_key_achievements": row.exp_key_achievements,
        }
        for row in application.experience.all().order_by("row_order")
    ]
    skills = list(application.skills.all())
    technical_skills = [s.skill_name for s in skills if s.skill_type == "technical"]
    soft_skills = [s.skill_name for s in skills if s.skill_type == "soft"]

    return {
        **_summary(application),
        "current_supervisor_id": application.current_supervisor_id,
        "cnic": application.cnic,
        "personal_email": application.personal_email,
        "preferred_contact_method": application.preferred_contact_method,
        "certifications_list": application.certifications_list,
        "application_rationale_sop": application.application_rationale_sop,
        "ack_manager_notified_bool": application.ack_manager_notified_bool,
        "ack_data_accuracy_bool": application.ack_data_accuracy_bool,
        "education": education,
        "experience": experience,
        "skills_technical": technical_skills,
        "skills_soft": soft_skills,
    }


# ---------------------------------------------------------------------------
# List / detail
# ---------------------------------------------------------------------------

@require_GET
def list_applications_report(request):
    identity, refusal = require_applications_viewer(request)
    if refusal:
        return JsonResponse({"error": refusal}, status=403)

    queryset = _apply_filters(request, _base_queryset())

    try:
        page_number = max(int(request.GET.get("page", 1)), 1)
    except (TypeError, ValueError):
        page_number = 1
    try:
        page_size = min(max(int(request.GET.get("page_size", DEFAULT_PAGE_SIZE)), 1), 200)
    except (TypeError, ValueError):
        page_size = DEFAULT_PAGE_SIZE

    paginator = Paginator(queryset, page_size)
    page = paginator.get_page(page_number)

    return JsonResponse(
        {
            "results": [_summary(app) for app in page.object_list],
            "count": paginator.count,
            "page": page.number,
            "num_pages": paginator.num_pages,
            "statuses": list(
                InternalJobApplication.objects.order_by()
                .values_list("status", flat=True)
                .distinct()
            ),
        },
        status=200,
    )


@require_GET
def application_detail(request, application_id: int):
    identity, refusal = require_applications_viewer(request)
    if refusal:
        return JsonResponse({"error": refusal}, status=403)

    application = _base_queryset().filter(id=application_id).first()
    if application is None:
        return JsonResponse({"error": "Application not found"}, status=404)

    return JsonResponse(_detail(application), status=200)


# ---------------------------------------------------------------------------
# PDF rendering
# ---------------------------------------------------------------------------

_styles = getSampleStyleSheet()
_STYLE_TITLE = ParagraphStyle(
    "AppTitle", parent=_styles["Title"], fontSize=16, spaceAfter=4
)
_STYLE_SUBTITLE = ParagraphStyle(
    "AppSubtitle", parent=_styles["Normal"], fontSize=10, textColor=colors.grey, spaceAfter=14
)
_STYLE_HEADING = ParagraphStyle(
    "SectionHeading",
    parent=_styles["Heading2"],
    fontSize=12,
    spaceBefore=14,
    spaceAfter=6,
    textColor=colors.HexColor("#1c3d5a"),
)
_STYLE_LABEL = ParagraphStyle("FieldLabel", parent=_styles["Normal"], fontSize=8, textColor=colors.grey)
_STYLE_VALUE = ParagraphStyle("FieldValue", parent=_styles["Normal"], fontSize=10, spaceAfter=6)
_STYLE_BODY = ParagraphStyle("Body", parent=_styles["Normal"], fontSize=9, leading=13)


def _field(label: str, value) -> list:
    text = str(value) if value not in (None, "") else "—"
    return [Paragraph(label, _STYLE_LABEL), Paragraph(text, _STYLE_VALUE)]


def _two_col(rows: list) -> Table:
    """rows: list of (label, value) pairs, laid out two fields per line.

    Each field is its own [label, value] paragraph pair; nesting each pair in
    a small inner table keeps the label glued to its value when the row wraps.
    """
    grid = []
    for i in range(0, len(rows), 2):
        left = _field(*rows[i])
        right = (
            _field(*rows[i + 1])
            if i + 1 < len(rows)
            else [Paragraph("", _STYLE_LABEL), Paragraph("", _STYLE_VALUE)]
        )
        grid.append([left, right])

    flattened_rows = [
        [Table([[p] for p in cell], colWidths=[8.7 * cm]) for cell in row]
        for row in grid
    ]
    table = Table(flattened_rows, colWidths=[9 * cm, 9 * cm])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return table


def render_application_pdf(application: InternalJobApplication) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.6 * cm,
        bottomMargin=1.6 * cm,
        title=f"Job Application - {application.emp_full_name}",
    )

    story = []
    story.append(Paragraph("Internal Job Application", _STYLE_TITLE))
    story.append(
        Paragraph(
            f"Application #{application.id} · Vacancy: {application.target_job_req.title} · "
            f"Status: {application.status} · Submitted {application.created_at.strftime('%d %b %Y, %H:%M')}",
            _STYLE_SUBTITLE,
        )
    )

    story.append(Paragraph("Target Position &amp; Applicant Identity", _STYLE_HEADING))
    story.append(_two_col([
        ("Employee Full Name", application.emp_full_name),
        ("Employee ID", application.emp_id),
        ("Current Department", application.current_dept_code),
        ("Current Position Title", application.current_job_title),
        ("Current Supervisor", application.current_supervisor_id),
        ("CNIC", application.cnic),
    ]))

    story.append(Paragraph("Contact Information", _STYLE_HEADING))
    story.append(_two_col([
        ("Contact Phone Number", application.contact_phone_no),
        ("Corporate Email", application.corporate_email),
        ("Personal Email", application.personal_email),
        ("Preferred Contact Method", application.preferred_contact_method),
    ]))

    story.append(Paragraph("Educational Background", _STYLE_HEADING))
    education_rows = list(application.education.all().order_by("row_order"))
    if education_rows:
        data = [["Degree / Certificate", "Institution", "Major", "Year", "Grade"]]
        for row in education_rows:
            data.append([
                row.edu_degree_title, row.edu_institution_name,
                row.edu_major_specialization or "—",
                str(row.edu_graduation_year), row.edu_grade_score or "—",
            ])
        edu_table = Table(data, colWidths=[4.2 * cm, 4.8 * cm, 4 * cm, 2 * cm, 2.6 * cm], repeatRows=1)
        edu_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef3f8")),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d7dfe6")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(edu_table)
    else:
        story.append(Paragraph("No education records provided.", _STYLE_BODY))

    story.append(Paragraph("Professional Experience", _STYLE_HEADING))
    experience_rows = list(application.experience.all().order_by("row_order"))
    if experience_rows:
        for row in experience_rows:
            end = "Present" if row.exp_is_current else (
                row.exp_end_date.strftime("%b %Y") if row.exp_end_date else "—"
            )
            start = row.exp_start_date.strftime("%b %Y") if row.exp_start_date else "—"
            block = [
                Paragraph(f"<b>{row.exp_job_title}</b> — {row.exp_company_name} ({start} – {end})", _STYLE_BODY),
            ]
            if row.exp_key_responsibilities:
                block.append(Paragraph(f"<i>Responsibilities:</i> {row.exp_key_responsibilities}", _STYLE_BODY))
            if row.exp_key_achievements:
                block.append(Paragraph(f"<i>Achievements:</i> {row.exp_key_achievements}", _STYLE_BODY))
            block.append(Spacer(1, 8))
            story.append(KeepTogether(block))
    else:
        story.append(Paragraph("No experience records provided.", _STYLE_BODY))

    story.append(Paragraph("Skills &amp; Certifications", _STYLE_HEADING))
    skills = list(application.skills.all())
    technical = ", ".join(s.skill_name for s in skills if s.skill_type == "technical") or "—"
    soft = ", ".join(s.skill_name for s in skills if s.skill_type == "soft") or "—"
    story.append(Paragraph(f"<b>Technical Skills:</b> {technical}", _STYLE_BODY))
    story.append(Paragraph(f"<b>Soft Skills:</b> {soft}", _STYLE_BODY))
    story.append(Paragraph(f"<b>Certifications:</b> {application.certifications_list or '—'}", _STYLE_BODY))

    story.append(Paragraph("Statement of Purpose", _STYLE_HEADING))
    story.append(Paragraph(application.application_rationale_sop, _STYLE_BODY))

    story.append(Paragraph("Acknowledgements", _STYLE_HEADING))
    story.append(Paragraph(
        f"Manager notified: <b>{'Yes' if application.ack_manager_notified_bool else 'No'}</b> &nbsp;&nbsp; "
        f"Data accuracy confirmed: <b>{'Yes' if application.ack_data_accuracy_bool else 'No'}</b>",
        _STYLE_BODY,
    ))

    doc.build(story)
    return buffer.getvalue()


def _safe_filename(application: InternalJobApplication) -> str:
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", application.emp_full_name or "applicant").strip("_")
    return f"{application.id}_{name or 'applicant'}.pdf"


@require_GET
def application_pdf(request, application_id: int):
    identity, refusal = require_applications_viewer(request)
    if refusal:
        return JsonResponse({"error": refusal}, status=403)

    application = _base_queryset().filter(id=application_id).first()
    if application is None:
        return JsonResponse({"error": "Application not found"}, status=404)

    pdf_bytes = render_application_pdf(application)
    # `inline=1` opens the PDF in the browser's own viewer, whose print button
    # covers "print" without a separate print endpoint; omit it to download.
    disposition = "inline" if request.GET.get("inline") == "1" else "attachment"
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'{disposition}; filename="{_safe_filename(application)}"'
    return response


# ---------------------------------------------------------------------------
# Bulk ZIP export
# ---------------------------------------------------------------------------

@require_GET
def applications_zip(request):
    identity, refusal = require_applications_viewer(request)
    if refusal:
        return JsonResponse({"error": refusal}, status=403)

    queryset = _apply_filters(request, _base_queryset())
    count = queryset.count()

    if count == 0:
        return JsonResponse({"error": "No applications match the current filters"}, status=404)

    if count > MAX_ZIP_APPLICATIONS:
        return JsonResponse(
            {
                "error": (
                    f"{count} applications match these filters, which is more than the "
                    f"{MAX_ZIP_APPLICATIONS}-file export limit. Narrow the filters (status, "
                    "vacancy, or date range) and try again."
                )
            },
            status=400,
        )

    buffer = io.BytesIO()
    used_names = set()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for application in queryset:
            filename = _safe_filename(application)
            # Guard against two applicants producing the same sanitized name.
            if filename in used_names:
                filename = f"{application.id}_{application.emp_id}.pdf"
            used_names.add(filename)
            archive.writestr(filename, render_application_pdf(application))

    buffer.seek(0)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    response = FileResponse(
        buffer, as_attachment=True, filename=f"job_applications_{stamp}.zip"
    )
    return response