from django.urls import path, include
from .views import AttendanceView

urlpatterns = [
    path('get/', AttendanceView.get),
    path('today/', AttendanceView.todays_attendance),
    path('history/', AttendanceView.attendance_history),
    path('sections/', AttendanceView.attendance_section),
    path('individual/', AttendanceView.attendance_individual),
]
