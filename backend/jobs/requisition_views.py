"""Maintaining the vacancies the application form offers.

The application form reads `requisitions/`, which lists only what can still be
applied for. This module is the other side: the screen where HR advertises a
post, edits it, closes it, or removes one that nobody has applied to.

A vacancy can carry its advertisement as a PDF. It is uploaded and removed here
by whoever manages vacancies, and viewed by anyone through
`requisitions/<id>/advertisement/view/` - the same people who can see the
vacancy on the application form.

A vacancy is only ever deleted when it is neither live (open and not past its
closing date) nor applied for. A live advertisement is being read by employees
right now; an applied-for one is referenced by the applications filed against it.
"""

import json
import logging
from datetime import date

from django.db.models import Count
from django.db.models.deletion import ProtectedError
from django.http import FileResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from sqlalchemy import text

from db import SessionLocal

from .models import JobDescription, JobRequisition
from .permissions import require_requisition_manager

logger = logging.getLogger(__name__)

MAX_TITLE = 200
MAX_DEPARTMENT = 200
MAX_LOCATION = 200
MAX_DESCRIPTION = 4000
MAX_REFERENCE = 100
MAX_GRADE = 40

# Advertisement PDFs. Generous for a scanned notice, small enough that the
# server is not used as file storage.
MAX_ADVERTISEMENT_BYTES = 10 * 1024 * 1024


def _text(value) -> str:
    return str(value or "").strip()


def department_and_location_options() -> dict:
    """The grades, departments (the `sections` table) and locations a vacancy
    can name. Grades come in seniority order (by id: MG-01 up)."""
    session = SessionLocal()
    try:
        sections = session.execute(
            text("SELECT name FROM sections WHERE name IS NOT NULL ORDER BY name")
        ).fetchall()
        locations = session.execute(
            text("SELECT name FROM locations WHERE name IS NOT NULL ORDER BY name")
        ).fetchall()
        grades = session.execute(
            text("SELECT name FROM grades WHERE name IS NOT NULL ORDER BY id")
        ).fetchall()
    finally:
        session.close()
    return {
        "grades": [row.name.strip() for row in grades if row.name and row.name.strip()],
        "departments": [row.name.strip() for row in sections if row.name and row.name.strip()],
        "locations": [row.name.strip() for row in locations if row.name and row.name.strip()],
    }


@require_GET
def form_options(request):
    """What the vacancy form's Grade, Department and Location dropdowns offer."""
    try:
        return JsonResponse(department_and_location_options(), status=200)
    except Exception:
        logger.exception("could not read sections / locations for the vacancy form")
        return JsonResponse(
            {"error": "The grade, department and location lists could not be loaded"}, status=503
        )


def delete_refusal(requisition: JobRequisition, application_count: int):
    """Why this vacancy cannot be deleted, or None when it can."""
    if requisition.is_live:
        return (
            "This vacancy is live on the application form, so it cannot be deleted. "
            "Close it first."
        )
    if application_count:
        return (
            f"{application_count} application(s) have been submitted for this vacancy, "
            "so it cannot be deleted. Keep it closed instead."
        )
    return None


def advertisement_url(requisition: JobRequisition) -> str:
    """Where the advertisement PDF is viewed, relative to the API root."""
    if not requisition.advertisement_pdf:
        return ""
    return f"/jobs/requisitions/{requisition.id}/advertisement/view/"


def _serialize(requisition: JobRequisition, application_count: int = 0) -> dict:
    closing = requisition.closing_date
    advertised = requisition.advertisement_date
    refusal = delete_refusal(requisition, application_count)
    return {
        "id": requisition.id,
        "title": requisition.title,
        "reference_no": requisition.reference_no,
        "grade": requisition.grade,
        "department": requisition.department,
        "location": requisition.location,
        "description": requisition.description,
        "advertisement_date": advertised.isoformat() if advertised else None,
        "closing_date": closing.isoformat() if closing else None,
        # The description behind the post, so the screen can show which one is
        # attached without a second request.
        "job_description_id": requisition.job_description_id,
        "job_description_title": (
            requisition.job_description.title if requisition.job_description_id else ""
        ),
        "job_description_code": (
            requisition.job_description.code or "" if requisition.job_description_id else ""
        ),
        "is_open": requisition.is_open,
        # Distinguishes "closed by HR" from "the closing date has passed", which
        # look the same to an applicant but not to whoever is maintaining it.
        "has_expired": bool(closing and closing < date.today() and requisition.is_open),
        "is_live": requisition.is_live,
        "application_count": application_count,
        # The page disables Delete and says why; the server refuses regardless.
        "can_delete": refusal is None,
        "delete_blocked_reason": refusal or "",
        "advertisement_url": advertisement_url(requisition),
        "advertisement_name": requisition.advertisement_pdf_name
        if requisition.advertisement_pdf else "",
        "created_at": requisition.created_at.strftime("%Y-%m-%d %H:%M")
        if requisition.created_at
        else None,
    }


def _validate(data, existing: JobRequisition | None = None):
    """Returns (cleaned, errors)."""
    errors = {}
    cleaned = {}

    title = _text(data.get("title"))
    if not title:
        errors["title"] = "A job title is required"
    elif len(title) < 3:
        errors["title"] = "That title looks too short"
    elif len(title) > MAX_TITLE:
        errors["title"] = f"Keep the title within {MAX_TITLE} characters"
    cleaned["title"] = title

    for field, label, maximum in (
        ("reference_no", "Advertisement / reference no.", MAX_REFERENCE),
        ("grade", "Grade", MAX_GRADE),
        ("department", "Department / function", MAX_DEPARTMENT),
        ("location", "Location", MAX_LOCATION),
        ("description", "Description", MAX_DESCRIPTION),
    ):
        value = _text(data.get(field))
        if len(value) > maximum:
            errors[field] = f"Keep {label.lower()} within {maximum} characters"
        cleaned[field] = value or None

    # Grade, department and location come from the grades, sections and
    # locations tables. An older vacancy keeps whatever it was saved with until
    # it is changed.
    try:
        options = department_and_location_options()
    except Exception:
        logger.exception("could not read sections / locations to check a vacancy")
        options = None
    if options is not None:
        for field, allowed, label in (
            ("grade", options.get("grades", []), "grade"),
            ("department", options["departments"], "department"),
            ("location", options["locations"], "location"),
        ):
            value = cleaned.get(field)
            unchanged = existing is not None and (getattr(existing, field) or None) == value
            if value and not unchanged and value not in allowed:
                errors[field] = f"Choose a {label} from the list"

    advertised_raw = _text(data.get("advertisement_date"))
    advertised = None
    if advertised_raw:
        try:
            advertised = date.fromisoformat(advertised_raw[:10])
        except ValueError:
            errors["advertisement_date"] = "Use a date like 2026-09-30"
        else:
            if advertised > date.today():
                errors["advertisement_date"] = "The advertisement date cannot be in the future"
    cleaned["advertisement_date"] = advertised

    closing_raw = _text(data.get("closing_date"))
    closing = None
    if closing_raw:
        try:
            closing = date.fromisoformat(closing_raw[:10])
        except ValueError:
            errors["closing_date"] = "Use a date like 2026-09-30"
        else:
            # A closing date already past would advertise a post nobody can
            # apply for. Editing an old vacancy without touching its date is
            # allowed, so an unchanged past date is left alone.
            unchanged = existing is not None and existing.closing_date == closing
            if closing < date.today() and not unchanged:
                errors["closing_date"] = "The closing date cannot be in the past"
            elif advertised and closing < advertised:
                errors["closing_date"] = "The closing date is before the advertisement date"
    cleaned["closing_date"] = closing

    raw_description = data.get("job_description_id")
    description_id = None
    if raw_description in (None, "", 0, "0"):
        # Every opening carries its own description. Only a vacancy advertised
        # before that rule, and still without one, may be saved without.
        grandfathered = existing is not None and existing.job_description_id is None
        if not grandfathered:
            errors["job_description_id"] = (
                "Choose the job description for this position"
                if existing is None
                else "A job description cannot be removed from an opening"
            )
    else:
        try:
            description_id = int(raw_description)
        except (TypeError, ValueError):
            errors["job_description_id"] = "That is not a job description"
        else:
            description = JobDescription.objects.filter(id=description_id).first()
            if description is None:
                errors["job_description_id"] = "That job description no longer exists"
            elif not description.is_active and (
                existing is None or existing.job_description_id != description_id
            ):
                # A retired description stays on the vacancies that already use
                # it, but should not be attached to another.
                errors["job_description_id"] = "That job description is no longer active"
            else:
                # One opening per description: a new position gets a new one.
                taken = JobRequisition.objects.filter(job_description_id=description_id)
                if existing is not None:
                    taken = taken.exclude(id=existing.id)
                holder = taken.first()
                if holder is not None:
                    errors["job_description_id"] = (
                        f"This job description already belongs to the opening "
                        f"\"{holder.title}\". Each opening needs its own - create a "
                        f"new job description for this position."
                    )
    cleaned["job_description_id"] = description_id

    cleaned["is_open"] = bool(data.get("is_open", True))

    # A duplicate title is almost always a double submission rather than two
    # genuinely separate posts.
    if title and not errors.get("title"):
        clash = JobRequisition.objects.filter(title__iexact=title)
        if existing is not None:
            clash = clash.exclude(id=existing.id)
        if clash.exists():
            errors["title"] = "A vacancy with this title already exists"

    reference = cleaned.get("reference_no")
    if reference and not errors.get("reference_no"):
        clash = JobRequisition.objects.filter(reference_no__iexact=reference)
        if existing is not None:
            clash = clash.exclude(id=existing.id)
        if clash.exists():
            errors["reference_no"] = "Another vacancy already uses this reference number"

    return cleaned, errors


@require_GET
def manage_list(request):
    """Every vacancy, open or closed, with how many have applied to each."""
    rows = (
        JobRequisition.objects.select_related("job_description")
        .annotate(application_count=Count("applications"))
        .order_by("-created_at")
    )

    return JsonResponse(
        [_serialize(row, row.application_count) for row in rows], safe=False, status=200
    )


@csrf_exempt
@require_POST
def create_requisition(request):
    identity, refusal = require_requisition_manager(request)
    if refusal:
        return JsonResponse({"error": refusal}, status=403)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    cleaned, errors = _validate(data)
    if errors:
        return JsonResponse({"errors": errors}, status=400)

    requisition = JobRequisition.objects.create(**cleaned)
    logger.info(
        "job requisition %s created by auth user %s: %s",
        requisition.id, identity.get("user_id"), requisition.title,
    )

    return JsonResponse(_serialize(requisition), status=201)


@csrf_exempt
@require_POST
def update_requisition(request, requisition_id: int):
    identity, refusal = require_requisition_manager(request)
    if refusal:
        return JsonResponse({"error": refusal}, status=403)

    requisition = JobRequisition.objects.filter(id=requisition_id).first()
    if requisition is None:
        return JsonResponse({"error": "That vacancy no longer exists"}, status=404)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    cleaned, errors = _validate(data, existing=requisition)
    if errors:
        return JsonResponse({"errors": errors}, status=400)

    for field, value in cleaned.items():
        setattr(requisition, field, value)
    requisition.save()

    logger.info(
        "job requisition %s updated by auth user %s (open=%s)",
        requisition.id, identity.get("user_id"), requisition.is_open,
    )

    count = requisition.applications.count()
    return JsonResponse(_serialize(requisition, count), status=200)


@csrf_exempt
@require_POST
def delete_requisition(request, requisition_id: int):
    """Remove a vacancy that is not live and that nobody has applied to.

    A live vacancy is on the application form right now, so it has to be closed
    first. Applications reference the vacancy they were filed against, so one
    with applications is never deleted. Either way the response says why rather
    than failing obscurely.
    """
    identity, refusal = require_requisition_manager(request)
    if refusal:
        return JsonResponse({"error": refusal}, status=403)

    requisition = JobRequisition.objects.filter(id=requisition_id).first()
    if requisition is None:
        return JsonResponse({"error": "That vacancy no longer exists"}, status=404)

    refusal = delete_refusal(requisition, requisition.applications.count())
    if refusal:
        return JsonResponse({"error": refusal}, status=409)

    advertisement = requisition.advertisement_pdf
    try:
        requisition.delete()
    except ProtectedError:
        return JsonResponse(
            {"error": "This vacancy has applications and cannot be deleted."},
            status=409,
        )

    if advertisement:
        advertisement.delete(save=False)

    logger.info(
        "job requisition %s deleted by auth user %s", requisition_id, identity.get("user_id")
    )
    return JsonResponse({"detail": "Vacancy deleted"}, status=200)


# ---------------------------------------------------------------------------
# The advertisement PDF
# ---------------------------------------------------------------------------

def _pdf_problem(upload) -> str | None:
    """Why an uploaded file is not an acceptable advertisement, or None."""
    if upload is None:
        return "Choose a PDF file to upload"
    if not upload.name.lower().endswith(".pdf"):
        return "The advertisement must be a PDF file"
    if upload.size == 0:
        return "That file is empty"
    if upload.size > MAX_ADVERTISEMENT_BYTES:
        return f"Keep the PDF within {MAX_ADVERTISEMENT_BYTES // (1024 * 1024)} MB"
    # The extension says nothing about the content; a real PDF starts with this.
    head = upload.read(5)
    upload.seek(0)
    if head != b"%PDF-":
        return "That file is not a valid PDF"
    return None


@csrf_exempt
@require_POST
def upload_advertisement(request, requisition_id: int):
    """Attach the advertisement PDF to a vacancy, replacing any earlier one."""
    identity, refusal = require_requisition_manager(request)
    if refusal:
        return JsonResponse({"error": refusal}, status=403)

    requisition = JobRequisition.objects.filter(id=requisition_id).first()
    if requisition is None:
        return JsonResponse({"error": "That vacancy no longer exists"}, status=404)

    upload = request.FILES.get("file")
    problem = _pdf_problem(upload)
    if problem:
        return JsonResponse({"errors": {"advertisement_pdf": problem}}, status=400)

    previous = requisition.advertisement_pdf
    previous_name = previous.name if previous else None

    original_name = upload.name.replace("\\", "/").split("/")[-1][:255]
    requisition.advertisement_pdf.save(f"vacancy-{requisition.id}.pdf", upload, save=False)
    requisition.advertisement_pdf_name = original_name
    requisition.save(update_fields=["advertisement_pdf", "advertisement_pdf_name"])

    # The old file is only removed once the new one is safely recorded.
    if previous_name and previous_name != requisition.advertisement_pdf.name:
        requisition.advertisement_pdf.storage.delete(previous_name)

    logger.info(
        "advertisement for job requisition %s uploaded by auth user %s (%d bytes)",
        requisition.id, identity.get("user_id"), upload.size,
    )
    count = requisition.applications.count()
    return JsonResponse(_serialize(requisition, count), status=200)


@csrf_exempt
@require_POST
def remove_advertisement(request, requisition_id: int):
    identity, refusal = require_requisition_manager(request)
    if refusal:
        return JsonResponse({"error": refusal}, status=403)

    requisition = JobRequisition.objects.filter(id=requisition_id).first()
    if requisition is None:
        return JsonResponse({"error": "That vacancy no longer exists"}, status=404)

    if requisition.advertisement_pdf:
        requisition.advertisement_pdf.delete(save=False)
    requisition.advertisement_pdf = None
    requisition.advertisement_pdf_name = ""
    requisition.save(update_fields=["advertisement_pdf", "advertisement_pdf_name"])

    logger.info(
        "advertisement for job requisition %s removed by auth user %s",
        requisition.id, identity.get("user_id"),
    )
    count = requisition.applications.count()
    return JsonResponse(_serialize(requisition, count), status=200)


@require_GET
def view_advertisement(request, requisition_id: int):
    """The advertisement PDF, opened in the browser's own viewer."""
    requisition = JobRequisition.objects.filter(id=requisition_id).first()
    if requisition is None or not requisition.advertisement_pdf:
        return JsonResponse({"error": "No advertisement is attached to this vacancy"},
                            status=404)
    try:
        handle = requisition.advertisement_pdf.open("rb")
    except FileNotFoundError:
        logger.error("advertisement file missing for job requisition %s: %s",
                     requisition.id, requisition.advertisement_pdf.name)
        return JsonResponse({"error": "The advertisement file could not be found"},
                            status=404)

    return FileResponse(
        handle,
        content_type="application/pdf",
        as_attachment=request.GET.get("download") == "1",
        filename=requisition.advertisement_pdf_name or f"vacancy-{requisition.id}.pdf",
    )
