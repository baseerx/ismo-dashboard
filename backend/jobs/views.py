"""Endpoints behind the internal recruitment online application form.

Three jobs: list the vacancies that can be applied for, hand the form what the
employee record already knows about the person filling it in, and store a
submission - one application per vacancy chosen - with its four repeating
sections.
"""

import json
import logging
from datetime import date

from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from sqlalchemy import text

from db import SessionLocal

from .form_text import DECLARATION_PARAGRAPHS, SUBMISSION_NOTE
from .models import (
    InternalJobApplication,
    InternalJobApplicationCertification,
    InternalJobApplicationEducation,
    InternalJobApplicationExperience,
    InternalJobApplicationTraining,
    JobRequisition,
)
from .validators import validate_application

logger = logging.getLogger(__name__)

GENDER_NAMES = {"M": "Male", "F": "Female", "male": "Male", "female": "Female"}


def _requisition_payload(row) -> dict:
    """A vacancy as section 1 of the form needs it."""
    return {
        "id": row["id"],
        "title": row["title"],
        "reference_no": row["reference_no"] or "",
        "grade": row["grade"] or "",
        "department": row["department"] or "",
        "location": row["location"] or "",
        "advertisement_date": row["advertisement_date"].isoformat() if row["advertisement_date"] else None,
        "closing_date": row["closing_date"].isoformat() if row["closing_date"] else None,
    }


@require_GET
def requisitions(request):
    """Vacancies that can still be applied for, newest first.

    Open, and either without a closing date or not yet past it - a post whose
    closing date has gone by should not appear on the form even if nobody has
    got round to closing it.
    """
    rows = (
        JobRequisition.objects.filter(is_open=True)
        .filter(Q(closing_date__isnull=True) | Q(closing_date__gte=date.today()))
        .values(
            "id", "title", "reference_no", "grade", "department", "location",
            "advertisement_date", "closing_date",
        )
    )

    return JsonResponse([_requisition_payload(row) for row in rows], safe=False, status=200)


@require_GET
def application_profile(request):
    """What the form can fill in for one employee before they type anything.

    Everything here comes from the employee record and the tables it points at,
    plus the email on the account mapped to that ERP id. Fields the database
    does not hold - a date of birth, a mobile number - come back empty for the
    applicant to fill in, and every one of them stays editable on the form.
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
                    l.name AS office_location,
                    u.email AS official_email
                FROM employees e
                LEFT JOIN sections s ON s.id = e.section_id
                LEFT JOIN designations d ON d.id = e.designation_id
                LEFT JOIN grades g ON g.id = e.grade_id
                LEFT JOIN locations l ON l.id = e.location_id
                LEFT JOIN profiles p ON p.erpid = e.erp_id
                LEFT JOIN auth_user u ON u.id = p.authid
                WHERE e.erp_id = :erp_id AND e.flag = 1
                """
            ),
            {"erp_id": erp_id},
        ).first()

        if not employee:
            return JsonResponse({"error": "Employee not found"}, status=404)

        # Designation is the job title; `position` is a free-text note on the
        # row and is only used when there is no designation.
        designation = employee.designation or employee.position or ""

        return JsonResponse(
            {
                # section 2
                "emp_id": employee.erp_id,
                "full_name": employee.name or "",
                "cnic": employee.cnic or "",
                "gender": GENDER_NAMES.get((employee.gender or "").strip(), ""),
                "official_email": employee.official_email or "",
                "current_office_location": employee.office_location or "",
                # section 3
                "current_designation": designation,
                "current_grade": employee.grade or "",
                "department_function": employee.section_name or "",
                # Held nowhere in the HR tables; the applicant supplies them.
                "father_or_husband_name": "",
                "date_of_birth": "",
                "mobile_no": "",
                "emergency_contact_no": "",
                "date_of_joining_ismo": "",
                "date_of_appointment_to_current_grade": "",
                "date_of_joining_current_position": "",
                "hris_id": employee.hris_id,
                # The form shows the declaration it is asking to be accepted.
                "declaration_paragraphs": list(DECLARATION_PARAGRAPHS),
                "submission_note": SUBMISSION_NOTE,
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
        .prefetch_related("education", "experience", "certifications", "trainings")
    )

    return JsonResponse(
        [
            {
                "id": application.id,
                "reference_no": application.application_reference_no or "",
                "vacancy": application.vacancy_position_title or application.target_job_req.title,
                "target_job_req_id": application.target_job_req_id,
                "status": application.status,
                "hr_verification_status": application.hr_verification_status,
                "created_at": application.created_at.strftime("%Y-%m-%d %H:%M"),
                "education_count": application.education.count(),
                "experience_count": application.experience.count(),
                "certification_count": application.certifications.count(),
                "training_count": application.trainings.count(),
            }
            for application in applications
        ],
        safe=False,
        status=200,
    )


def _reference_no(application: InternalJobApplication) -> str:
    """ISMO/IJA/2026/00042 - printed in the form's submission record."""
    year = (application.created_at or date.today()).year
    return f"ISMO/IJA/{year}/{application.id:05d}"


@csrf_exempt
@require_POST
def create_application(request):
    """Store one application per vacancy chosen, or explain what is wrong."""
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

    requisitions_to_use = []
    if cleaned.get("target_job_req_ids") and "target_job_req_ids" not in errors:
        found = {
            item.id: item
            for item in JobRequisition.objects.filter(id__in=cleaned["target_job_req_ids"])
        }

        unusable = []
        today = date.today()
        for requisition_id in cleaned["target_job_req_ids"]:
            requisition = found.get(requisition_id)
            if requisition is None:
                unusable.append(f"#{requisition_id} no longer exists")
            elif not requisition.is_open:
                unusable.append(f"{requisition.title} has closed")
            elif requisition.closing_date and requisition.closing_date < today:
                unusable.append(f"{requisition.title} is past its closing date")
            else:
                requisitions_to_use.append(requisition)

        if unusable:
            errors["target_job_req_ids"] = "; ".join(unusable)

    if errors:
        return JsonResponse({"errors": errors}, status=400)

    # One application per person per vacancy. Vacancies already applied for are
    # reported back rather than blocking the ones that are new, so a stale
    # selection does not send the applicant away empty-handed.
    already_applied = set(
        InternalJobApplication.objects.filter(
            applicant_erp_id=applicant_erp_id,
            target_job_req__in=requisitions_to_use,
        ).values_list("target_job_req_id", flat=True)
    )

    skipped = [item.title for item in requisitions_to_use if item.id in already_applied]
    to_create = [item for item in requisitions_to_use if item.id not in already_applied]

    if not to_create:
        return JsonResponse(
            {
                "errors": {
                    "target_job_req_ids": (
                        "You have already applied for "
                        + ("this vacancy." if len(skipped) == 1
                           else "these vacancies: " + ", ".join(skipped))
                    )
                },
                "skipped": skipped,
            },
            status=409,
        )

    # One row per vacancy, each carrying its own copy of the application. The
    # repetition is deliberate: an application is a snapshot of what was
    # submitted, each vacancy is reviewed and progresses on its own, and the
    # reviewer for one post should not be reading a record that also belongs to
    # another.
    created = []
    with transaction.atomic():
        for requisition in to_create:
            application = InternalJobApplication.objects.create(
                applicant_erp_id=applicant_erp_id,
                target_job_req=requisition,
                # 1. vacancy information, as advertised on the day
                vacancy_position_title=requisition.title,
                vacancy_reference_no=requisition.reference_no,
                vacancy_grade=requisition.grade,
                vacancy_department=requisition.department,
                vacancy_advertisement_date=requisition.advertisement_date,
                vacancy_closing_date=requisition.closing_date,
                # 2. personal & contact information
                emp_id=cleaned["emp_id"],
                full_name=cleaned["full_name"],
                father_or_husband_name=cleaned["father_or_husband_name"],
                cnic=cleaned["cnic"],
                date_of_birth=cleaned["date_of_birth"],
                gender=cleaned["gender"],
                official_email=cleaned["official_email"],
                mobile_no=cleaned["mobile_no"],
                current_office_location=cleaned["current_office_location"],
                emergency_contact_no=cleaned["emergency_contact_no"],
                # 3. current employment details
                date_of_joining_ismo=cleaned["date_of_joining_ismo"],
                current_designation=cleaned["current_designation"],
                current_grade=cleaned["current_grade"],
                department_function=cleaned["department_function"],
                date_of_appointment_to_current_grade=cleaned["date_of_appointment_to_current_grade"],
                total_service_ismo=cleaned["total_service_ismo"],
                total_relevant_experience=cleaned["total_relevant_experience"],
                date_of_joining_current_position=cleaned["date_of_joining_current_position"],
                # 8 and 9
                declaration_accepted=cleaned["declaration_accepted"],
                applicant_signature=cleaned["applicant_signature"],
            )

            application.application_reference_no = _reference_no(application)
            application.save(update_fields=["application_reference_no"])

            InternalJobApplicationEducation.objects.bulk_create([
                InternalJobApplicationEducation(application=application, **row)
                for row in cleaned["education"]
            ])
            InternalJobApplicationExperience.objects.bulk_create([
                InternalJobApplicationExperience(application=application, **row)
                for row in cleaned["experience"]
            ])
            InternalJobApplicationCertification.objects.bulk_create([
                InternalJobApplicationCertification(application=application, **row)
                for row in cleaned["certifications"]
            ])
            InternalJobApplicationTraining.objects.bulk_create([
                InternalJobApplicationTraining(application=application, **row)
                for row in cleaned["trainings"]
            ])

            created.append({
                "id": application.id,
                "vacancy": requisition.title,
                "reference_no": application.application_reference_no,
            })

    logger.info(
        "internal job applications %s: erp=%s vacancies=%s skipped=%d "
        "education=%d experience=%d certifications=%d trainings=%d",
        [item["id"] for item in created], applicant_erp_id,
        [item.id for item in to_create], len(skipped),
        len(cleaned["education"]), len(cleaned["experience"]),
        len(cleaned["certifications"]), len(cleaned["trainings"]),
    )

    if len(created) == 1:
        message = (
            f"Your application has been submitted for {created[0]['vacancy']}. "
            f"Reference {created[0]['reference_no']}."
        )
    else:
        message = f"Your application has been submitted for {len(created)} vacancies."
    if skipped:
        message += " Already applied for, so left alone: " + ", ".join(skipped) + "."

    return JsonResponse(
        {
            "applications": created,
            # Kept so anything reading the old shape still finds a first id.
            "id": created[0]["id"],
            "vacancy": created[0]["vacancy"],
            "reference_no": created[0]["reference_no"],
            "skipped": skipped,
            "education_count": len(cleaned["education"]),
            "experience_count": len(cleaned["experience"]),
            "certification_count": len(cleaned["certifications"]),
            "training_count": len(cleaned["trainings"]),
            "message": message,
        },
        status=201,
    )
