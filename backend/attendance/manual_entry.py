"""Update Attendance: insert or correct one employee's check-in and check-out
for one date (Biometric Attendance > Update Attendance).

Only administrators - superusers, or anyone Assign Rights grants the page to.
For the chosen day it works on exactly two punches: the first check-in and the
last check-out, which is what every report reads. An existing punch is moved to
the new time; a missing one is inserted the way the device writes it. Other
punches of the day are left as recorded. Every change is written to
attendance_manual_edits with who made it, when, the old and new times, and the
reason given.
"""

import json
import logging
from datetime import date, datetime, time

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Max
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from jobs.permissions import _has_menu_right, identity_from_request
from users.models import Employees

from .models import Attendance, AttendanceManualEdit

logger = logging.getLogger(__name__)

PAGE_URI = "/attendance/manual-entry"

CHECK_IN = "Checked In"
CHECK_OUTS = ("Checked Out", "Early Checked Out")

# The device's own rules for its marks.
LATE_AFTER = time(8, 30)
EARLY_BEFORE = time(16, 0)

MIN_REASON = 5
MAX_REASON = 300


def _require_admin(request):
    """(identity, refusal). Exactly one is set."""
    identity, refusal = identity_from_request(request)
    if refusal:
        return None, refusal
    if identity.get("is_superuser") or _has_menu_right(identity.get("user_id"), PAGE_URI):
        return identity, None
    return None, "You do not have rights to update attendance."


def _parse_date(value):
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _parse_time(value):
    """A time from "HH:MM" or "HH:MM:SS"; None for blank; False when unreadable."""
    text = str(value or "").strip()
    if not text:
        return None
    for pattern in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(text, pattern).time()
        except ValueError:
            continue
    return False


def _hhmm(moment) -> str:
    return moment.strftime("%H:%M") if moment else ""


def _employee(erp_id):
    return (
        Employees.objects.filter(erp_id=erp_id)
        .order_by("-flag")
        .values("erp_id", "hris_id", "name", "section_id", "flag")
        .first()
    )


def _day_punches(hris_id, work_date):
    return list(
        Attendance.objects.filter(user_id=hris_id, timestamp__date=work_date).order_by("timestamp")
    )


def _first_check_in(punches):
    return next((p for p in punches if p.status == CHECK_IN), None)


def _last_check_out(punches):
    return next((p for p in reversed(punches) if p.status in CHECK_OUTS), None)


def _day_payload(employee, work_date):
    punches = _day_punches(employee["hris_id"], work_date)
    check_in, check_out = _first_check_in(punches), _last_check_out(punches)
    return {
        "erp_id": employee["erp_id"],
        "name": employee["name"],
        "date": work_date.isoformat(),
        "check_in": _hhmm(check_in.timestamp) if check_in else "",
        "check_out": _hhmm(check_out.timestamp) if check_out else "",
        "punches": [
            {"time": p.timestamp.strftime("%H:%M:%S"), "status": p.status} for p in punches
        ],
        "history": [
            {
                "changed_at": edit.changed_at.strftime("%Y-%m-%d %H:%M"),
                "changed_by": edit.changed_by_name,
                "check_in": [edit.old_check_in, edit.new_check_in],
                "check_out": [edit.old_check_out, edit.new_check_out],
                "reason": edit.reason,
            }
            for edit in AttendanceManualEdit.objects.filter(
                erp_id=employee["erp_id"], work_date=work_date
            )[:20]
        ],
    }


@require_GET
def manual_entry_day(request):
    """The chosen employee's punches for the chosen date, and earlier edits."""
    identity, refusal = _require_admin(request)
    if refusal:
        return JsonResponse({"error": refusal}, status=403)

    work_date = _parse_date(request.GET.get("date"))
    if work_date is None:
        return JsonResponse({"error": "Give the date like 2026-10-15"}, status=400)
    employee = _employee(request.GET.get("erp_id"))
    if employee is None:
        return JsonResponse({"error": "Employee not found"}, status=404)

    return JsonResponse(_day_payload(employee, work_date), status=200)


def _next_uid():
    # Highest existing id + 1, worked out by the database rather than by
    # loading every punch, as the device's own ids are below this range.
    return (Attendance.objects.aggregate(top=Max("uid"))["top"] or 0) + 1


@csrf_exempt
@require_POST
def manual_entry_save(request):
    """Set the first check-in and / or the last check-out for one day."""
    identity, refusal = _require_admin(request)
    if refusal:
        return JsonResponse({"error": refusal}, status=403)

    try:
        data = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid request"}, status=400)
    if not isinstance(data, dict):
        return JsonResponse({"error": "Invalid request"}, status=400)

    errors = {}
    work_date = _parse_date(data.get("date"))
    if work_date is None:
        errors["date"] = "Choose the date"
    elif work_date > date.today():
        errors["date"] = "Attendance cannot be entered for a future date"

    new_in, new_out = _parse_time(data.get("check_in")), _parse_time(data.get("check_out"))
    if new_in is False:
        errors["check_in"] = "Enter the check-in time like 08:30"
    if new_out is False:
        errors["check_out"] = "Enter the check-out time like 16:30"
    if new_in is None and new_out is None and "check_in" not in errors and "check_out" not in errors:
        errors["check_in"] = "Enter a check-in time, a check-out time, or both"

    reason = str(data.get("reason") or "").strip()
    if len(reason) < MIN_REASON:
        errors["reason"] = "Say why the attendance is being changed"
    elif len(reason) > MAX_REASON:
        errors["reason"] = f"Keep the reason within {MAX_REASON} characters"

    employee = _employee(data.get("erp_id"))
    if employee is None:
        errors["erp_id"] = "Choose the employee"

    if errors:
        return JsonResponse({"errors": errors}, status=400)

    actor = User.objects.filter(pk=identity.get("user_id")).first()
    actor_name = (actor.get_full_name() or actor.username) if actor else ""

    with transaction.atomic():
        punches = _day_punches(employee["hris_id"], work_date)
        check_in, check_out = _first_check_in(punches), _last_check_out(punches)

        # The day's result must still read in order: check-in before check-out.
        effective_in = new_in or (check_in.timestamp.time() if check_in else None)
        effective_out = new_out or (check_out.timestamp.time() if check_out else None)
        if effective_in and effective_out and effective_out <= effective_in:
            field = "check_out" if new_out else "check_in"
            return JsonResponse(
                {"errors": {field: "The check-out must be later than the check-in"}}, status=400
            )

        # Reports read the first check-in and the last check-out. A time that
        # another punch would overrule is refused rather than silently ignored.
        if new_in is not None:
            earlier = next((p for p in punches if p.status == CHECK_IN and p is not check_in
                            and p.timestamp.time() < new_in), None)
            if earlier:
                return JsonResponse({"errors": {"check_in": (
                    f"Another check-in at {earlier.timestamp:%H:%M} is earlier, so it would still "
                    "count as the day's check-in"
                )}}, status=400)
        if new_out is not None:
            later = next((p for p in punches if p.status in CHECK_OUTS and p is not check_out
                          and p.timestamp.time() > new_out), None)
            if later:
                return JsonResponse({"errors": {"check_out": (
                    f"Another check-out at {later.timestamp:%H:%M} is later, so it would still "
                    "count as the day's check-out"
                )}}, status=400)

        old_in, old_out = _hhmm(check_in.timestamp) if check_in else "", \
            _hhmm(check_out.timestamp) if check_out else ""

        if new_in is not None:
            moment = datetime.combine(work_date, new_in)
            mark = "late" if new_in > LATE_AFTER else "on time"
            if check_in:
                check_in.timestamp, check_in.lateintime = moment, mark
                check_in.save(update_fields=["timestamp", "lateintime"])
            else:
                Attendance.objects.create(
                    uid=_next_uid(), user_id=employee["hris_id"], timestamp=moment,
                    status=CHECK_IN, punch=0, lateintime=mark,
                )

        if new_out is not None:
            moment = datetime.combine(work_date, new_out)
            status = "Early Checked Out" if new_out < EARLY_BEFORE else "Checked Out"
            if check_out:
                check_out.timestamp, check_out.status = moment, status
                check_out.save(update_fields=["timestamp", "status"])
            else:
                Attendance.objects.create(
                    uid=_next_uid(), user_id=employee["hris_id"], timestamp=moment,
                    status=status, punch=1, lateintime="on time",
                )

        AttendanceManualEdit.objects.create(
            erp_id=employee["erp_id"], hris_id=employee["hris_id"], work_date=work_date,
            old_check_in=old_in, new_check_in=_hhmm(new_in) if new_in else "",
            old_check_out=old_out, new_check_out=_hhmm(new_out) if new_out else "",
            reason=reason, changed_by=identity.get("user_id"), changed_by_name=actor_name,
        )

    logger.info(
        "manual attendance for ERP %s on %s by auth user %s: in %s->%s, out %s->%s",
        employee["erp_id"], work_date, identity.get("user_id"),
        old_in or "-", _hhmm(new_in) if new_in else "(kept)",
        old_out or "-", _hhmm(new_out) if new_out else "(kept)",
    )
    return JsonResponse(
        {"message": "Attendance saved", "day": _day_payload(employee, work_date)}, status=200
    )
