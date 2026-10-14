"""The HR-facing side of the internal job application system.

Where `views.py` lets an employee see their own submissions, this module is
for whoever reviews them: list everything (with filters), pull the full
record for one applicant into a popup, download a single application as a
PDF, or export a filtered batch as a ZIP of PDFs.
"""

import io
import json
import logging
import re
import zipfile
from xml.sax.saxutils import escape
from datetime import datetime

from django.core.paginator import Paginator
from django.db import DatabaseError
from django.db.models import Q
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

from .form_text import (
    ACK_DATA_ACCURACY,
    ACK_MANAGER_NOTIFIED,
    DECLARATION_PARAGRAPHS,
    SUBMISSION_NOTE,
)
from .models import InternalJobApplication, JobRequisition
from .reports_permissions import require_applications_viewer

# A ZIP this size is already a multi-minute request; past this, the caller
# should narrow the filters instead of exporting everything at once.
MAX_ZIP_APPLICATIONS = 300

DEFAULT_PAGE_SIZE = 50

# How the prefilled fields are named on the form, for the "changed from the
# employee record" list.
RECORD_FIELD_LABELS = {
    "emp_id": "Employee ID",
    "full_name": "Employee Full Name",
    "department_function": "Current Department",
    "current_designation": "Current Position Title",
    "current_grade": "Current Grade",
    "current_supervisor_name": "Current Supervisor Name",
    "cnic": "CNIC No.",
    "gender": "Gender",
    "official_email": "Corporate Email Address",
    "current_office_location": "Current Office / Location",
}


def record_changes(application: InternalJobApplication) -> list:
    """What the applicant corrected from the employee record, labelled."""
    return [
        {
            "field": field,
            "label": RECORD_FIELD_LABELS.get(field, field),
            "record": change.get("record", ""),
            "submitted": change.get("submitted", ""),
        }
        for field, change in application.record_changes.items()
        if isinstance(change, dict)
    ]

logger = logging.getLogger(__name__)

# What the page shows when the tables cannot be read - most often a backend
# deployed without its migrations. The detail goes to the log, not the browser.
DATABASE_PROBLEM = (
    "The job applications could not be read from the database. This usually "
    "means the latest database update has not been applied on the server "
    "(python manage.py migrate). Please contact the system administrator."
)


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
            | queryset.filter(skills_technical_tags__icontains=search)
            | queryset.filter(skills_soft_checkboxes__icontains=search)
        )

    # Skills matrix filter: an exact tag, technical or soft, ignoring case.
    # The lists are stored as JSON, so the quoted value matches one whole tag
    # ("SQL") and not a tag that merely contains it ("PostgreSQL").
    skill = (request.GET.get("skill") or "").strip()
    if skill:
        quoted = json.dumps(skill)
        queryset = queryset.filter(
            Q(skills_technical_tags__icontains=quoted)
            | Q(skills_soft_checkboxes__icontains=quoted)
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
        "current_supervisor_name": application.current_supervisor_name,
        # How many prefilled fields the applicant changed - flagged in the list.
        "record_change_count": len(application.record_changes),
        "technical_skills": application.technical_skills,
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
            "key_achievements": row.key_achievements,
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
        "personal_email": application.personal_email or "",
        "preferred_contact_method": application.preferred_contact_method,
        "current_supervisor_erp_id": application.current_supervisor_erp_id,
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
        "record_changes": record_changes(application),
        # skills, statement of purpose, acknowledgements
        "soft_skills": application.soft_skills,
        "application_rationale_sop": application.application_rationale_sop,
        "ack_manager_notified_bool": application.ack_manager_notified_bool,
        "ack_data_accuracy_bool": application.ack_data_accuracy_bool,
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

    try:
        paginator = Paginator(queryset, page_size)
        page = paginator.get_page(page_number)
        results = [_summary(app) for app in page.object_list]
        statuses = list(
            InternalJobApplication.objects.order_by()
            .values_list("status", flat=True)
            .distinct()
        )
        # Lets an empty page say whether nothing has been filed at all, or
        # only nothing that matches the filters, and whether anything is
        # advertised for people to apply to.
        total_applications = InternalJobApplication.objects.count()
        open_vacancies = JobRequisition.objects.filter(is_open=True).count()
    except DatabaseError:
        logger.exception("job applications report could not be read")
        return JsonResponse({"error": DATABASE_PROBLEM}, status=503)

    return JsonResponse(
        {
            "results": results,
            "count": paginator.count,
            "page": page.number,
            "num_pages": paginator.num_pages,
            "statuses": statuses,
            "total_applications": total_applications,
            "open_vacancies": open_vacancies,
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


def _yes(value: bool) -> str:
    return "Yes" if value else "No"


def render_application_pdf(application: InternalJobApplication) -> bytes:
    """The submitted application in the six sections of the specification."""
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

    # ---- 1. target position & internal validation ------------------------
    story.append(_block(1, "Target Position &amp; Internal Validation", _two_col([
        ("Job Requisition / Opening",
         application.vacancy_position_title or application.target_job_req.title),
        ("Advertisement / Reference No.", application.vacancy_reference_no),
        ("Grade", application.vacancy_grade),
        ("Department / Function", application.vacancy_department),
        ("Date of Advertisement", _date(application.vacancy_advertisement_date)),
        ("Closing Date", _date(application.vacancy_closing_date)),
        ("Employee Full Name", application.full_name),
        ("Employee ID", application.emp_id),
        ("Current Department", application.department_function),
        ("Current Position Title", application.current_designation),
        ("Current Grade", application.current_grade),
        ("Current Supervisor Name", application.current_supervisor_name or "None on record"),
        ("Date of Joining ISMO", _date(application.date_of_joining_ismo)),
        ("Date of Joining Current Position",
         _date(application.date_of_joining_current_position)),
        ("Date of Appointment to Current Grade",
         _date(application.date_of_appointment_to_current_grade)),
        ("Total Service in ISMO", application.total_service_ismo),
        ("Total Relevant Experience", application.total_relevant_experience),
    ])))

    changes = record_changes(application)
    if changes:
        story.append(Paragraph(
            "<b>Changed by the applicant from the employee record</b>", _STYLE_BODY
        ))
        story.append(Spacer(1, 4))
        story.append(_grid(
            ["Field", "Employee record", "Submitted"],
            [[change["label"], change["record"], change["submitted"]] for change in changes],
            [5 * cm, 6.5 * cm, 6.5 * cm],
        ))
        story.append(Spacer(1, 8))

    # ---- 2. personal & contact information -------------------------------
    story.append(_block(2, "Personal &amp; Contact Information", _two_col([
        ("Contact Phone Number", application.mobile_no),
        ("Corporate Email Address", application.official_email),
        ("Personal Email Address (optional)", application.personal_email),
        ("Internal Communication Channel", application.preferred_contact_method),
        ("Father's / Husband's Name", application.father_or_husband_name),
        ("CNIC No.", application.cnic),
        ("Date of Birth", _date(application.date_of_birth)),
        ("Gender", application.gender),
        ("Current Office / Location", application.current_office_location),
        ("Emergency Contact No. (optional)", application.emergency_contact_no),
    ])))

    # ---- 3. educational background ---------------------------------------
    story.append(_section(3, "Educational Background"))
    story.append(Spacer(1, 6))
    education = list(application.education.all())
    if education:
        story.append(_grid(
            ["Degree / Certificate Earned", "Major / Field of Study",
             "Institution / University", "Country", "Graduation Year",
             "CGPA / Percentage / Grade"],
            [[row.degree_qualification, row.major_field_of_study, row.institution_university,
              row.country, row.year_of_completion, row.cgpa_division] for row in education],
            [3.4 * cm, 3.2 * cm, 4 * cm, 2.4 * cm, 2.5 * cm, 2.5 * cm],
        ))
    else:
        story.append(Paragraph("No qualifications listed.", _STYLE_BODY))

    # ---- 4. professional experience --------------------------------------
    story.append(_section(4, "Professional Experience"))
    story.append(Spacer(1, 6))
    experience = list(application.experience.all())
    if experience:
        story.append(_grid(
            ["Job Position Title", "Organization / Company", "Grade", "Start Date",
             "End Date", "Duration"],
            [[row.designation, row.organization_employer, row.grade,
              _date(row.from_date, "%b %Y"),
              "Present Role" if row.is_current else _date(row.to_date, "%b %Y"),
              row.duration] for row in experience],
            [4 * cm, 4.6 * cm, 1.6 * cm, 2.4 * cm, 2.6 * cm, 2.8 * cm],
        ))
        for index, row in enumerate(experience, start=1):
            story.append(Spacer(1, 5))
            story.append(Paragraph(
                f"<b>{index}. {_markup(row.designation)}</b> – Key Responsibilities &amp; Roles",
                _STYLE_BODY,
            ))
            story.append(Paragraph(_markup(row.key_responsibilities), _STYLE_BODY))
            if row.key_achievements:
                story.append(Paragraph("<b>Key Achievements &amp; Projects</b>", _STYLE_BODY))
                story.append(Paragraph(_markup(row.key_achievements), _STYLE_BODY))
    else:
        story.append(Paragraph("No employment history listed.", _STYLE_BODY))

    # ---- 5. skills matrix & professional certifications ------------------
    story.append(_block(5, "Skills Matrix &amp; Professional Certifications", _two_col([
        ("Core Technical Skills", ", ".join(application.technical_skills)),
        ("Soft Skills / Leadership Capabilities", ", ".join(application.soft_skills)),
    ])))
    story.append(Paragraph("<b>Active Professional Certifications</b>", _STYLE_BODY))
    story.append(Spacer(1, 4))
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

    story.append(Spacer(1, 6))
    story.append(Paragraph("<b>Trainings &amp; Professional Development</b>", _STYLE_BODY))
    story.append(Spacer(1, 4))
    trainings = list(application.trainings.all())
    if trainings:
        story.append(_grid(
            ["Training / Course Title", "Training Provider / Institute", "Duration",
             "Date / Year", "Relevant to Position"],
            [[row.training_title, row.training_provider, row.duration, row.date_or_year,
              _yes(row.relevant_to_position)] for row in trainings],
            [4.6 * cm, 4.6 * cm, 2.6 * cm, 2.6 * cm, 3.6 * cm],
        ))
    else:
        story.append(Paragraph("None declared.", _STYLE_BODY))

    # ---- 6. statement of purpose & workflow acknowledgement --------------
    story.append(_section(6, "Statement of Purpose &amp; Workflow Acknowledgement"))
    story.append(Spacer(1, 6))
    story.append(Paragraph("<b>Why are you applying for this position?</b>", _STYLE_BODY))
    story.append(Paragraph(_markup(application.application_rationale_sop), _STYLE_BODY))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"{escape(ACK_MANAGER_NOTIFIED)}: <b>{_yes(application.ack_manager_notified_bool)}</b>",
        _STYLE_BODY,
    ))
    story.append(Paragraph(
        f"{escape(ACK_DATA_ACCURACY)}: <b>{_yes(application.ack_data_accuracy_bool)}</b>",
        _STYLE_BODY,
    ))
    story.append(Spacer(1, 8))
    story.append(Paragraph("<b>Declaration &amp; Undertaking</b>", _STYLE_BODY))
    story.append(Spacer(1, 4))
    for paragraph in DECLARATION_PARAGRAPHS:
        story.append(Paragraph(paragraph, _STYLE_BODY))
        story.append(Spacer(1, 5))
    story.append(Paragraph(
        f"Accepted by the applicant: <b>{_yes(application.declaration_accepted)}</b>",
        _STYLE_BODY,
    ))
    story.append(Spacer(1, 8))
    story.append(_two_col([
        ("Applicant Name", application.full_name),
        ("Employee ID", application.emp_id),
        ("Date of Submission", application.created_at.strftime("%d %b %Y, %H:%M")),
        ("Application Reference No.", application.application_reference_no),
        ("Applicant's Electronic Signature / Confirmation", application.applicant_signature),
        ("HR Verification Status", application.hr_verification_status),
    ]))
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