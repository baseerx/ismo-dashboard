"""Who may view and export submitted job applications.

Separate from `require_requisition_manager` on purpose: "can advertise a
vacancy" and "can see every applicant's CNIC, phone number, and full
application" are different levels of trust. A recruiter can be granted this
page's sub-menu without also being handed the ability to open or close
vacancies, and vice versa.
"""

from .permissions import _has_menu_right, identity_from_request

# Matches the sub_menu row already created for this page:
#   Internal Recruitment Portal > Job Reports > /job-reports
REPORTS_URI = "/job-reports"


def require_applications_viewer(request):
    """Returns (identity, refusal). Exactly one is set."""
    identity, refusal = identity_from_request(request)
    if refusal:
        return None, refusal

    if identity.get("is_superuser"):
        return identity, None

    if _has_menu_right(identity.get("user_id"), REPORTS_URI):
        return identity, None

    return None, (
        "You do not have rights to view job applications. An administrator can "
        "grant them from Assign Rights."
    )