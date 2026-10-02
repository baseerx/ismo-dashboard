from django.urls import path
from .views import get_leave_requests, get_leaves_count, create_leave_request, handle_leave_request, individual_report, section_leave_report, individual_detail_report, leavetype_detail_report, get_leave_balance, get_leave_types, download_leave_attachment
from .portal_extensions import get_leave_balance_summary, duplicate_employee_report
from .advance_leave_view import advance_leave
from .leave_history_view import get_leave_history

urlpatterns = [
    path("get/<int:erpid>/", get_leave_requests, name="get_leave_requests"),
    path("types/", get_leave_types, name="get_leave_types"),
    path("attachment/<int:leave_id>/", download_leave_attachment,
         name="download_leave_attachment"),
    path("apply/", create_leave_request, name="create_leave_request"),
    path("balance/", get_leave_balance, name="get_leave_balance"),
    path("history/", get_leaves_count, name="get_leaves_count"),
    path("individual-report/", individual_report, name="individual_report"),
    path("individual-detail-report/", individual_detail_report, name="individual_detail_report"),
    path("leavetype-detail-report/", leavetype_detail_report,
         name="leavetype_detail_report"),
    path("section-leave-report/", section_leave_report, name="section_leave_report"),
    path("approve/", handle_leave_request, name="handle_leave_request"),
    path("balance-summary/<int:erpid>/", get_leave_balance_summary, name="get_leave_balance_summary"),
    path("duplicate-employees/", duplicate_employee_report, name="duplicate_employee_report"),

    path("advance/", advance_leave, name="advance_leave"),
    path("history/<int:leave_id>/", get_leave_history, name="get_leave_history"),
]