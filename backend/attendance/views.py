from django.shortcuts import render
from .models import Attendance  # Assuming you have an Attendance model defined
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from datetime import datetime
from sqlalchemy import text
from django.views.decorators.csrf import csrf_exempt
import json
from db import SessionLocal  # Assuming you have a SessionLocal defined for database access
# Create your views here.

class AttendanceView:
    @require_GET  # Ensure this view only responds to GET requests
    def get(request):
        attendance_records=Attendance.objects.all()  # Fetch all attendance records
        records = attendance_records.values(
            'uid', 'user_id', 'timestamp', 'status', 'punch'
        )
        attendance_list = list(records)
        return JsonResponse(attendance_list, safe=False)  # Return as JSON response
    
    @require_GET
    def todays_attendance(request):
        today = datetime.now().date()
        session = SessionLocal()
        records = []
        try:
            query = text("""
                SELECT 
                    a.id AS id,
                    u.id AS user_id,
                    u.name AS name,
                    a.uid AS uid,
                    a.timestamp AS timestamp,
                    a.status AS status,
                    a.punch AS punch
                FROM users u
                LEFT JOIN attendance a 
                    ON u.user_id = a.user_id AND DATE(a.timestamp) = :today
            """)
            result = session.execute(query, {"today": today})
            for row in result:

                records.append({
                    'id': row.id,
                    'uid': row.uid,
                    'user_id': row.user_id,
                    'name': row.name,
                    'timestamp': '-' if row.timestamp is None else row.timestamp,
                    'late': '-' if row.uid is None else 'late' if row.timestamp and row.timestamp.hour >= 9 else 'on time',  # Assuming 9 AM is the cutoff for being on time
                    'status': '-' if row.status is None else row.status,
                    'flag': 'Present' if row.uid is not None else 'Absent',
                    'punch': row.punch
                })
            return JsonResponse(records, safe=False)
        finally:
            session.close()
            

    @csrf_exempt
    @require_POST
    def attendance_history(request):
        data = json.loads(request.body)
        fromdate = data.get('fromdate')
        todate = data.get('todate')

        session = SessionLocal()
        records = []
        try:
            query = text("""
                SELECT 
                    a.id AS id,
                    u.id AS user_id,
                    u.name AS name,
                    a.uid AS uid,
                    a.timestamp AS timestamp,
                    a.status AS status,
                    a.punch AS punch
                FROM users u
                LEFT JOIN attendance a 
                    ON u.user_id = a.user_id AND DATE(a.timestamp) BETWEEN :fromdate AND :todate
            """)
            result = session.execute(query, {"fromdate": fromdate, "todate": todate})
            for row in result:
         
                records.append({
                    'id': row.id,
                    'uid': row.uid,
                    'user_id': row.user_id,
                    'name': row.name,
                    'timestamp': '-' if row.timestamp is None else row.timestamp,
                    # Assuming 9 AM is the cutoff for being on time
                    'late': '-' if row.uid is None else 'late' if row.timestamp and row.timestamp.hour >= 9 else 'on time',
                    'status': '-' if row.status is None else row.status,
                    'flag': 'Present' if row.uid is not None else 'Absent',
                    'punch': row.punch
                })
            return JsonResponse(records, safe=False)
        finally:
            session.close()
       
