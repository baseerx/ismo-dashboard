"""Endpoints behind the internal recruitment online application form.

Three jobs: list the vacancies that can be applied for, hand the form what the
employee record already knows about the person filling it in, and store a
submission - one application per vacancy chosen - with its four repeating
sections.

Who the applicant is comes from the signed-in session (the bearer token), never
from the request: an employee can only see their own profile and applications,
and can only apply as themselves.

The form is prefilled from the employee record, and every prefilled field can
be corrected by the applicant - the record is not always right. What they
submit is filed; anything that differs from the record is kept alongside it
(`record_mismatches`) so HR can see what was changed.
"""

import json
import logging
from datetime import date

from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from notifications.service import employee_label, notify

from .applicant import employee_record
from .form_text import (
    ACK_DATA_ACCURACY,
    ACK_MANAGER_NOTIFIED,
    CONTACT_METHODS,
    DECLARATION_PARAGRAPHS,
    HOW_TO_APPLY,
    SOFT_SKILLS,
    SUBMISSION_NOTE,
)
from .jd_views import body_for_form
from .models import (
    InternalJobApplication,
    InternalJobApplicationCertification,
    InternalJobApplicationEducation,
    InternalJobApplicationExperience,
    InternalJobApplicationTraining,
    JobRequisition,
)
from .permissions import identity_from_request
from .requisition_views import advertisement_url
from .validators import (
    MAX_ACHIEVEMENTS,
    MAX_RESPONSIBILITIES,
    MAX_SOP,
    MAX_TECHNICAL_SKILLS,
    MIN_SOP,
    validate_application,
)

logger = logging.getLogger(__name__)

# Fields the form prefills from the employee record. All of them can be
# corrected; a submitted value that differs from the record is noted for HR.
RECORD_FIELDS = (
    "emp_id",
    "full_name",
    "department_function",
    "current_designation",
    "current_grade",
    "current_supervisor_name",
    "cnic",
    "gender",
    "official_email",
    "current_office_location",
)


def _same(record_value, submitted_value) -> bool:
    """Equal once case and spacing are ignored - "G-07" and "g-07 " match."""
    normal = lambda value: " ".join(str(value if value is not None else "").split()).casefold()
    return normal(record_value) == normal(submitted_value)


def _changes_from_record(record: dict, cleaned: dict) -> dict:
    """{field: {"record": .., "submitted": ..}} for every corrected field."""
    changes = {}
    for field in RECORD_FIELDS:
        on_record = record.get(field)
        if on_record in (None, ""):
            continue
        submitted = cleaned.get(field)
        if not _same(on_record, submitted):
            changes[field] = {
                "record": str(on_record),
                "submitted": "" if submitted is None else str(submitted),
            }
    return changes


def _session_erp_id(request):
    """(erp_id, refusal) for the signed-in user. Exactly one is set."""
    identity, refusal = identity_from_request(request)
    if refusal:
        return None, refusal
    try:
        erp_id = int(identity.get("erpid") or 0)
    except (TypeError, ValueError):
        erp_id = 0
    if erp_id <= 0:
        return None, "Your account is not linked to an employee record. Contact HR."
    return erp_id, None


def _requisition_payload(requisition: JobRequisition) -> dict:
    """A vacancy as section 1 of the form needs it, with its description.

    The description travels with the vacancy so choosing a position in the
    dropdown can show its duties straight away.
    """
    return {
        "id": requisition.id,
        "title": requisition.title,
        "reference_no": requisition.reference_no or "",
        "grade": requisition.grade or "",
        "department": requisition.department or "",
        "location": requisition.location or "",
        "advertisement_date": requisition.advertisement_date.isoformat()
        if requisition.advertisement_date else None,
        "closing_date": requisition.closing_date.isoformat()
        if requisition.closing_date else None,
        # A note about this advertisement, as opposed to the description of the
        # post itself.
        "notes": requisition.description or "",
        "job_description": body_for_form(requisition.job_description),
        # The advertisement PDF, when HR attached one.
        "advertisement_url": advertisement_url(requisition),
        "advertisement_name": requisition.advertisement_pdf_name
        if requisition.advertisement_pdf else "",
    }


@require_GET
def application_instructions(request):
    """The "how to apply" guidance the form shows in a popup.

    Open to anyone, like the vacancy list, so the guidance can be read even by
    someone whose employee record could not be loaded.
    """
    return JsonResponse(
        {
            "sections": [
                {"heading": heading, "points": list(points)}
                for heading, points in HOW_TO_APPLY
            ],
            "submission_note": SUBMISSION_NOTE,
        },
        status=200,
    )


@require_GET
def requisitions(request):
    """Vacancies that can still be applied for, newest first.

    Open, and either without a closing date or not yet past it - a post whose
    closing date has gone by should not appear on the form even if nobody has
    got round to closing it.
    """
    rows = (
        JobRequisition.objects.select_related("job_description")
        .filter(is_open=True)
        .filter(Q(closing_date__isnull=True) | Q(closing_date__gte=date.today()))
    )

    return JsonResponse([_requisition_payload(row) for row in rows], safe=False, status=200)


@require_GET
def application_profile(request):
    """What the form can fill in for the signed-in employee before they type.

    Everything here comes from the employee record and the tables it points at,
    plus the email on the account mapped to that ERP id. Fields the database
    does not hold - a date of birth, a mobile number - come back empty for the
    applicant to fill in. Everything is editable; `record_fields` lists the
    ones the record supplied, so the form can mark them as prefilled.
    """
    erp_id, refusal = _session_erp_id(request)
    if refusal:
        return JsonResponse({"error": refusal}, status=401)

    record = employee_record(erp_id)
    if not record:
        return JsonResponse({"error": "Employee not found"}, status=404)

    return JsonResponse(
        {
            **record,
            "record_fields": [field for field in RECORD_FIELDS if record.get(field)],
            # Held nowhere in the HR tables; the applicant supplies them.
            "father_or_husband_name": "",
            "date_of_birth": "",
            "mobile_no": "",
            "emergency_contact_no": "",
            "date_of_joining_ismo": "",
            "date_of_appointment_to_current_grade": "",
            "date_of_joining_current_position": "",
            # Fixed wording and lists, served so the page and the server can
            # never disagree about them.
            "declaration_paragraphs": list(DECLARATION_PARAGRAPHS),
            "submission_note": SUBMISSION_NOTE,
            "soft_skill_options": list(SOFT_SKILLS),
            "contact_methods": list(CONTACT_METHODS),
            "ack_manager_notified_text": ACK_MANAGER_NOTIFIED,
            "ack_data_accuracy_text": ACK_DATA_ACCURACY,
            "limits": {
                "responsibilities": MAX_RESPONSIBILITIES,
                "achievements": MAX_ACHIEVEMENTS,
                "sop_min": MIN_SOP,
                "sop_max": MAX_SOP,
                "technical_skills": MAX_TECHNICAL_SKILLS,
            },
        },
        status=200,
    )


@require_GET
def my_applications(request):
    """Applications already submitted by the signed-in employee, newest first."""
    erp_id, refusal = _session_erp_id(request)
    if refusal:
        return JsonResponse({"error": refusal}, status=401)

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

    if not isinstance(data, dict):
        return JsonResponse({"errors": {"__all__": "The submission was not readable"}},
                            status=400)

    # The applicant is whoever is signed in, not whatever the payload claims.
    applicant_erp_id, refusal = _session_erp_id(request)
    if refusal:
        return JsonResponse({"error": refusal}, status=401)

    record = employee_record(applicant_erp_id)
    if not record:
        return JsonResponse(
            {"error": "No active employee record was found for your account."}, status=404
        )

    cleaned, errors = validate_application(data)

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

    # What the applicant corrected from the record, for HR to see. The
    # supervisor stays identified only while the name is the one on record.
    record_changes = _changes_from_record(record, cleaned)
    supervisor_erp_id = (
        None if "current_supervisor_name" in record_changes
        else record["current_supervisor_erp_id"]
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
                personal_email=cleaned["personal_email"],
                preferred_contact_method=cleaned["preferred_contact_method"],
                # 3. current employment details
                date_of_joining_ismo=cleaned["date_of_joining_ismo"],
                current_designation=cleaned["current_designation"],
                current_grade=cleaned["current_grade"],
                department_function=cleaned["department_function"],
                date_of_appointment_to_current_grade=cleaned["date_of_appointment_to_current_grade"],
                total_service_ismo=cleaned["total_service_ismo"],
                total_relevant_experience=cleaned["total_relevant_experience"],
                date_of_joining_current_position=cleaned["date_of_joining_current_position"],
                current_supervisor_erp_id=supervisor_erp_id,
                current_supervisor_name=cleaned["current_supervisor_name"],
                record_mismatches=json.dumps(record_changes),
                # skills, statement of purpose, acknowledgements
                skills_technical_tags=json.dumps(cleaned["skills_technical_tags"]),
                skills_soft_checkboxes=json.dumps(cleaned["skills_soft_checkboxes"]),
                application_rationale_sop=cleaned["application_rationale_sop"],
                ack_manager_notified_bool=cleaned["ack_manager_notified_bool"],
                ack_data_accuracy_bool=cleaned["ack_data_accuracy_bool"],
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

    supervisor_notified = _notify_supervisor(supervisor_erp_id, applicant_erp_id, created)

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
            "supervisor_notified": supervisor_notified,
            "changed_from_record": sorted(record_changes),
            "message": message,
        },
        status=201,
    )


def _notify_supervisor(supervisor, applicant_erp_id, created) -> bool:
    """Alert the applicant's current supervisor that they have applied.

    The applicant has just certified that their manager knows; this makes sure
    of it. Only the supervisor on record can be alerted - when the applicant
    corrected the name, there is nobody this app can identify. Runs after the
    applications are committed and never fails the request - `notify`
    swallows its own errors.
    """
    if not supervisor or supervisor == applicant_erp_id:
        return False

    positions = ", ".join(item["vacancy"] for item in created)
    references = ", ".join(item["reference_no"] for item in created)
    notification = notify(
        recipient_erp_id=supervisor,
        category="job_application",
        event="submitted",
        title="A team member applied for an internal vacancy",
        message=(
            f"{employee_label(applicant_erp_id)} has applied for {positions} "
            f"({references}) and has confirmed that you are aware of the application."
        ),
        related_id=created[0]["id"],
        actor_erp_id=applicant_erp_id,
    )
    return notification is not None
