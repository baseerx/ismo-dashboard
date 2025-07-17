from django.urls import path, include
from .views import AttendanceView

urlpatterns = [
    path('get/', AttendanceView.get),
    path('today/', AttendanceView.todays_attendance),
    path('overview/<int:erpid>/', AttendanceView.attendance_overview),
    path('history/', AttendanceView.attendance_history),
    path('sections/', AttendanceView.attendance_section),
    path('status/', AttendanceView.attendance_status),
    path('individual/', AttendanceView.attendance_individual),
    path('detailed/', AttendanceView.attendance_detailed),
]
