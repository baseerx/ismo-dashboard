from typing import Any, Dict, Optional


def build_user_context_block(user_context: Optional[Dict[str, Any]]) -> str:
    """
    The frontend already has the logged-in user's profile cached in
    localStorage (name, erpid, department, etc - same object your
    AttendanceOverview.tsx reads). Rather than re-deriving this
    server-side, the frontend sends it along with each chat request and
    this just formats it into the system prompt.
    """
    if not user_context:
        return "The current user's identity is unknown."

    lines = ["You are speaking with:"]
    for label, key in [
        ("Name", "name"),
        ("Role", "role"),
        ("Department", "department"),
        ("Employee ID", "erpid"),
        ("Manager", "manager"),
    ]:
        value = user_context.get(key)
        if value:
            lines.append(f"- {label}: {value}")

    return "\n".join(lines)
