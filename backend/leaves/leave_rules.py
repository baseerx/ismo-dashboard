
from django.db.models import Q
from .models import LeaveModel, LeaveTypeCountModel


MAX_DAYS_PER_REQUEST = {
    "casual leave": 5,
    "rest & recreational leave": 15,
    "bereavement leave": 3,
    "hajj leave": 30,
    "paternity leave": 30,
    "medical leave": 120,
    "sick leave": 120,          
    "iddat leave": 130,
    "disability leave": 365,   
}


def enforce_max_days_per_request(leave_type, requested_days):
    
    cap = MAX_DAYS_PER_REQUEST.get((leave_type or "").strip().lower())
    if cap is not None and requested_days > cap:
        return f"'{leave_type}' cannot exceed {cap} days in a single request (Ch.12)."
    return None


REMOVED_LEAVE_TYPES = {"marriage leave", "annulment leave"}


def check_removed_leave_type(leave_type):
    """None if the type is still offered, else an error string."""
    if (leave_type or "").strip().lower() in REMOVED_LEAVE_TYPES:
        return f"'{leave_type}' is no longer offered."
    return None


MATERNITY_SEQUENCE = [
    "Maternity Leave First",
    "Maternity Leave Second",
    "Maternity Leave Third",
]

ACTIVE_STATUS_EXCLUDE = Q(status__iexact="rejected") | Q(status__iexact="cancelled")


def prior_occurrence_count(erp_id, leave_type):
    return LeaveModel.objects.filter(
        erp_id=erp_id, leave_type__iexact=leave_type
    ).exclude(ACTIVE_STATUS_EXCLUDE).count()


def prior_maternity_count(erp_id):
    return LeaveModel.objects.filter(
        erp_id=erp_id, leave_type__in=MATERNITY_SEQUENCE
    ).exclude(ACTIVE_STATUS_EXCLUDE).count()


def resolve_maternity_leave_type(erp_id):
    
    count = prior_maternity_count(erp_id)
    if count >= 3:
        return None, (
            "Maternity Leave has been used 3 times already. Further "
            "maternity leave is debited to the normal leave account -- "
            "please apply through Earned Leave or Extraordinary Leave."
        )
    return MATERNITY_SEQUENCE[count], None


def check_hajj_occurrence(erp_id):
    if prior_occurrence_count(erp_id, "Hajj Leave") >= 1:
        return "Hajj Leave can only be availed once in an employee's entire service."
    return None


def paternity_alert(erp_id):
 
    count = prior_occurrence_count(erp_id, "Paternity Leave")
    if count >= 3:
        return (
            f"This is application #{count + 1} for Paternity Leave. "
            "Paternity Leave is normally limited to 3 occurrences per "
            "service; beyond the 3rd it is debited to the normal leave account."
        )
    return None

def compute_remaining_balance(erp_id, leave_type, fy_start, fy_end):
    
    leave_limit = LeaveTypeCountModel.objects.filter(leave_type=leave_type).first()
    total_allowed = leave_limit.total_leaves if leave_limit else None
    if total_allowed is None:
        return None

    used_leaves = LeaveModel.objects.filter(
        erp_id=erp_id, leave_type=leave_type,
        status__in=["approved", "pending"],
        start_date__lte=fy_end, end_date__gte=fy_start,
    )
    used_days = 0
    for leave in used_leaves:
        if leave.start_date and leave.end_date:
            actual_start = max(leave.start_date, fy_start)
            actual_end = min(leave.end_date, fy_end)
            used_days += (actual_end - actual_start).days + 1

    if leave_type.lower() == "casual leave":
        has_rr = LeaveModel.objects.filter(
            erp_id=erp_id, leave_type="Rest & Recreational Leave",
            status__in=["approved", "pending"],
            start_date__lte=fy_end, end_date__gte=fy_start,
        ).exists()
        if has_rr:
            used_days += 10

    return total_allowed - used_days


def check_rr_prerequisite(erp_id, fy_start, fy_end):
    cl_remaining = compute_remaining_balance(erp_id, "Casual Leave", fy_start, fy_end)
    if cl_remaining is None or cl_remaining < 10:
        shown = cl_remaining if cl_remaining is not None else "undefined"
        return (
            "Rest & Recreational Leave requires at least 10 Casual Leave "
            f"days available (currently {shown})."
        )
    return None


def split_medical_leave_lwp(erp_id, requested_days, fy_start, fy_end):
    
    already_used = LeaveModel.objects.filter(
        erp_id=erp_id, leave_type__iexact="Medical Leave",
        status__in=["approved", "pending"],
        start_date__lte=fy_end, end_date__gte=fy_start,
    )
    used_days = 0
    for leave in already_used:
        if leave.start_date and leave.end_date:
            actual_start = max(leave.start_date, fy_start)
            actual_end = min(leave.end_date, fy_end)
            used_days += (actual_end - actual_start).days + 1

    remaining_paid = max(0, 120 - used_days)
    paid_days = min(requested_days, remaining_paid)
    lwp_days = requested_days - paid_days
    return paid_days, lwp_days


def resolve_ex_pakistan_shortfall(erp_id, requested_days, fy_start, fy_end):
    """Returns (covered_days, lwp_days)."""
    cl_remaining = compute_remaining_balance(erp_id, "Casual Leave", fy_start, fy_end) or 0
    el_remaining = compute_remaining_balance(erp_id, "Earned Leave", fy_start, fy_end) or 0
    available = max(0, cl_remaining) + max(0, el_remaining)
    covered_days = min(requested_days, available)
    lwp_days = requested_days - covered_days
    return covered_days, lwp_days


def validate_attachment_universal(upload):
    from django.conf import settings
    import os

    if upload is None:
        return None

    extension = os.path.splitext(upload.name or "")[1].lower()
    allowed = [
        ext.lower()
        for ext in getattr(settings, "LEAVE_ATTACHMENT_ALLOWED_EXTENSIONS", [])
    ]
    if allowed and extension not in allowed:
        return "Unsupported file type. Allowed: " + ", ".join(sorted(allowed))

    max_mb = getattr(settings, "LEAVE_ATTACHMENT_MAX_MB", 5)
    if upload.size > max_mb * 1024 * 1024:
        return f"Attachment must be {max_mb} MB or smaller."

    return None