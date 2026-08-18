"""Tool definitions handed to the model, and the dispatcher behind them.

This is the fallback path. Questions the intent router recognises are answered
from SQL with wording assembled in `answers.py`; these tools exist for the
phrasings it does not recognise, so an unusual question still gets real data
instead of a guess.

Every tool is scoped to the caller: the schemas below expose dates and leave
types, never an employee id, and the dispatcher passes the `Identity` through
itself. Prompt injection in a document therefore cannot talk the model into
fetching another employee's record, because there is no parameter for it.
"""

import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.auth.identity import Identity
from app.chat.tools.documents_tool import search_documents
from app.chat.tools.hr_data_tools import (
    get_attendance,
    get_leave_balance,
    get_leave_history,
    get_my_profile,
    get_official_work,
)
from app.chat.tools.navigation_tool import resolve_navigation

logger = logging.getLogger(__name__)

_DATE_ARGS = {
    "start_date": {
        "type": "string",
        "description": "First day of the period, as YYYY-MM-DD. Omit for the last 12 months.",
    },
    "end_date": {
        "type": "string",
        "description": "Last day of the period, as YYYY-MM-DD. Omit for today.",
    },
}

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": (
                "Search the organisation's trained HR policy documents. Use this for any "
                "question about rules, entitlements as written, procedures or definitions."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to look for"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_leave_balance",
            "description": (
                "The signed-in employee's own leave entitlement, days used and days "
                "remaining for the current financial year."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "leave_type": {
                        "type": "string",
                        "description": "Optional: one type, e.g. 'Casual Leave'. Omit for all types.",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_leave_history",
            "description": "The signed-in employee's own leave requests over a period.",
            "parameters": {
                "type": "object",
                "properties": {
                    **_DATE_ARGS,
                    "status": {
                        "type": "string",
                        "description": "Optional filter: approved, pending or rejected.",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_attendance",
            "description": (
                "The signed-in employee's own attendance day by day, with check-in and "
                "check-out times and whether each day was present, leave, holiday or absent."
            ),
            "parameters": {"type": "object", "properties": dict(_DATE_ARGS)},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_official_work",
            "description": "The signed-in employee's own official work / tour records over a period.",
            "parameters": {"type": "object", "properties": dict(_DATE_ARGS)},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_my_profile",
            "description": "Who the signed-in employee is: name, ERP id, section, designation, grade.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "navigate",
            "description": (
                "Offer the user a link to a page in the dashboard. Use when they want to "
                "*do* something (apply for leave, view the attendance screen)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "destination": {
                        "type": "string",
                        "enum": [
                            "leave_application", "leave_history", "official_work",
                            "attendance", "attendance_today", "public_holidays",
                            "profile", "dashboard", "change_password",
                        ],
                    }
                },
                "required": ["destination"],
            },
        },
    },
]

# Tools whose result is a table worth showing the user, and the key holding it.
DATA_TOOLS = {
    "get_leave_balance": "balances",
    "get_leave_history": "records",
    "get_attendance": "days",
    "get_official_work": "records",
}


async def dispatch_tool_call(
    tool_name: str,
    arguments: Dict[str, Any],
    db: Session,
    identity: Identity,
    document_id: Optional[int] = None,
) -> Any:
    arguments = arguments if isinstance(arguments, dict) else {}
    logger.info("dispatch_tool_call: tool=%s args=%s erp=%s", tool_name, arguments, identity.erp_id)

    try:
        if tool_name == "search_documents":
            return await search_documents(arguments.get("query", ""), document_id=document_id)

        if tool_name == "get_leave_balance":
            return get_leave_balance(db, identity, arguments.get("leave_type"))

        if tool_name == "get_leave_history":
            return get_leave_history(
                db,
                identity,
                arguments.get("start_date"),
                arguments.get("end_date"),
                arguments.get("status"),
            )

        if tool_name == "get_attendance":
            return get_attendance(db, identity, arguments.get("start_date"), arguments.get("end_date"))

        if tool_name == "get_official_work":
            return get_official_work(
                db, identity, arguments.get("start_date"), arguments.get("end_date")
            )

        if tool_name == "get_my_profile":
            return get_my_profile(db, identity)

        if tool_name == "navigate":
            return resolve_navigation(arguments.get("destination", ""))

        logger.warning("dispatch_tool_call: unknown tool %r", tool_name)
        return {"error": f"Unknown tool: {tool_name}"}

    except Exception as exc:
        logger.exception("dispatch_tool_call: %s failed", tool_name)
        return {"error": f"{tool_name} could not be completed: {exc}"}
