"""The menu the sidebar shows a signed-in user: exactly what Assign Rights has
granted them, page for page. No page is added for everyone.

One exception holds pages back: internees never get Internal Recruitment
Portal > Job Application, even if a right was assigned to them. The job
application endpoints refuse internees as well (see jobs/applicant.py).
"""

from django.http import JsonResponse
from django.views.decorators.http import require_GET
from sqlalchemy import text

from db import SessionLocal
from jobs.applicant import APPLICATION_URI, internee_auth_user
from jobs.permissions import identity_from_request


def _withheld(session, user_id) -> set:
    """Page addresses this user is never shown, whatever is assigned."""
    return {APPLICATION_URI} if internee_auth_user(session, user_id) else set()


@require_GET
def my_pages(request):
    """The page addresses the signed-in user has been granted, for the
    frontend's route guard. The user comes from the sign-in token rather than
    an id in the URL, so one user cannot ask for another's pages."""
    identity, refusal = identity_from_request(request)
    if refusal:
        return JsonResponse({"error": refusal}, status=401)
    user_id = identity.get("user_id")
    if not user_id:
        return JsonResponse({"error": "Sign in again to continue."}, status=401)

    session = SessionLocal()
    try:
        rows = session.execute(
            text("""
                SELECT DISTINCT s.uri
                FROM assign_rights a
                INNER JOIN sub_menu s ON a.sub_menu = s.id
                INNER JOIN auth_user u ON u.id = a.user_id AND u.is_active = 1
                WHERE a.user_id = :id
            """),
            {"id": user_id},
        ).fetchall()
        withheld = _withheld(session, user_id)
        return JsonResponse(
            {"uris": [row.uri for row in rows if row.uri and row.uri not in withheld]},
            status=200,
        )
    except Exception as error:
        return JsonResponse({"error": str(error)}, status=500)
    finally:
        session.close()


@require_GET
def sidebar_menu(request, id):
    session = SessionLocal()
    try:
        granted = session.execute(
            text("""
                SELECT a.id, m.name AS mainmenu, s.sub_menu AS submenu, s.uri
                FROM assign_rights a
                INNER JOIN main_menu m ON a.main_menu = m.id
                INNER JOIN sub_menu s ON a.sub_menu = s.id
                WHERE a.user_id = :id
            """),
            {"id": id},
        ).fetchall()
        withheld = _withheld(session, id)

        return JsonResponse(
            [
                {"id": row.id, "mainmenu": row.mainmenu, "submenu": row.submenu, "uri": row.uri}
                for row in granted
                if row.uri not in withheld
            ],
            safe=False,
            status=200,
        )
    except Exception as error:
        return JsonResponse({"error": str(error)}, status=500)
    finally:
        session.close()
