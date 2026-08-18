"""Where in the dashboard a request can be sent.

The paths are the ones registered in the frontend's `App.tsx`. A link that does
not resolve drops the user on a blank page, so this map is the only place they
are written down and it is checked against the router when routes change.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

ROUTE_MAP = {
    "leave_application": {"path": "/leaves/apply", "label": "Apply for leave"},
    "leave_history": {"path": "/leaves/leave-history", "label": "Leave history"},
    "official_work": {"path": "/leaves/official-work", "label": "Official work"},
    "attendance": {"path": "/attendance/overview", "label": "My attendance"},
    "attendance_today": {"path": "/attendance/today", "label": "Today's attendance"},
    "public_holidays": {"path": "/leaves/public-holidays", "label": "Public holidays"},
    "profile": {"path": "/profile", "label": "My profile"},
    "dashboard": {"path": "/dashboard", "label": "Dashboard"},
    "change_password": {"path": "/change-password", "label": "Change password"},
}


def resolve_navigation(destination: str) -> Optional[dict]:
    entry = ROUTE_MAP.get((destination or "").strip())
    if not entry:
        logger.info("resolve_navigation: no route for %r", destination)
        return None

    return {"type": "navigate", "path": entry["path"], "label": entry["label"]}
