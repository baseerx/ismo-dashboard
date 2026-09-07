"""Maintaining the vacancies the application form offers.

The application form reads `requisitions/`, which lists only what can still be
applied for. This module is the other side: the screen where HR advertises a
post, edits it, closes it, or removes one that nobody has applied to.
"""

import json
import logging
from datetime import date

from django.db.models import Count
from django.db.models.deletion import ProtectedError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import JobDescription, JobRequisition
from .permissions import require_requisition_manager

logger = logging.getLogger(__name__)

MAX_TITLE = 200
MAX_DEPARTMENT = 200
MAX_LOCATION = 200
MAX_DESCRIPTION = 4000
MAX_REFERENCE = 100
MAX_GRADE = 40


def _text(value) -> str:
    return str(value or "").strip()


def _serialize(requisition: JobRequisition, application_count: int = 0) -> dict:
    closing = requisition.closing_date
    advertised = requisition.advertisement_date
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
        "application_count": application_count,
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
    if raw_description not in (None, "", 0, "0"):
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
    """Remove a vacancy nobody has applied to.

    Applications reference the vacancy they were filed against, so one with
    applications is never deleted - closing it is what the caller wants, and the
    response says so rather than failing obscurely.
    """
    identity, refusal = require_requisition_manager(request)
    if refusal:
        return JsonResponse({"error": refusal}, status=403)

    requisition = JobRequisition.objects.filter(id=requisition_id).first()
    if requisition is None:
        return JsonResponse({"error": "That vacancy no longer exists"}, status=404)

    count = requisition.applications.count()
    if count:
        return JsonResponse(
            {
                "error": (
                    f"{count} application(s) have been submitted for this vacancy, "
                    "so it cannot be deleted. Close it instead to take it off the form."
                )
            },
            status=409,
        )

    try:
        requisition.delete()
    except ProtectedError:
        return JsonResponse(
            {"error": "This vacancy has applications and cannot be deleted."},
            status=409,
        )

    logger.info(
        "job requisition %s deleted by auth user %s", requisition_id, identity.get("user_id")
    )
    return JsonResponse({"detail": "Vacancy deleted"}, status=200)
