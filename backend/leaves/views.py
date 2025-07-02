from django.shortcuts import render
from django.http import JsonResponse
from .models import LeaveModel
from django.views.decorators.http import require_GET,require_POST
from django.views.decorators.csrf import csrf_exempt
import json

# Create your views here.

@require_GET
def get_leave_requests(request):
    leaves = LeaveModel.objects.all()
    data = {
        "leaves": [
            {
                "id": leave.id,
                "employee_id": leave.employee_id,
                "erp_id": leave.erp_id,
                "leave_type": leave.leave_type,
                "start_date": leave.start_date,
                "end_date": leave.end_date,
                "reason": leave.reason,
                "status": leave.status,
                "created_at": leave.created_at,
            }
            for leave in leaves
        ]
    }
    return JsonResponse(data)

@csrf_exempt
@require_POST
def create_leave_request(request):
    data = json.loads(request.body.decode('utf-8'))
    leave = LeaveModel.objects.create(
        erp_id=data.get("erp_id", 0),
        employee_id=data.get("employee_id", 0),
        leave_type=data.get("leave_type", ""),
        reason=data.get("reason", ""),
        status=data.get("status", ""),
        start_date=data.get("start_date"),
        end_date=data.get("end_date"),
    )
    
    return JsonResponse({"message": "Leave request created successfully", "id": leave.id})
