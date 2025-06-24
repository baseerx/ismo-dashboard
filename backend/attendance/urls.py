from django.urls import path, include
from .views import AttendanceView

urlpatterns = [
    path('get/', AttendanceView.get),
]
