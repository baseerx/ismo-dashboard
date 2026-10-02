import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .approval_workflow import advance_leave_approval, ApprovalActionError


@csrf_exempt
@require_POST
def advance_leave(request):
    data = json.loads(request.body.decode("utf-8"))

    leave_id = data.get("recordid")
    actor_erp_id = data.get("actor_erp_id")
    action = data.get("action")
    comment = data.get("comment")

    if not all([leave_id, actor_erp_id, action]):
        return JsonResponse(
            {"error": "recordid, actor_erp_id and action are required"},
            status=400,
        )

    try:
        leave = advance_leave_approval(leave_id, actor_erp_id, action, comment)
    except ApprovalActionError as e:
        return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse(
        {
            "message": f"Leave stage {action}d successfully",
            "leave_id": leave.pk,
            "leave_status": leave.status,
        },
        status=200,
    )