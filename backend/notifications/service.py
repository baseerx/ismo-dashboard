"""Helpers other modules call to raise a notification.

Kept separate from views so leaves / officialwork can import it without
pulling in request handling, and so the routes a notification points at are
defined in exactly one place.
"""

from users.models import Employees

from .models import Notification


# Frontend routes. These must match the paths registered in App.tsx —
# a notification whose link does not resolve just lands on a blank page.
ROUTE_MY_LEAVES = "/leaves/apply"
ROUTE_OFFICIAL_WORK = "/leaves/official-work"


def _erp(erp_id):
    """An ERP id as a positive int, or None if it is unset or not a number."""
    try:
        erp = int(erp_id or 0)
    except (TypeError, ValueError):
        return None

    # 0 is the "unset" value used across these tables for head_erpid.
    return erp if erp > 0 else None


def employee_name(erp_id):
    """Name held against an ERP id, or None when it cannot be resolved.

    Never raises: a notification is written as a side effect of the real
    action, so a missing or duplicated employees row must degrade the text,
    not the request.
    """
    erp = _erp(erp_id)
    if erp is None:
        return None

    try:
        # An ERP id can appear more than once in `employees` when someone has
        # been re-entered; the current row is the one carrying flag=1, so
        # order by flag descending and take that one.
        name = (
            Employees.objects.filter(erp_id=erp)
            .order_by('-flag')
            .values_list('name', flat=True)
            .first()
        )
    except Exception:
        return None

    return (name or "").strip() or None


def employee_label(erp_id, with_erp=True):
    """How a person is named inside notification text.

    "Ali Khan (ERP 1234)" by default — the head still needs the ERP id to
    find the row in the leave table — and the bare "Ali Khan" with
    `with_erp=False`, for the trailing "approved by ..." where the id adds
    nothing. Degrades to "ERP 1234" when the name cannot be resolved, and to
    "" when there is no usable id at all.
    """
    erp = _erp(erp_id)
    if erp is None:
        return ""

    name = employee_name(erp)
    if not name:
        return f"ERP {erp}"

    return f"{name} (ERP {erp})" if with_erp else name


def notify(
    recipient_erp_id,
    category,
    event,
    title,
    message="",
    link=None,
    related_id=None,
    actor_erp_id=None,
):
    """Create a notification, or return None if it cannot be created.

    Deliberately swallows every error: a notification is a side effect of the
    real action (approving a leave, applying for one), and failing to record
    it must never roll back or 500 the action itself.
    """
    recipient = _erp(recipient_erp_id)
    if recipient is None:
        return None

    try:
        return Notification.objects.create(
            recipient_erp_id=recipient,
            category=category,
            event=event,
            title=title[:150],
            message=message or "",
            link=link,
            related_id=related_id,
            actor_erp_id=actor_erp_id,
        )
    except Exception:
        return None


def _describe(leave_type, start_date, end_date):
    span = ""
    if start_date and end_date:
        if start_date == end_date:
            span = f" on {start_date:%d-%m-%Y}"
        else:
            span = f" from {start_date:%d-%m-%Y} to {end_date:%d-%m-%Y}"
    return f"{leave_type or 'Leave'}{span}"


def _by_actor(actor_erp_id):
    """" by Ali Khan" for the approver, or "" when no actor was recorded.

    Older records were written without one, so the sentence has to read
    correctly with the clause absent.
    """
    actor = employee_label(actor_erp_id, with_erp=False)
    return f" by {actor}" if actor else ""


def notify_leave_decision(leave, action, actor_erp_id=None):
    """Tell the applicant their leave was approved or rejected."""
    decided = "approved" if action == "approve" else "rejected"
    detail = _describe(leave.leave_type, leave.start_date, leave.end_date)

    return notify(
        recipient_erp_id=leave.erp_id,
        category="leave",
        event=decided,
        title=f"Your leave was {decided}",
        message=f"{detail} has been {decided}{_by_actor(actor_erp_id)}.",
        link=ROUTE_MY_LEAVES,
        related_id=leave.pk,
        actor_erp_id=actor_erp_id,
    )


def notify_leave_submitted(leave):
    """Tell the section head that a request is waiting on them."""
    detail = _describe(leave.leave_type, leave.start_date, leave.end_date)

    return notify(
        recipient_erp_id=leave.head_erpid,
        category="leave",
        event="awaiting_approval",
        title="A leave request needs your approval",
        message=f"{employee_label(leave.erp_id)} applied for {detail}.",
        link=ROUTE_MY_LEAVES,
        related_id=leave.pk,
        actor_erp_id=leave.erp_id,
    )


def notify_official_work_decision(record, action, actor_erp_id=None):
    decided = "approved" if action == "approve" else "rejected"
    detail = _describe(record.leave_type, record.start_date, record.end_date)

    return notify(
        recipient_erp_id=record.erp_id,
        category="official_work",
        event=decided,
        title=f"Your official work was {decided}",
        message=f"{detail} has been {decided}{_by_actor(actor_erp_id)}.",
        link=ROUTE_OFFICIAL_WORK,
        related_id=record.pk,
        actor_erp_id=actor_erp_id,
    )


def notify_official_work_submitted(record):
    detail = _describe(record.leave_type, record.start_date, record.end_date)

    return notify(
        recipient_erp_id=record.head_erpid,
        category="official_work",
        event="awaiting_approval",
        title="An official work request needs your approval",
        message=f"{employee_label(record.erp_id)} applied for {detail}.",
        link=ROUTE_OFFICIAL_WORK,
        related_id=record.pk,
        actor_erp_id=record.erp_id,
    )
