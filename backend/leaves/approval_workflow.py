from django.utils import timezone
from .models import LeaveModel, LeaveApprovalStage
from .approval_hierarchy import build_full_approval_chain
from notifications.service import (
    notify_leave_stage_pending,
    notify_leave_stage_forwarded,
    notify_leave_decision,
)


def initialize_approval_chain(leave):

    try:
        chain = build_full_approval_chain(leave)
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            "Approval chain build failed for leave %s; using legacy routing",
            leave.pk,
        )
        chain = []

    if not chain or any(erp_id is None for _, _, erp_id in chain):
        stage = LeaveApprovalStage.objects.create(
            leave=leave,
            sequence=0,
            label="Section Head (legacy routing)",
            role_key="legacy_head",
            assigned_erp_id=leave.head_erpid,
        )
        notify_leave_stage_pending(leave, stage)
        return stage

    stages = [
        LeaveApprovalStage(
            leave=leave, sequence=seq, label=label,
            role_key=role_key, assigned_erp_id=erp_id,
        )
        for seq, (label, role_key, erp_id) in enumerate(chain)
    ]
    LeaveApprovalStage.objects.bulk_create(stages)
    notify_leave_stage_pending(leave, stages[0])
    return stages[0]


def get_current_stage(leave):
    return (
        LeaveApprovalStage.objects
        .filter(leave=leave, status="pending")
        .order_by("sequence")
        .first()
    )


def serialize_current_stage(leave):
    stage = get_current_stage(leave)
    if stage is None:
        return None
    return {
        "current_stage_label": stage.label,
        "current_stage_role": stage.role_key,
        "current_stage_erp_id": stage.assigned_erp_id,
    }


def leave_ids_visible_via_chain(erp_id):
   
    assigned = LeaveApprovalStage.objects.filter(
        assigned_erp_id=erp_id
    ).values_list("leave_id", flat=True)
    acted = LeaveApprovalStage.objects.filter(
        acted_by_erp_id=erp_id
    ).values_list("leave_id", flat=True)
    return set(assigned) | set(acted)


class ApprovalActionError(Exception):
    pass


def advance_leave_approval(leave_id, actor_erp_id, action, comment=None):

    if action not in ("approve", "reject"):
        raise ApprovalActionError("action must be 'approve' or 'reject'")

    leave = LeaveModel.objects.filter(pk=leave_id).first()
    if leave is None:
        raise ApprovalActionError("Leave request not found")

    if leave.status != "pending":
        raise ApprovalActionError(
            f"This leave is already '{leave.status}' and cannot be acted on again."
        )

    stage = get_current_stage(leave)
    if stage is None:
        raise ApprovalActionError("No pending approval stage found for this leave.")

    if int(actor_erp_id) != int(stage.assigned_erp_id or -1):
        raise ApprovalActionError(
            f"You are not the assigned approver for this stage ({stage.label})."
        )

    stage.status = "approved" if action == "approve" else "rejected"
    stage.acted_by_erp_id = actor_erp_id
    stage.comment = comment
    stage.acted_at = timezone.now()
    stage.save()

    if action == "reject":
        leave.status = "rejected"
        leave.save()
        LeaveApprovalStage.objects.filter(
            leave=leave, status="pending"
        ).update(status="skipped")
        notify_leave_decision(leave, "reject", actor_erp_id=actor_erp_id)
        return leave

    next_stage = (
        LeaveApprovalStage.objects
        .filter(leave=leave, status="pending")
        .order_by("sequence")
        .first()
    )
    if next_stage is None:
        leave.status = "approved"
        leave.save()
        notify_leave_decision(leave, "approve", actor_erp_id=actor_erp_id)
    else:
        notify_leave_stage_forwarded(leave, stage, comment=comment)
        notify_leave_stage_pending(leave, next_stage)

    return leave