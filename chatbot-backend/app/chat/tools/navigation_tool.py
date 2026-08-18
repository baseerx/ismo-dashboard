import logging
from typing import Optional

logger = logging.getLogger(__name__)

# PLACEHOLDER routes - replace these with your actual React Router paths.
# Could later be replaced by querying /api/mainmenu/get/ and /api/submenu/get/
# dynamically since that's already your menu system, but a static map is
# simpler to start with.
ROUTE_MAP = {
    "leave_application": {"path": "/leaves/apply", "label": "Apply for Leave"},
    "attendance": {"path": "/attendance", "label": "Attendance"},
    "profile": {"path": "/profile", "label": "My Profile"},
    "amendments": {"path": "/amendments", "label": "Amendments"},
    "compliance": {"path": "/compliance", "label": "Compliance"},
    "document_upload": {"path": "/documents/upload", "label": "Upload Document"},
}


def resolve_navigation(destination: str) -> Optional[dict]:
    logger.info("resolve_navigation: destination=%r", destination)
    entry = ROUTE_MAP.get(destination)
    if not entry:
        logger.warning("resolve_navigation: unknown destination=%r (not in ROUTE_MAP keys=%s)",
                        destination, list(ROUTE_MAP.keys()))
        return None
    result = {"type": "navigate", "path": entry["path"], "label": entry["label"]}
    logger.info("resolve_navigation: resolved to %s", result)
    return result