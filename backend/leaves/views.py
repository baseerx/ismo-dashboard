from django.shortcuts import render
from django.http import JsonResponse
from .models import LeaveModel
from django.views.decorators.http import require_GET,require_POST
from django.views.decorators.csrf import csrf_exempt
import json
from sqlalchemy import text
from db import SessionLocal
# Create your views here.

@require_GET
def get_leave_requests(request):
    leaves = LeaveModel.objects.all()
    data=[]
    sessions= SessionLocal()
    query=text("""
    SELECT
        l.id,
               e.name,
        l.employee_id,
        l.erp_id,
        l.leave_type,
        l.start_date,
        l.end_date,
        l.reason,
        l.status,
        l.created_at
    FROM leaves l JOIN employees e ON l.employee_id = e.id 
""")
    
    result=sessions.execute(query).fetchall()
    for row in result:
        data.append({
            "id": row[0],
            "employee_name": row[1],
            "employee_id": row[2],
            "erp_id": row[3],
            "leave_type": row[4],
            "start_date": row[5].strftime('%Y-%m-%d'),
            "end_date": row[6].strftime('%Y-%m-%d'),
            "reason": row[7],
            "status": row[8],
            "created_at": row[9].strftime('%Y-%m-%d %H:%M:%S')
        })
    sessions.close()
    return JsonResponse({"leaves": data})

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
