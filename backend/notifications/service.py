

from users.models import Employees

from .models import Notification


ROUTE_MY_LEAVES = "/leaves/apply"
ROUTE_OFFICIAL_WORK = "/leaves/official-work"


def _erp(erp_id):
    
    try:
        erp = int(erp_id or 0)
    except (TypeError, ValueError):
        return None

    
    return erp if erp > 0 else None


def employee_name(erp_id):
  
    erp = _erp(erp_id)
    if erp is None:
        return None

    try:
        
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
    
    actor = employee_label(actor_erp_id, with_erp=False)
    return f" by {actor}" if actor else ""


def notify_leave_decision(leave, action, actor_erp_id=None):
    
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


def notify_leave_stage_pending(leave, stage):
  
    detail = _describe(leave.leave_type, leave.start_date, leave.end_date)

    return notify(
        recipient_erp_id=stage.assigned_erp_id,
        category="leave",
        event="awaiting_approval",
        title=f"A leave request needs your {stage.label.lower()}",
        message=f"{employee_label(leave.erp_id)} applied for {detail}.",
        link=ROUTE_MY_LEAVES,
        related_id=leave.pk,
        actor_erp_id=leave.erp_id,
    )


def notify_leave_stage_forwarded(leave, stage, comment=None):
    
    detail = _describe(leave.leave_type, leave.start_date, leave.end_date)
    remark_clause = f' Remarks: "{comment}"' if comment else ""

    return notify(
        recipient_erp_id=leave.erp_id,
        category="leave",
        event="stage_forwarded",
        title="Your leave request has moved forward",
        message=f"{detail} passed {stage.label.lower()} and moved to the next stage.{remark_clause}",
        link=ROUTE_MY_LEAVES,
        related_id=leave.pk,
    )