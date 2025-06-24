from django.shortcuts import render
from .models import Attendance  # Assuming you have an Attendance model defined
from django.http import JsonResponse
# Create your views here.

class AttendanceView:
    def get(request):
        attendance_records=Attendance.objects.all()  # Fetch all attendance records
        records = attendance_records.values(
            'uid', 'user_id', 'timestamp', 'status', 'punch'
        )
        attendance_list = list(records)
        return JsonResponse(attendance_list, safe=False)  # Return as JSON response