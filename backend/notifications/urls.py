from django.urls import path

from .views import get_notifications, mark_read, mark_all_read

urlpatterns = [
    path("get/<int:erpid>/", get_notifications, name="get_notifications"),
    path("mark-read/", mark_read, name="mark_read"),
    path("mark-all-read/", mark_all_read, name="mark_all_read"),
]
