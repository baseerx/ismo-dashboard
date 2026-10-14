"""The menu the sidebar shows a signed-in user.

Mostly what Assign Rights has granted them - plus a few pages every employee
can use without being granted anything, such as the internal job application
form. Those are added here rather than as assign_rights rows, so a new
employee sees them from their first sign-in and the Assign Rights screen only
ever lists what an administrator actually granted.
"""

from django.http import JsonResponse
from django.views.decorators.http import require_GET
from sqlalchemy import text

from db import SessionLocal

# Pages on every employee's menu, by their sub_menu.uri.
ALWAYS_VISIBLE_URIS = (
    "/internal-job-application",
)

_COLUMNS = "m.name AS mainmenu, s.sub_menu AS submenu, s.uri"


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

        have = {item["uri"] for item in items}
        missing = [uri for uri in ALWAYS_VISIBLE_URIS if uri not in have]
        if missing:
            placeholders = ", ".join(f":uri{index}" for index in range(len(missing)))
            for row in session.execute(
                text(f"""
                    SELECT s.id, {_COLUMNS}
                    FROM sub_menu s
                    INNER JOIN main_menu m ON s.main_menu = m.id
                    WHERE s.uri IN ({placeholders})
                """),
                {f"uri{index}": uri for index, uri in enumerate(missing)},
            ).fetchall():
                items.append({
                    "id": None,
                    "mainmenu": row.mainmenu,
                    "submenu": row.submenu,
                    "uri": row.uri,
                    # Not an assign_rights row: there is nothing to revoke.
                    "always_visible": True,
                })

        return JsonResponse(items, safe=False, status=200)
    except Exception as error:
        return JsonResponse({"error": str(error)}, status=500)
    finally:
        session.close()
