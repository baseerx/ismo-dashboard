"""The job description library.

Descriptions are written once here and attached to the vacancies advertised for
them, so the same post does not have its duties retyped every time it is
advertised. Reading is open, like the rest of this API - the application form
shows the description to whoever is applying. Writing needs the rights for this
page.
"""

import json
import logging

from django.db.models import Count
from django.db.models.deletion import ProtectedError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import JobDescription
from .permissions import require_description_manager

logger = logging.getLogger(__name__)

MAX_TITLE = 200
MAX_CODE = 60
MAX_DEPARTMENT = 200
MAX_GRADE = 40
MAX_REPORTS_TO = 200
# The body fields. Long enough for a real description, short enough that one
# runaway paste cannot fill the table.
MAX_BODY = 8000
MIN_RESPONSIBILITIES = 20


def _text(value) -> str:
    return str(value or "").strip()


def _serialize(description: JobDescription, requisition_count: int = 0) -> dict:
    return {
        "id": description.id,
        "title": description.title,
        "code": description.code or "",
        "department": description.department or "",
        "grade": description.grade or "",
        "reports_to": description.reports_to or "",
        "job_purpose": description.job_purpose or "",
        "key_responsibilities": description.key_responsibilities or "",
        "qualifications": description.qualifications or "",
        "experience_required": description.experience_required or "",
        "skills_competencies": description.skills_competencies or "",
        "is_active": description.is_active,
        "requisition_count": requisition_count,
        "created_at": description.created_at.strftime("%Y-%m-%d %H:%M")
        if description.created_at
        else None,
    }


def body_for_form(description: JobDescription | None) -> dict | None:
    """What the application form shows under a chosen vacancy.

    Shared with jobs/views.py so the applicant and the library never disagree
    about what a description says.
    """
    if description is None:
        return None
    return {
        "id": description.id,
        "title": description.title,
        "code": description.code or "",
        "department": description.department or "",
        "grade": description.grade or "",
        "reports_to": description.reports_to or "",
        "job_purpose": description.job_purpose or "",
        "key_responsibilities": description.key_responsibilities or "",
        "qualifications": description.qualifications or "",
        "experience_required": description.experience_required or "",
        "skills_competencies": description.skills_competencies or "",
    }


def _validate(data, existing: JobDescription | None = None):
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
        ("code", "JD code", MAX_CODE),
        ("department", "Department / function", MAX_DEPARTMENT),
        ("grade", "Grade", MAX_GRADE),
        ("reports_to", "Reports to", MAX_REPORTS_TO),
    ):
        value = _text(data.get(field))
        if len(value) > maximum:
            errors[field] = f"Keep {label.lower()} within {maximum} characters"
        cleaned[field] = value or None

    responsibilities = _text(data.get("key_responsibilities"))
    if not responsibilities:
        errors["key_responsibilities"] = "Key responsibilities are required"
    elif len(responsibilities) < MIN_RESPONSIBILITIES:
        errors["key_responsibilities"] = "Add a little more detail"
    elif len(responsibilities) > MAX_BODY:
        errors["key_responsibilities"] = f"Keep this within {MAX_BODY} characters"
    cleaned["key_responsibilities"] = responsibilities

    for field, label in (
        ("job_purpose", "Job purpose"),
        ("qualifications", "Qualifications"),
        ("experience_required", "Experience required"),
        ("skills_competencies", "Skills and competencies"),
    ):
        value = _text(data.get(field))
        if len(value) > MAX_BODY:
            errors[field] = f"Keep {label.lower()} within {MAX_BODY} characters"
        cleaned[field] = value or None

    cleaned["is_active"] = bool(data.get("is_active", True))

    # Two descriptions sharing a code cannot be told apart on an advertisement.
    code = cleaned.get("code")
    if code and not errors.get("code"):
        clash = JobDescription.objects.filter(code__iexact=code)
        if existing is not None:
            clash = clash.exclude(id=existing.id)
        if clash.exists():
            errors["code"] = "Another description already uses this code"

    if title and not errors.get("title"):
        clash = JobDescription.objects.filter(title__iexact=title)
        if existing is not None:
            clash = clash.exclude(id=existing.id)
        if clash.exists():
            errors["title"] = "A description with this title already exists"

    return cleaned, errors


@require_GET
def description_list(request):
    """Descriptions that can be attached to a vacancy.

    Only the active ones, since this feeds the picker on the vacancy screen.
    """
    rows = JobDescription.objects.filter(is_active=True)
    return JsonResponse([_serialize(row) for row in rows], safe=False, status=200)


@require_GET
def manage_list(request):
    """Every description, active or retired, with how many vacancies use it."""
    rows = JobDescription.objects.all().annotate(
        requisition_count=Count("requisitions")
    )
    return JsonResponse(
        [_serialize(row, row.requisition_count) for row in rows], safe=False, status=200
    )


@csrf_exempt
@require_POST
def create_description(request):
    identity, refusal = require_description_manager(request)
    if refusal:
        return JsonResponse({"error": refusal}, status=403)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    cleaned, errors = _validate(data)
    if errors:
        return JsonResponse({"errors": errors}, status=400)

    description = JobDescription.objects.create(**cleaned)
    logger.info(
        "job description %s created by auth user %s: %s",
        description.id, identity.get("user_id"), description.title,
    )
    return JsonResponse(_serialize(description), status=201)


@csrf_exempt
@require_POST
def update_description(request, description_id: int):
    identity, refusal = require_description_manager(request)
    if refusal:
        return JsonResponse({"error": refusal}, status=403)

    description = JobDescription.objects.filter(id=description_id).first()
    if description is None:
        return JsonResponse({"error": "That description no longer exists"}, status=404)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    cleaned, errors = _validate(data, existing=description)
    if errors:
        return JsonResponse({"errors": errors}, status=400)

    for field, value in cleaned.items():
        setattr(description, field, value)
    description.save()

    logger.info(
        "job description %s updated by auth user %s (active=%s)",
        description.id, identity.get("user_id"), description.is_active,
    )

    count = description.requisitions.count()
    return JsonResponse(_serialize(description, count), status=200)


@csrf_exempt
@require_POST
def delete_description(request, description_id: int):
    identity, refusal = require_description_manager(request)
    if refusal:
        return JsonResponse({"error": refusal}, status=403)

    description = JobDescription.objects.filter(id=description_id).first()
    if description is None:
        return JsonResponse({"error": "That description no longer exists"}, status=404)

    try:
        title = description.title
        description.delete()
    except ProtectedError:
        # Deleting it would take the duties away from vacancies that were
        # advertised on it, including any already applied for.
        used_by = description.requisitions.count()
        return JsonResponse(
            {
                "error": (
                    f"This description is attached to {used_by} "
                    f"{'vacancy' if used_by == 1 else 'vacancies'}, so it cannot be "
                    "deleted. Mark it inactive instead - it stays with those "
                    "vacancies but is no longer offered for new ones."
                )
            },
            status=409,
        )

    logger.info(
        "job description %s (%s) deleted by auth user %s",
        description_id, title, identity.get("user_id"),
    )
    return JsonResponse({"success": True, "message": "Job description deleted"}, status=200)
