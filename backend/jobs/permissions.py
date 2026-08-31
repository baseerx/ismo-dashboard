"""Who may advertise and withdraw vacancies.

Reading the list of openings is open, like the rest of this API. Writing is not:
a vacancy is published to every employee, so it should not be creatable by an
unauthenticated POST.

The gate is deliberately not `is_staff` — 209 of the 213 accounts carry that
flag, so it grants nothing. It is instead: a superuser, or anyone the Assign
Rights screen has granted this page to. That keeps the decision where this
application already makes it, and lets HR manage vacancies without being handed
superuser rights.

As in assignrights/chatbot_visibility.py, the token's one-hour `expires` stamp is
not enforced: nothing else in this API checks it and the frontend does not sign
people out, so enforcing it here would reject an administrator who had been
logged in since the morning.
"""

import logging

import jwt
from django.conf import settings
from sqlalchemy import text

from db import SessionLocal

logger = logging.getLogger(__name__)

# The management page. A user granted this sub-menu may maintain vacancies.
MANAGE_URI = "/job-requisitions"


def identity_from_request(request):
    """The signed-in user behind this request, or (None, reason)."""
    header = request.headers.get("Authorization") or ""
    token = header[7:].strip() if header.lower().startswith("bearer ") else header.strip()

    if not token:
        # Shared by the vacancy and reports pages, so nothing page-specific.
        return None, "Sign in again to continue."

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"],
            options={"verify_exp": False},
        )
    except jwt.PyJWTError:
        return None, "That session is not valid any more. Sign in again."

    return payload, None


def _has_menu_right(auth_user_id, uri: str = MANAGE_URI) -> bool:
    """True when Assign Rights has granted this user the given sub-menu page.

    `uri` defaults to MANAGE_URI (vacancy management) so existing callers are
    unaffected; other pages - e.g. the applications report - pass their own
    sub-menu URI to reuse this same lookup against a different grant.
    """
    if not auth_user_id:
        return False

    session = SessionLocal()
    try:
        row = session.execute(
            text(
                """
                SELECT TOP 1 a.id
                FROM assign_rights a
                JOIN sub_menu s ON s.id = a.sub_menu
                WHERE a.user_id = :user_id AND s.uri = :uri
                """
            ),
            {"user_id": auth_user_id, "uri": uri},
        ).first()
        return row is not None
    except Exception:
        # A permissions lookup that cannot run must not read as "allowed".
        logger.exception("could not check menu rights for user %s (uri=%s)", auth_user_id, uri)
        return False
    finally:
        session.close()


def require_requisition_manager(request):
    """Returns (identity, refusal). Exactly one is set."""
    identity, refusal = identity_from_request(request)
    if refusal:
        return None, refusal

    if identity.get("is_superuser"):
        return identity, None

    if _has_menu_right(identity.get("user_id")):
        return identity, None

    return None, (
        "You do not have rights to manage vacancies. An administrator can grant "
        "them from Assign Rights."
    )