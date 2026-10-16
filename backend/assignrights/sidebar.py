"""The menu the sidebar shows a signed-in user: exactly what Assign Rights has
granted them, page for page. No page is added for everyone and none is held
back - including Internal Recruitment Portal > Job Application, which is shown
to whoever it is assigned to.
"""

from django.http import JsonResponse
from django.views.decorators.http import require_GET
from sqlalchemy import text

from db import SessionLocal


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

        return JsonResponse(
            [
                {"id": row.id, "mainmenu": row.mainmenu, "submenu": row.submenu, "uri": row.uri}
                for row in granted
            ],
            safe=False,
            status=200,
        )
    except Exception as error:
        return JsonResponse({"error": str(error)}, status=500)
    finally:
        session.close()
