
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .models import LeaveModel, LeaveApprovalStage


@require_GET
def get_leave_history(request, leave_id):
    leave = LeaveModel.objects.filter(pk=leave_id).first()
    if leave is None:
        return JsonResponse({"error": "Leave request not found"}, status=404)

    stages = LeaveApprovalStage.objects.filter(leave=leave).order_by("sequence")

    return JsonResponse({
        "leave_id": leave.pk,
        "leave_type": leave.leave_type,
        "overall_status": leave.status,
        "stages": [
            {
                "sequence": s.sequence,
                "label": s.label,
                "role": s.role_key,
                "assigned_erp_id": s.assigned_erp_id,
                "status": s.status,
                "acted_by_erp_id": s.acted_by_erp_id,
                "comment": s.comment,
                "acted_at": s.acted_at.strftime("%Y-%m-%d %H:%M:%S") if s.acted_at else None,
            }
            for s in stages
        ],
    }, status=200)