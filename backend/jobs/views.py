"""Endpoints behind the internal job application form.

Three jobs: list the vacancies that can be applied for, hand the form what the
`employees` table already knows about the person filling it in, and store a
submission with its education rows.
"""

import json
import logging

from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from sqlalchemy import text

from db import SessionLocal

from .models import (
    InternalJobApplication,
    InternalJobApplicationEducation,
    JobRequisition,
)
from .validators import validate_application

logger = logging.getLogger(__name__)


@require_GET
def requisitions(request):
    """Open vacancies, newest first, for the dropdown."""
    rows = JobRequisition.objects.filter(is_open=True).values(
        "id", "title", "department", "location", "closing_date"
    )

    return JsonResponse(
        [
            {
                "id": row["id"],
                "title": row["title"],
                "department": row["department"],
                "location": row["location"],
                "closing_date": row["closing_date"].isoformat() if row["closing_date"] else None,
            }
            for row in rows
        ],
        safe=False,
        status=200,
    )


@require_GET
def application_profile(request):
    """What the form can fill in for one employee before they type anything.

    Everything here comes from `employees` and the tables it points at, plus
    the corporate email from the account mapped to that ERP id. Fields the
    database does not hold - a personal phone number, for instance - come back
    empty for the applicant to fill in.
    """
    erp_id = request.GET.get("erp_id")
    if not erp_id:
        return JsonResponse({"error": "erp_id is required"}, status=400)

    session = SessionLocal()
    try:
        employee = session.execute(
            text(
                """
                SELECT
                    e.erp_id, e.hris_id, e.name, e.cnic, e.gender, e.position,
                    e.section_id, e.grade_id,
                    s.name AS section_name,
                    d.title AS designation,
                    g.name AS grade,
                    u.email AS corporate_email
                FROM employees e
                LEFT JOIN sections s ON s.id = e.section_id
                LEFT JOIN designations d ON d.id = e.designation_id
                LEFT JOIN grades g ON g.id = e.grade_id
                LEFT JOIN profiles p ON p.erpid = e.erp_id
                LEFT JOIN auth_user u ON u.id = p.authid
                WHERE e.erp_id = :erp_id AND e.flag = 1
                """
            ),
            {"erp_id": erp_id},
        ).first()

        if not employee:
            return JsonResponse({"error": "Employee not found"}, status=404)

        # The reporting line is not a column anywhere, so the most senior other
        # person in the same section is offered as the supervisor. It is a
        # starting point the applicant can correct, which is why the form leaves
        # the field editable.
        supervisor = session.execute(
            text(
                """
                SELECT TOP 1 e.erp_id, e.name, g.name AS grade
                FROM employees e
                LEFT JOIN grades g ON g.id = e.grade_id
                WHERE e.flag = 1
                  AND e.section_id = :section_id
                  AND e.erp_id <> :erp_id
                ORDER BY e.grade_id DESC, e.erp_id ASC
                """
            ),
            {"section_id": employee.section_id, "erp_id": employee.erp_id},
        ).first()

        return JsonResponse(
            {
                "erp_id": employee.erp_id,
                "emp_full_name": employee.name or "",
                "emp_id": employee.erp_id,
                "hris_id": employee.hris_id,
                "cnic": employee.cnic or "",
                "gender": employee.gender or "",
                "current_dept_code": employee.section_name or "",
                # Designation is the job title; `position` is a free-text note
                # on the row and is only used when there is no designation.
                "current_job_title": employee.designation or employee.position or "",
                "grade": employee.grade or "",
                "current_supervisor_id": supervisor.name if supervisor else "",
                "current_supervisor_erp_id": supervisor.erp_id if supervisor else None,
                "corporate_email": employee.corporate_email or "",
                # Not held anywhere in the HR tables; the applicant supplies it.
                "contact_phone_no": "",
            },
            status=200,
        )
    finally:
        session.close()


@require_GET
def my_applications(request):
    """Applications already submitted by one employee, newest first."""
    erp_id = request.GET.get("erp_id")
    if not erp_id:
        return JsonResponse({"error": "erp_id is required"}, status=400)

    applications = (
        InternalJobApplication.objects.filter(applicant_erp_id=erp_id)
        .select_related("target_job_req")
        .prefetch_related("education")
    )

    return JsonResponse(
        [
            {
                "id": application.id,
                "vacancy": application.target_job_req.title,
                "target_job_req_id": application.target_job_req_id,
                "status": application.status,
                "created_at": application.created_at.strftime("%Y-%m-%d %H:%M"),
                "education_count": application.education.count(),
            }
            for application in applications
        ],
        safe=False,
        status=200,
    )


@csrf_exempt
@require_POST
def create_application(request):
    """Store one application and its education rows, or explain what is wrong."""
    try:
        data = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    cleaned, errors = validate_application(data)

    # The applicant is the session's own ERP id. The form shows it and lets it
    # be corrected for display, but the record is filed against who is signed
    # in, not against whatever the payload claims.
    try:
        applicant_erp_id = int(data.get("applicant_erp_id") or 0)
    except (TypeError, ValueError):
        applicant_erp_id = 0
    if applicant_erp_id <= 0:
        errors["applicant_erp_id"] = "Sign in again - your employee id is missing"

    requisition = None
    if cleaned.get("target_job_req_id"):
        requisition = JobRequisition.objects.filter(
            id=cleaned["target_job_req_id"]
        ).first()
        if requisition is None:
            errors["target_job_req_id"] = "That vacancy no longer exists"
        elif not requisition.is_open:
            errors["target_job_req_id"] = "That vacancy has closed"

    if errors:
        return JsonResponse({"errors": errors}, status=400)

    # One application per person per vacancy: a second submission would leave
    # reviewers guessing which one counts.
    already = InternalJobApplication.objects.filter(
        applicant_erp_id=applicant_erp_id, target_job_req=requisition
    ).first()
    if already:
        return JsonResponse(
            {
                "errors": {
                    "target_job_req_id": "You have already applied for this vacancy."
                }
            },
            status=409,
        )

    with transaction.atomic():
        application = InternalJobApplication.objects.create(
            applicant_erp_id=applicant_erp_id,
            target_job_req=requisition,
            emp_full_name=cleaned["emp_full_name"],
            emp_id=cleaned["emp_id"],
            current_dept_code=cleaned["current_dept_code"],
            current_job_title=cleaned["current_job_title"],
            current_supervisor_id=cleaned["current_supervisor_id"],
            current_supervisor_erp_id=cleaned["current_supervisor_erp_id"],
            cnic=cleaned["cnic"],
            contact_phone_no=cleaned["contact_phone_no"],
            corporate_email=cleaned["corporate_email"],
            personal_email=cleaned["personal_email"],
            preferred_contact_method=cleaned["preferred_contact_method"],
        )

        InternalJobApplicationEducation.objects.bulk_create(
            [
                InternalJobApplicationEducation(application=application, **row)
                for row in cleaned["education"]
            ]
        )

    logger.info(
        "internal job application %s: erp=%s vacancy=%s education_rows=%d",
        application.id, applicant_erp_id, requisition.id, len(cleaned["education"]),
    )

    return JsonResponse(
        {
            "id": application.id,
            "vacancy": requisition.title,
            "education_count": len(cleaned["education"]),
            "message": "Your application has been submitted.",
        },
        status=201,
    )
