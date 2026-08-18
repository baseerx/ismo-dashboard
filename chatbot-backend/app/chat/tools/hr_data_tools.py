import logging
from typing import Any, Dict, Optional

from app.services.django_client import django_get

logger = logging.getLogger(__name__)

# NOTE: paths below assume /api/leaves/balance/, /api/attendance/my-today/,
# and /api/officialwork/balance/ all derive the user from request.user
# (they take no erpid in the URL, unlike attendance/overview/<erpid>/ which
# is clearly for viewing someone else). Test each against your real
# views.py - if any of these actually require an erpid param, add it to
# the `params` dict below.


async def get_leave_balance(auth_header: Optional[str]) -> Dict[str, Any]:
    logger.info("get_leave_balance: calling /api/leaves/balance/ (auth_present=%s)", bool(auth_header))
    result = await django_get("/api/leaves/balance/", auth_header)
    logger.info("get_leave_balance: result=%s", result)
    return result


async def get_leave_history(auth_header: Optional[str]) -> Dict[str, Any]:
    logger.info("get_leave_history: calling /api/leaves/history/ (auth_present=%s)", bool(auth_header))
    result = await django_get("/api/leaves/history/", auth_header)
    logger.info("get_leave_history: result=%s", result)
    return result


async def get_attendance_today(auth_header: Optional[str]) -> Dict[str, Any]:
    logger.info("get_attendance_today: calling /api/attendance/my-today/ (auth_present=%s)", bool(auth_header))
    result = await django_get("/api/attendance/my-today/", auth_header)
    logger.info("get_attendance_today: result=%s", result)
    return result


async def get_official_work_balance(auth_header: Optional[str]) -> Dict[str, Any]:
    logger.info("get_official_work_balance: calling /api/officialwork/balance/ (auth_present=%s)", bool(auth_header))
    result = await django_get("/api/officialwork/balance/", auth_header)
    logger.info("get_official_work_balance: result=%s", result)
    return result

# get_profile intentionally removed: /api/users/details/ is NOT a "my
# profile" endpoint - it returns Create Employee form metadata (sections,
# locations, grades, a randomly generated new_hris_id for registering a
# NEW employee). The user's real profile (name, erpid, section, grade,
# gender, email) is already returned once at login by UsersView.login_user
# and cached in the frontend's localStorage("user") - that's exactly what
# gets sent as `user_context` with every chat request. Profile questions
# are answered directly from the system prompt, no tool call needed.