"""The HR-facing side of the internal job application system.

Where `views.py` lets an employee see their own submissions, this module is
for whoever reviews them: list everything (with filters), pull the full
record for one applicant into a popup, download a single application as a
PDF, or export a filtered batch as a ZIP of PDFs.
"""

import io
import re
import zipfile
from xml.sax.saxutils import escape
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

from .form_text import DECLARATION_PARAGRAPHS, SUBMISSION_NOTE
from .models import InternalJobApplication
from .reports_permissions import require_applications_viewer

# A ZIP this size is already a multi-minute request; past this, the caller
# should narrow the filters instead of exporting everything at once.
MAX_ZIP_APPLICATIONS = 300

DEFAULT_PAGE_SIZE = 50


class FilterError(ValueError):
    """A query string the page would never produce - answered as a 400 rather
    than letting the database raise on it."""


# ---------------------------------------------------------------------------
# Shared query helpers
# ---------------------------------------------------------------------------

def _base_queryset():
    return (
        InternalJobApplication.objects.select_related("target_job_req")
        .prefetch_related("education", "experience", "certifications", "trainings")
        .order_by("-created_at")
    )


def _as_date(value, label: str):
    """A date from the query string, or None when it was not given."""
    value = (value or "").strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise FilterError(f"The {label} date should look like 2026-08-27")


def _apply_filters(request, queryset):
    """Status / vacancy / free-text / date-range filters, shared by the list
    endpoint and the ZIP export so "export what I'm looking at" is exact."""
    status = request.GET.get("status")
    if status:
        queryset = queryset.filter(status=status)

    vacancy_id = request.GET.get("target_job_req_id")
    if vacancy_id:
        try:
            queryset = queryset.filter(target_job_req_id=int(vacancy_id))
        except (TypeError, ValueError):
            raise FilterError("The vacancy filter is not a vacancy id")

    search = (request.GET.get("search") or "").strip()
    if search:
        queryset = (
            queryset.filter(full_name__icontains=search)
            | queryset.filter(official_email__icontains=search)
            | queryset.filter(emp_id__icontains=search)
            | queryset.filter(cnic__icontains=search)
            | queryset.filter(application_reference_no__icontains=search)
            | queryset.filter(vacancy_position_title__icontains=search)
        )

    date_from = _as_date(request.GET.get("date_from"), "From")
    if date_from:
        queryset = queryset.filter(created_at__date__gte=date_from)

    date_to = _as_date(request.GET.get("date_to"), "To")
    if date_to:
        queryset = queryset.filter(created_at__date__lte=date_to)

    if date_from and date_to and date_from > date_to:
        raise FilterError("The From date is after the To date")

    return queryset.distinct()


def _iso(value):
    return value.isoformat() if value else None


def _summary(application: InternalJobApplication) -> dict:
    """One row of the report list."""
    return {
        "id": application.id,
        "reference_no": application.application_reference_no or "",
        "vacancy": application.vacancy_position_title or application.target_job_req.title,
        "vacancy_reference_no": application.vacancy_reference_no or "",
        "target_job_req_id": application.target_job_req_id,
        "full_name": application.full_name,
        "emp_id": application.emp_id,
        "department_function": application.department_function,
        "current_designation": application.current_designation,
        "current_grade": application.current_grade,
        "official_email": application.official_email,
        "mobile_no": application.mobile_no,
        "status": application.status,
        "hr_verification_status": application.hr_verification_status,
        "created_at": application.created_at.strftime("%Y-%m-%d %H:%M"),
        "education_count": application.education.count(),
        "experience_count": application.experience.count(),
        "certification_count": application.certifications.count(),
        "training_count": application.trainings.count(),
    }


def _detail(application: InternalJobApplication) -> dict:
    """Everything the printed form shows, section by section."""
    education = [
        {
            "degree_qualification": row.degree_qualification,
            "major_field_of_study": row.major_field_of_study,
            "institution_university": row.institution_university,
            "country": row.country,
            "year_of_completion": row.year_of_completion,
            "cgpa_division": row.cgpa_division,
        }
        for row in application.education.all()
    ]
    experience = [
        {
            "organization_employer": row.organization_employer,
            "designation": row.designation,
            "grade": row.grade or "",
            "from_date": _iso(row.from_date),
            "to_date": _iso(row.to_date),
            "is_current": row.is_current,
            "duration": row.duration,
            "key_responsibilities": row.key_responsibilities,
        }
        for row in application.experience.all()
    ]
    certifications = [
        {
            "certification_membership": row.certification_membership,
            "certifying_body": row.certifying_body,
            "date_obtained": _iso(row.date_obtained),
            "expiry_date": _iso(row.expiry_date),
            "registration_no": row.registration_no or "",
        }
        for row in application.certifications.all()
    ]
    trainings = [
        {
            "training_title": row.training_title,
            "training_provider": row.training_provider,
            "duration": row.duration or "",
            "date_or_year": row.date_or_year or "",
            "relevant_to_position": row.relevant_to_position,
        }
        for row in application.trainings.all()
    ]

    return {
        **_summary(application),
        # 1. vacancy information
        "vacancy_grade": application.vacancy_grade or "",
        "vacancy_department": application.vacancy_department or "",
        "vacancy_advertisement_date": _iso(application.vacancy_advertisement_date),
        "vacancy_closing_date": _iso(application.vacancy_closing_date),
        # 2. personal & contact information
        "father_or_husband_name": application.father_or_husband_name,
        "cnic": application.cnic,
        "date_of_birth": _iso(application.date_of_birth),
        "gender": application.gender,
        "current_office_location": application.current_office_location,
        "emergency_contact_no": application.emergency_contact_no or "",
        # 3. current employment details
        "date_of_joining_ismo": _iso(application.date_of_joining_ismo),
        "date_of_appointment_to_current_grade": _iso(
            application.date_of_appointment_to_current_grade
        ),
        "total_service_ismo": application.total_service_ismo,
        "total_relevant_experience": application.total_relevant_experience,
        "date_of_joining_current_position": _iso(application.date_of_joining_current_position),
        # 4 to 7
        "education": education,
        "experience": experience,
        "certifications": certifications,
        "trainings": trainings,
        # 8 and 9
        "declaration_accepted": application.declaration_accepted,
        "applicant_signature": application.applicant_signature,
    }


# ---------------------------------------------------------------------------
# List / detail
# ---------------------------------------------------------------------------

@require_GET
def list_applications_report(request):
    identity, refusal = require_applications_viewer(request)
    if refusal:
        return JsonResponse({"error": refusal}, status=403)

    try:
        queryset = _apply_filters(request, _base_queryset())
    except FilterError as problem:
        return JsonResponse({"error": str(problem)}, status=400)

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

_SECTION_BLUE = colors.HexColor("#1f4e79")

_styles = getSampleStyleSheet()
_STYLE_TITLE = ParagraphStyle(
    "AppTitle", parent=_styles["Title"], fontSize=14, spaceAfter=6
)
_STYLE_FORM_TITLE = ParagraphStyle(
    "FormTitle", parent=_styles["Title"], fontSize=11.5, spaceAfter=4
)
_STYLE_SUBTITLE = ParagraphStyle(
    "AppSubtitle", parent=_styles["Normal"], fontSize=9, alignment=1,
    fontName="Helvetica-Oblique", textColor=colors.HexColor("#444444"), spaceAfter=12,
)
_STYLE_SECTION_BAR = ParagraphStyle(
    "SectionBar", parent=_styles["Normal"], fontSize=9.5,
    fontName="Helvetica-Bold", textColor=colors.white,
)
_STYLE_LABEL = ParagraphStyle("FieldLabel", parent=_styles["Normal"], fontSize=8, textColor=colors.grey)
_STYLE_VALUE = ParagraphStyle("FieldValue", parent=_styles["Normal"], fontSize=9.5, spaceAfter=6)
_STYLE_BODY = ParagraphStyle("Body", parent=_styles["Normal"], fontSize=9, leading=13)
_STYLE_NOTE = ParagraphStyle(
    "Note", parent=_styles["Normal"], fontSize=7.5, alignment=1,
    fontName="Helvetica-Oblique", textColor=colors.HexColor("#555555"),
)
_STYLE_TABLE_HEAD = ParagraphStyle("TableHead", parent=_styles["Normal"], fontSize=7.5, leading=9.5)
_STYLE_TABLE_CELL = ParagraphStyle("TableCell", parent=_styles["Normal"], fontSize=7.5, leading=9.5)

def _iso(value):
    return value.isoformat() if value else None


def _summary(application: InternalJobApplication) -> dict:
    """One row of the report list."""
    return {
        "id": application.id,
        "reference_no": application.application_reference_no or "",
        "vacancy": application.vacancy_position_title or application.target_job_req.title,
        "vacancy_reference_no": application.vacancy_reference_no or "",
        "target_job_req_id": application.target_job_req_id,
        "full_name": application.full_name,
        "emp_id": application.emp_id,
        "department_function": application.department_function,
        "current_designation": application.current_designation,
        "current_grade": application.current_grade,
        "official_email": application.official_email,
        "mobile_no": application.mobile_no,
        "status": application.status,
        "hr_verification_status": application.hr_verification_status,
        "created_at": application.created_at.strftime("%Y-%m-%d %H:%M"),
        "education_count": application.education.count(),
        "experience_count": application.experience.count(),
        "certification_count": application.certifications.count(),
        "training_count": application.trainings.count(),
    }


def _detail(application: InternalJobApplication) -> dict:
    """Everything the printed form shows, section by section."""
    education = [
        {
            "degree_qualification": row.degree_qualification,
            "major_field_of_study": row.major_field_of_study,
            "institution_university": row.institution_university,
            "country": row.country,
            "year_of_completion": row.year_of_completion,
            "cgpa_division": row.cgpa_division,
        }
        for row in application.education.all()
    ]
    experience = [
        {
            "organization_employer": row.organization_employer,
            "designation": row.designation,
            "grade": row.grade or "",
            "from_date": _iso(row.from_date),
            "to_date": _iso(row.to_date),
            "is_current": row.is_current,
            "duration": row.duration,
            "key_responsibilities": row.key_responsibilities,
        }
        for row in application.experience.all()
    ]
    certifications = [
        {
            "certification_membership": row.certification_membership,
            "certifying_body": row.certifying_body,
            "date_obtained": _iso(row.date_obtained),
            "expiry_date": _iso(row.expiry_date),
            "registration_no": row.registration_no or "",
        }
        for row in application.certifications.all()
    ]
    trainings = [
        {
            "training_title": row.training_title,
            "training_provider": row.training_provider,
            "duration": row.duration or "",
            "date_or_year": row.date_or_year or "",
            "relevant_to_position": row.relevant_to_position,
        }
        for row in application.trainings.all()
    ]

    return {
        **_summary(application),
        # 1. vacancy information
        "vacancy_grade": application.vacancy_grade or "",
        "vacancy_department": application.vacancy_department or "",
        "vacancy_advertisement_date": _iso(application.vacancy_advertisement_date),
        "vacancy_closing_date": _iso(application.vacancy_closing_date),
        # 2. personal & contact information
        "father_or_husband_name": application.father_or_husband_name,
        "cnic": application.cnic,
        "date_of_birth": _iso(application.date_of_birth),
        "gender": application.gender,
        "current_office_location": application.current_office_location,
        "emergency_contact_no": application.emergency_contact_no or "",
        # 3. current employment details
        "date_of_joining_ismo": _iso(application.date_of_joining_ismo),
        "date_of_appointment_to_current_grade": _iso(
            application.date_of_appointment_to_current_grade
        ),
        "total_service_ismo": application.total_service_ismo,
        "total_relevant_experience": application.total_relevant_experience,
        "date_of_joining_current_position": _iso(application.date_of_joining_current_position),
        # 4 to 7
        "education": education,
        "experience": experience,
        "certifications": certifications,
        "trainings": trainings,
        # 8 and 9
        "declaration_accepted": application.declaration_accepted,
        "applicant_signature": application.applicant_signature,
    }


# ---------------------------------------------------------------------------
# List / detail
# ---------------------------------------------------------------------------

@require_GET
def list_applications_report(request):
    identity, refusal = require_applications_viewer(request)
    if refusal:
        return JsonResponse({"error": refusal}, status=403)

    try:
        queryset = _apply_filters(request, _base_queryset())
    except FilterError as problem:
        return JsonResponse({"error": str(problem)}, status=400)

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

_SECTION_BLUE = colors.HexColor("#1f4e79")

_styles = getSampleStyleSheet()
_STYLE_TITLE = ParagraphStyle(
    "AppTitle", parent=_styles["Title"], fontSize=14, spaceAfter=6
)
_STYLE_FORM_TITLE = ParagraphStyle(
    "FormTitle", parent=_styles["Title"], fontSize=11.5, spaceAfter=4
)
_STYLE_SUBTITLE = ParagraphStyle(
    "AppSubtitle", parent=_styles["Normal"], fontSize=9, alignment=1,
    fontName="Helvetica-Oblique", textColor=colors.HexColor("#444444"), spaceAfter=12,
)
_STYLE_SECTION_BAR = ParagraphStyle(
    "SectionBar", parent=_styles["Normal"], fontSize=9.5,
    fontName="Helvetica-Bold", textColor=colors.white,
)
_STYLE_LABEL = ParagraphStyle("FieldLabel", parent=_styles["Normal"], fontSize=8, textColor=colors.grey)
_STYLE_VALUE = ParagraphStyle("FieldValue", parent=_styles["Normal"], fontSize=9.5, spaceAfter=6)
_STYLE_BODY = ParagraphStyle("Body", parent=_styles["Normal"], fontSize=9, leading=13)
_STYLE_NOTE = ParagraphStyle(
    "Note", parent=_styles["Normal"], fontSize=7.5, alignment=1,
    fontName="Helvetica-Oblique", textColor=colors.HexColor("#555555"),
)
_STYLE_TABLE_HEAD = ParagraphStyle("TableHead", parent=_styles["Normal"], fontSize=7.5, leading=9.5)
_STYLE_TABLE_CELL = ParagraphStyle("TableCell", parent=_styles["Normal"], fontSize=7.5, leading=9.5)

# Section 8 of the printed form, word for word. Served to the application page
# as well, so the applicant accepts exactly what the PDF records.
DECLARATION_PARAGRAPHS = (
    "I hereby declare that all information and particulars provided by me in this application "
    "are true, complete and correct to the best of my knowledge and belief. I understand that "
    "any false, incorrect, misleading or concealed information may result in cancellation of my "
    "candidature or, in case of selection/appointment, cancellation of my appointment, in "
    "addition to any disciplinary action that may be taken against me under the applicable "
    "rules, policies and procedures of ISMO.",
    "I further confirm that, based on the eligibility criteria prescribed in the advertisement, "
    "I meet the requirements for the position applied for and am eligible to apply.",
    "I understand that submission of this application does not confer any right to appointment "
    "and that selection shall be made in accordance with the applicable recruitment process and "
    "criteria approved by ISMO.",
    "If selected, I undertake to accept the offer of appointment/promotion to the position for "
    "which I have applied and to comply with the terms and conditions of the offer as prescribed "
    "by ISMO.",
)


def _markup(value) -> str:
    """Applicant text as safe paragraph markup, or an em dash when empty."""
    if value in (None, ""):
        return "—"
    return escape(str(value))


def _field(label: str, value) -> list:
    return [Paragraph(label, _STYLE_LABEL), Paragraph(_markup(value), _STYLE_VALUE)]


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


def _section(number: int, title: str) -> Table:
    """The printed form's numbered blue section bar."""
    bar = Table(
        [[Paragraph(f"{number}. {title.upper()}", _STYLE_SECTION_BAR)]],
        colWidths=[18 * cm],
    )
    bar.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _SECTION_BLUE),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return bar


def _grid(headers: list, rows: list, widths: list) -> Table:
    """One of the form's ruled tables, with its header row repeated on a break."""
    data = [[Paragraph(f"<b>{header}</b>", _STYLE_TABLE_HEAD) for header in headers]]
    for row in rows:
        data.append([Paragraph(_markup(cell), _STYLE_TABLE_CELL) for cell in row])

    table = Table(data, colWidths=widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dce6f1")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#9fb3c8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return table


def _date(value, fmt: str = "%d %b %Y") -> str:
    return value.strftime(fmt) if value else "—"


def _block(number: int, title: str, *content) -> KeepTogether:
    """A section bar and what follows it, kept on one page where it fits.

    Oversized content still splits - reportlab treats this as a preference -
    but a bar with nothing under it never happens.
    """
    flowables = [_section(number, title), Spacer(1, 6)]
    flowables.extend(content)
    return KeepTogether(flowables)


def render_application_pdf(application: InternalJobApplication) -> bytes:
    """The submitted application as the printed form, section by section."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=f"Internal Job Application - {application.full_name}",
        author="Independent System and Market Operator (ISMO)",
    )

    story = [
        Paragraph("INDEPENDENT SYSTEM AND MARKET OPERATOR (ISMO)", _STYLE_TITLE),
        Paragraph("INTERNAL RECRUITMENT – ONLINE APPLICATION FORM", _STYLE_FORM_TITLE),
        Paragraph("For applications against internally advertised positions", _STYLE_SUBTITLE),
    ]

    # ---- 1. vacancy information -----------------------------------------
    story.append(_block(1, "Vacancy Information", _two_col([
        ("Position Title", application.vacancy_position_title or application.target_job_req.title),
        ("Advertisement / Reference No.", application.vacancy_reference_no),
        ("Grade", application.vacancy_grade),
        ("Department / Function", application.vacancy_department),
        ("Date of Advertisement", _date(application.vacancy_advertisement_date)),
        ("Closing Date", _date(application.vacancy_closing_date)),
        ("Current Designation", application.current_designation),
        ("Current Grade", application.current_grade),
    ])))

    # ---- 2. personal & contact information -------------------------------
    story.append(_block(2, "Personal &amp; Contact Information", _two_col([
        ("Employee ID", application.emp_id),
        ("Full Name", application.full_name),
        ("Father's / Husband's Name", application.father_or_husband_name),
        ("CNIC No.", application.cnic),
        ("Date of Birth", _date(application.date_of_birth)),
        ("Gender", application.gender),
        ("Official Email Address", application.official_email),
        ("Mobile / Contact No.", application.mobile_no),
        ("Current Office / Location", application.current_office_location),
        ("Emergency Contact No. (optional)", application.emergency_contact_no),
    ])))

    # ---- 3. current employment details -----------------------------------
    story.append(_block(3, "Current Employment Details", _two_col([
        ("Date of Joining ISMO", _date(application.date_of_joining_ismo)),
        ("Current Designation", application.current_designation),
        ("Current Grade", application.current_grade),
        ("Department / Function", application.department_function),
        ("Date of Appointment to Current Grade",
         _date(application.date_of_appointment_to_current_grade)),
        ("Total Service in ISMO", application.total_service_ismo),
        ("Total Relevant Experience", application.total_relevant_experience),
        ("Date of Joining Current Position",
         _date(application.date_of_joining_current_position)),
    ])))

    # ---- 4. educational background ---------------------------------------
    story.append(_section(4, "Educational Background"))
    story.append(Spacer(1, 6))
    education = list(application.education.all())
    if education:
        story.append(_grid(
            ["Degree / Qualification", "Major / Field of Study", "Institution / University",
             "Country", "Year of Completion", "CGPA / Division"],
            [[row.degree_qualification, row.major_field_of_study, row.institution_university,
              row.country, row.year_of_completion, row.cgpa_division] for row in education],
            [3.4 * cm, 3.2 * cm, 4 * cm, 2.4 * cm, 2.5 * cm, 2.5 * cm],
        ))
    else:
        story.append(Paragraph("No qualifications listed.", _STYLE_BODY))

    # ---- 5. employment history / professional experience -----------------
    story.append(_section(5, "Employment History / Professional Experience"))
    story.append(Spacer(1, 6))
    experience = list(application.experience.all())
    if experience:
        story.append(_grid(
            ["Organization / Employer", "Designation", "Grade", "From", "To", "Duration",
             "Key Responsibilities / Relevant Experience"],
            [[row.organization_employer, row.designation, row.grade,
              _date(row.from_date, "%b %Y"),
              "Present" if row.is_current else _date(row.to_date, "%b %Y"),
              row.duration, row.key_responsibilities] for row in experience],
            [3 * cm, 2.4 * cm, 1.4 * cm, 1.8 * cm, 1.8 * cm, 2.1 * cm, 5.5 * cm],
        ))
    else:
        story.append(Paragraph("No employment history listed.", _STYLE_BODY))

    # ---- 6. professional certifications / memberships --------------------
    story.append(_section(6, "Professional Certifications / Memberships"))
    story.append(Spacer(1, 6))
    certifications = list(application.certifications.all())
    if certifications:
        story.append(_grid(
            ["Certification / Membership", "Certifying / Professional Body", "Date Obtained",
             "Expiry Date", "Registration / Membership No."],
            [[row.certification_membership, row.certifying_body,
              _date(row.date_obtained), _date(row.expiry_date), row.registration_no]
             for row in certifications],
            [4.2 * cm, 4.4 * cm, 2.6 * cm, 2.6 * cm, 4.2 * cm],
        ))
    else:
        story.append(Paragraph("None declared.", _STYLE_BODY))

    # ---- 7. trainings & professional development -------------------------
    story.append(_section(7, "Trainings &amp; Professional Development"))
    story.append(Spacer(1, 6))
    trainings = list(application.trainings.all())
    if trainings:
        story.append(_grid(
            ["Training / Course Title", "Training Provider / Institute", "Duration",
             "Date / Year", "Relevant to Position"],
            [[row.training_title, row.training_provider, row.duration, row.date_or_year,
              "Yes" if row.relevant_to_position else "No"] for row in trainings],
            [4.6 * cm, 4.6 * cm, 2.6 * cm, 2.6 * cm, 3.6 * cm],
        ))
    else:
        story.append(Paragraph("None declared.", _STYLE_BODY))

    # ---- 8. declaration & undertaking ------------------------------------
    story.append(_section(8, "Declaration &amp; Undertaking"))
    story.append(Spacer(1, 6))
    for paragraph in DECLARATION_PARAGRAPHS:
        story.append(Paragraph(paragraph, _STYLE_BODY))
        story.append(Spacer(1, 5))
    story.append(Paragraph(
        f"Accepted by the applicant: <b>{'Yes' if application.declaration_accepted else 'No'}</b>",
        _STYLE_BODY,
    ))

    # ---- 9. submission record --------------------------------------------
    story.append(_block(9, "Submission Record", _two_col([
        ("Applicant Name", application.full_name),
        ("Employee ID", application.emp_id),
        ("Date of Submission", application.created_at.strftime("%d %b %Y, %H:%M")),
        ("Application Reference No.", application.application_reference_no),
        ("Applicant's Electronic Signature / Confirmation", application.applicant_signature),
        ("HR Verification Status", application.hr_verification_status),
    ])))
    story.append(Spacer(1, 4))
    story.append(Paragraph(f"Note: {SUBMISSION_NOTE}", _STYLE_NOTE))

    doc.build(story)
    return buffer.getvalue()


def _safe_filename(application: InternalJobApplication) -> str:
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", application.full_name or "applicant").strip("_")
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

    try:
        queryset = _apply_filters(request, _base_queryset())
    except FilterError as problem:
        return JsonResponse({"error": str(problem)}, status=400)

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