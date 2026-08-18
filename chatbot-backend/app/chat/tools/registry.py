import logging
from typing import Any, Dict, Optional

from app.chat.tools.documents_tool import search_documents
from app.chat.tools.hr_data_tools import (
    get_attendance_today,
    get_leave_balance,
    get_leave_history,
    get_official_work_balance,
)
from app.chat.tools.navigation_tool import resolve_navigation

logger = logging.getLogger(__name__)

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": "Search HR policy documents, SOPs, and company documents for information.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "What to search for"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_leave_balance",
            "description": "Get the current logged-in user's remaining leave balance.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_leave_history",
            "description": "Get the current logged-in user's past leave requests.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_attendance_today",
            "description": "Get the current logged-in user's attendance status for today.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_official_work_balance",
            "description": "Get the current logged-in user's official work balance.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "navigate",
            "description": (
                "Open a page in the application for the user. Use this when the user "
                "wants to DO something (apply for leave, check attendance, edit profile) "
                "rather than just ask about it."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "destination": {
                        "type": "string",
                        "enum": [
                            "leave_application", "attendance", "profile",
                            "amendments", "compliance", "document_upload",
                        ],
                    },
                },
                "required": ["destination"],
            },
        },
    },
]


async def dispatch_tool_call(
    tool_name: str, arguments: Dict[str, Any], auth_header: Optional[str]
) -> Any:
    logger.info("dispatch_tool_call: tool=%s args=%s", tool_name, arguments)

    try:
        if tool_name == "search_documents":
            return await search_documents(arguments.get("query", ""))
        if tool_name == "get_leave_balance":
            return await get_leave_balance(auth_header)
        if tool_name == "get_leave_history":
            return await get_leave_history(auth_header)
        if tool_name == "get_attendance_today":
            return await get_attendance_today(auth_header)
        if tool_name == "get_official_work_balance":
            return await get_official_work_balance(auth_header)
        if tool_name == "navigate":
            return resolve_navigation(arguments.get("destination", ""))

        logger.warning("dispatch_tool_call: unknown tool requested: %s", tool_name)
        return {"error": f"Unknown tool: {tool_name}"}

    except Exception as exc:
        logger.exception("dispatch_tool_call: %s raised an exception", tool_name)
        return {"error": f"{tool_name} failed: {exc}"}