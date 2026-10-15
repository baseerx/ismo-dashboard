"""The menu the sidebar shows a signed-in user.

What Assign Rights has granted them, with one page under a stricter rule: the
internal job application form (Internal Recruitment Portal > Job Application)
is shown only to the accounts listed in RESTRICTED_EMAILS - not to other
superusers, and not to anyone Assign Rights grants it to.

The rule is applied here, on what the sidebar is sent, so the Assign Rights
screen still lists exactly what an administrator granted.
"""

from django.http import JsonResponse
from django.views.decorators.http import require_GET
from sqlalchemy import text

from db import SessionLocal

# The page under the stricter rule, by its sub_menu.uri.
RESTRICTED_URI = "/internal-job-application"

# The only accounts that see it, by their auth_user email. Add an address here
# to show the page to someone else.
RESTRICTED_EMAILS = ("baxeerkhan@gmail.com",)

_COLUMNS = "m.name AS mainmenu, s.sub_menu AS submenu, s.uri"


def _may_see_restricted(session, user_id) -> bool:
    """Only the accounts in RESTRICTED_EMAILS."""
    email = session.execute(
        text("SELECT email FROM auth_user WHERE id = :id AND is_active = 1"),
        {"id": user_id},
    ).scalar()
    allowed = {address.strip().lower() for address in RESTRICTED_EMAILS}
    return bool(email) and email.strip().lower() in allowed


@require_GET
def sidebar_menu(request, id):
    session = SessionLocal()
    try:
        granted = session.execute(
            text(f"""
                SELECT a.id, {_COLUMNS}
                FROM assign_rights a
                INNER JOIN main_menu m ON a.main_menu = m.id
                INNER JOIN sub_menu s ON a.sub_menu = s.id
                WHERE a.user_id = :id
            """),
            {"id": id},
        ).fetchall()

        items = [
            {"id": row.id, "mainmenu": row.mainmenu, "submenu": row.submenu, "uri": row.uri}
            for row in granted
        ]

        allowed = _may_see_restricted(session, id)
        if not allowed:
            items = [item for item in items if item["uri"] != RESTRICTED_URI]
        elif not any(item["uri"] == RESTRICTED_URI for item in items):
            # A listed account sees it even without an Assign Rights grant.
            row = session.execute(
                text(f"""
                    SELECT s.id, {_COLUMNS}
                    FROM sub_menu s
                    INNER JOIN main_menu m ON s.main_menu = m.id
                    WHERE s.uri = :uri
                """),
                {"uri": RESTRICTED_URI},
            ).first()
            if row is not None:
                items.append({
                    "id": None,
                    "mainmenu": row.mainmenu,
                    "submenu": row.submenu,
                    "uri": row.uri,
                })

        return JsonResponse(items, safe=False, status=200)
    except Exception as error:
        return JsonResponse({"error": str(error)}, status=500)
    finally:
        session.close()
