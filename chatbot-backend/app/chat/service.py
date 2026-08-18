"""Answering one question.

The shape of a turn:

    verified identity + question
        -> understand()            what is being asked, about whom, for when
        -> authorise               is the asker allowed to see that person
        -> SQL or retrieval        facts, from the database or the manual
        -> answer                  templated for data, model-written for policy

Authorisation happens before any lookup, on the ERP id from the signed token.
An employee asking about a colleague is refused outright rather than quietly
shown their own record, because a quietly wrong answer is worse than a refusal.
"""

import json
import logging
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.auth.identity import Identity
from app.chat import answers
from app.chat.dates import default_range
from app.chat.intent import Intent, Subject, Understanding, is_about_the_asker, understand
from app.chat.schemas import Action, DataBlock, ReportOffer, SourceChunk
from app.chat.tools.navigation_tool import resolve_navigation
from app.chat.tools.registry import DATA_TOOLS, TOOL_DEFINITIONS, dispatch_tool_call
from app.config.settings import settings
from app.hr import queries as hr
from app.models.chat import Conversation, Message
from app.rag.prompt import NO_CONTEXT_ANSWER, build_messages
from app.rag.retriever import retrieve_top_chunks
from app.services.llm import chat_with_tools, generate_reply

logger = logging.getLogger(__name__)

# One round is enough for the fallback path: fetch, then answer. More rounds
# mostly produce a small model talking itself in circles.
MAX_TOOL_ROUNDS = 1

REFUSAL = (
    "I can only show you your own records. Another employee's leave or attendance "
    "can be looked up by an administrator, or through the section reports on the "
    "dashboard if you are their section head."
)

FALLBACK_SYSTEM_PROMPT = """You are the HR Assistant for ISMO's employee dashboard.

You are speaking with:
{identity}

What you can do: answer questions from the organisation's HR policy manual, and
report this person's own leave balance, leave records, official work and
attendance (including date ranges, and Excel or PDF reports of them).

Rules:
- Never state a figure for someone's leave or attendance unless a tool gave it
  to you in this conversation. If you do not have it, say what you can look up
  and invite them to ask for it.
- Never discuss another employee's records.
- Keep replies to a few sentences unless asked for detail. Markdown is fine.
"""


# --------------------------------------------------------------- persistence

def _get_or_create_conversation(
    db: Session, conversation_id: Optional[int], identity: Identity, question: str
) -> Conversation:
    if conversation_id:
        conversation = (
            db.query(Conversation)
            .filter(Conversation.id == conversation_id)
            .first()
        )
        # An id belonging to someone else is treated as absent rather than
        # refused: the asker gets a new thread and learns nothing about theirs.
        if conversation and conversation.owner_erp_id in (identity.erp_id, None):
            if conversation.owner_erp_id is None:
                conversation.owner_erp_id = identity.erp_id
                db.commit()
            return conversation
        logger.info(
            "conversation %s is not owned by erp=%s, starting a new one",
            conversation_id, identity.erp_id,
        )

    conversation = Conversation(
        owner_erp_id=identity.erp_id,
        # The first question makes a better thread title than "New chat", and
        # costs nothing to derive.
        title=(question or "").strip()[:120] or None,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def _load_history(db: Session, conversation: Conversation, limit: int = 6) -> List[Dict[str, str]]:
    recent = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(limit)
        .all()
    )
    recent.reverse()
    return [{"role": message.role, "content": message.content} for message in recent]


def _save(db: Session, conversation: Conversation, role: str, content: str, sources=None) -> None:
    db.add(
        Message(
            conversation_id=conversation.id,
            role=role,
            content=content,
            sources_json=json.dumps(sources, default=str) if sources else None,
        )
    )
    db.commit()


# ------------------------------------------------------------- authorisation

def _resolve_subject(
    db: Session, identity: Identity, understanding: Understanding
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Whose record the question is about.

    Returns (employee, refusal). Exactly one is set: an employee to report on,
    or the reply to send instead.
    """
    me = hr.get_employee(db, identity.erp_id) or {
        "erp_id": identity.erp_id,
        "name": identity.name,
        "section": identity.section_name,
    }

    # An explicit ERP id in the question.
    if understanding.target_erp_id and understanding.target_erp_id != identity.erp_id:
        if not identity.is_admin:
            return None, REFUSAL

        target = hr.get_employee(db, understanding.target_erp_id)
        if not target:
            return None, (
                f"I could not find an active employee with ERP ID "
                f"{understanding.target_erp_id}."
            )
        return target, None

    # A name that may or may not belong to a colleague - the employee table
    # decides, so a word that merely looks like a name costs one lookup.
    for candidate in understanding.target_name_candidates:
        matches = hr.find_employees(db, candidate)
        if not matches:
            continue

        if len(matches) > 1 and identity.is_admin:
            names = ", ".join(f"{m['name']} (ERP {m['erp_id']})" for m in matches[:5])
            return None, (
                f'Several employees match "{candidate}": {names}. '
                "Which ERP ID did you mean?"
            )

        found = matches[0]
        if found["erp_id"] == identity.erp_id:
            return me, None
        if not identity.is_admin:
            return None, REFUSAL
        return found, None

    # "his attendance" with nobody named.
    if understanding.about_someone_else and understanding.needs_data:
        if not identity.is_admin:
            return None, REFUSAL
        return None, (
            "Which employee do you mean? Give me a name or an ERP ID, for example "
            '"attendance of ERP 786 last week".'
        )

    return me, None


# ---------------------------------------------------------------- data paths

def _leave_balance(db, employee, understanding, is_self):
    leave_type = (
        hr.resolve_leave_type(db, understanding.leave_type_hint)
        if understanding.leave_type_hint
        else None
    )
    balance = hr.leave_balance(db, employee["erp_id"], leave_type=leave_type)
    answer, block = answers.leave_balance(employee, balance, is_self, leave_type)
    return answer, block, None


def _leave_history(db, employee, understanding, is_self):
    period = understanding.date_range or default_range()
    period = period.clamped(settings.REPORT_MAX_RANGE_DAYS)
    records = hr.leave_history(db, employee["erp_id"], period.start, period.end)
    answer, block = answers.leave_history(employee, records, period, is_self)
    offer = answers.report_offer("leave", employee, period) if records else None
    return answer, block, offer


def _attendance_day(db, employee, understanding, is_self):
    period = understanding.date_range
    day = period.start if period else date.today()
    snapshot = hr.attendance_day(db, employee["erp_id"], day)
    answer, block = answers.attendance_day(employee, snapshot, day, is_self)
    return answer, block, None


def _attendance_range(db, employee, understanding, is_self):
    period = (understanding.date_range or default_range()).until_today()
    period = period.clamped(settings.REPORT_MAX_RANGE_DAYS)
    ranged = hr.attendance_range(db, employee["erp_id"], period.start, period.end)
    answer, block = answers.attendance_range(employee, ranged, period, is_self)
    offer = answers.report_offer("attendance", employee, period) if ranged.get("days") else None
    return answer, block, offer


def _official_work(db, employee, understanding, is_self):
    period = (understanding.date_range or default_range()).clamped(settings.REPORT_MAX_RANGE_DAYS)
    records = hr.official_work(db, employee["erp_id"], period.start, period.end)
    answer, block = answers.official_work(employee, records, period, is_self)
    offer = answers.report_offer("official_work", employee, period) if records else None
    return answer, block, offer


def _report(db, employee, understanding, is_self):
    """A file, rather than a table on screen."""
    subject = {
        Subject.ATTENDANCE: "attendance",
        Subject.OFFICIAL_WORK: "official_work",
        Subject.LEAVE: "leave",
    }.get(understanding.subject, "leave")

    period = understanding.date_range
    if period is None:
        return (
            f"Which period should the {subject.replace('_', ' ')} report cover? "
            'Give me a range, for example "from 1 July 2026 to 31 July 2026" or "last month".',
            None,
            None,
        )

    if subject == "attendance":
        # A report of future days would list them all as absent.
        period = period.until_today()
    period = period.clamped(settings.REPORT_MAX_RANGE_DAYS)

    if subject == "attendance":
        ranged = hr.attendance_range(db, employee["erp_id"], period.start, period.end)
        rows = ranged.get("days", [])
        _, block = answers.attendance_range(employee, ranged, period, is_self)
    elif subject == "official_work":
        rows = hr.official_work(db, employee["erp_id"], period.start, period.end)
        _, block = answers.official_work(employee, rows, period, is_self)
    else:
        rows = hr.leave_history(db, employee["erp_id"], period.start, period.end)
        _, block = answers.leave_history(employee, rows, period, is_self)

    answer = answers.report_answer(
        subject, employee, period, len(rows), is_self, understanding.report_format
    )
    offer = (
        answers.report_offer(subject, employee, period, understanding.report_format)
        if rows or subject == "attendance"
        else None
    )
    return answer, block, offer


DATA_HANDLERS = {
    Intent.LEAVE_BALANCE: _leave_balance,
    Intent.LEAVE_HISTORY: _leave_history,
    Intent.ATTENDANCE_DAY: _attendance_day,
    Intent.ATTENDANCE_RANGE: _attendance_range,
    Intent.OFFICIAL_WORK: _official_work,
    Intent.REPORT: _report,
}


# ---------------------------------------------------------------- rag / llm

def _policy_answer(
    question: str, history: List[Dict[str, str]], document_id: Optional[int]
) -> Tuple[str, List[Dict]]:
    chunks = retrieve_top_chunks(question, document_id=document_id)
    if not chunks:
        return NO_CONTEXT_ANSWER, []

    answer = generate_reply(build_messages(question, chunks, history))
    return (answer or "").strip() or NO_CONTEXT_ANSWER, chunks


async def _fallback_answer(
    db: Session,
    identity: Identity,
    question: str,
    history: List[Dict[str, str]],
    document_id: Optional[int],
) -> Tuple[str, List[Dict], Optional[DataBlock], List[Dict]]:
    """For questions the router did not recognise.

    Which source is tried first depends on who the question is about. A
    retrieval store always returns its nearest passages, so asking the manual
    "am I running low on days off?" yields the policy maximum - a number that
    reads like an answer about this person and is not one. Questions phrased
    about the asker therefore go to the tools, which return their actual
    record; everything else goes to the manual.
    """
    chunks: List[Dict] = []

    if not is_about_the_asker(question):
        chunks = retrieve_top_chunks(question, document_id=document_id)
        if chunks:
            answer = generate_reply(build_messages(question, chunks, history))
            if answer and answer.strip():
                return answer.strip(), chunks, None, []

    messages = [
        {"role": "system", "content": FALLBACK_SYSTEM_PROMPT.format(identity=identity.describe())},
        *history,
        {"role": "user", "content": question},
    ]

    block: Optional[DataBlock] = None
    actions: List[Dict] = []
    answer = ""

    for _ in range(MAX_TOOL_ROUNDS + 1):
        message = chat_with_tools(messages, tools=TOOL_DEFINITIONS)
        tool_calls = message.get("tool_calls") or []

        if not tool_calls:
            answer = (message.get("content") or "").strip()
            break

        messages.append(message)

        for call in tool_calls:
            name = call["function"]["name"]
            arguments = call["function"].get("arguments") or {}
            result = await dispatch_tool_call(name, arguments, db, identity, document_id)

            if name == "navigate" and result:
                actions.append(result)
            elif name == "search_documents" and isinstance(result, list):
                chunks = result
            elif name in DATA_TOOLS and isinstance(result, dict):
                block = _block_from_tool(name, result)

            messages.append({"role": "tool", "content": json.dumps(result, default=str)[:6000]})

    if not answer:
        answer = (
            "I could not work that one out. I can answer questions from the HR manual, and "
            "show your leave balance, leave records, official work or attendance for any "
            "period — including an Excel or PDF report."
        )

    return answer, chunks, block, actions


def _block_from_tool(name: str, result: Dict[str, Any]) -> Optional[DataBlock]:
    """Show the model's tool result as a table, so the figures on screen are the
    ones the database returned rather than the ones it chose to repeat."""
    key = DATA_TOOLS[name]
    rows = result.get(key) or []
    if not rows:
        return None

    columns = list(rows[0].keys())
    return DataBlock(
        title={
            "get_leave_balance": "Leave balance",
            "get_leave_history": "Leave records",
            "get_attendance": "Attendance",
            "get_official_work": "Official work",
        }[name],
        columns=[{"key": column, "label": column.replace("_", " ").title()} for column in columns],
        rows=[{column: _plain(row.get(column)) for column in columns} for row in rows],
        summary=result.get("summary") or {},
    )


def _plain(value: Any) -> Any:
    if isinstance(value, (str, int, float)) or value is None:
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()[:10]
    return str(value)


# ----------------------------------------------------------------- entry point

async def answer_question(
    db: Session,
    question: str,
    identity: Identity,
    conversation_id: Optional[int] = None,
    document_id: Optional[int] = None,
) -> Dict[str, Any]:
    conversation = _get_or_create_conversation(db, conversation_id, identity, question)
    history = _load_history(db, conversation)
    _save(db, conversation, "user", question)

    understanding = understand(question)
    logger.info(
        "answer_question: erp=%s admin=%s intent=%s subject=%s range=%s",
        identity.erp_id,
        identity.is_admin,
        understanding.intent.value,
        understanding.subject.value if understanding.subject else None,
        understanding.date_range.label if understanding.date_range else None,
    )

    sources: List[Dict] = []
    actions: List[Dict] = []
    block: Optional[DataBlock] = None
    offer: Optional[ReportOffer] = None

    if understanding.navigate_to:
        navigation = resolve_navigation(understanding.navigate_to)
        if navigation:
            actions.append(navigation)

    if understanding.intent in DATA_HANDLERS:
        employee, refusal = _resolve_subject(db, identity, understanding)
        if refusal:
            answer = refusal
            actions = []
        else:
            is_self = employee["erp_id"] == identity.erp_id
            answer, block, offer = DATA_HANDLERS[understanding.intent](
                db, employee, understanding, is_self
            )

    elif understanding.intent is Intent.PROFILE:
        employee = hr.get_employee(db, identity.erp_id) or {
            "erp_id": identity.erp_id, "name": identity.name
        }
        answer, block = answers.profile(employee, identity.name, identity.is_admin)

    elif understanding.intent is Intent.POLICY:
        answer, sources = _policy_answer(question, history, document_id)

    elif understanding.intent is Intent.SMALLTALK:
        answer = (
            answers.courtesy()
            if understanding.is_courtesy
            else answers.greeting(identity.name, identity.is_admin)
        )

    elif understanding.intent is Intent.NAVIGATE:
        label = actions[0]["label"] if actions else "that page"
        answer = (
            f"Opening **{label}** for you — use the button below if it does not switch over."
            if actions
            else "I am not sure which page you mean. Try \"apply for leave\" or \"open attendance\"."
        )

    else:
        answer, sources, block, tool_actions = await _fallback_answer(
            db, identity, question, history, document_id
        )
        actions.extend(tool_actions)

    trimmed_sources = [
        SourceChunk(
            document_id=chunk.get("document_id"),
            filename=chunk.get("filename"),
            chunk_index=chunk.get("chunk_index"),
            page_number=chunk.get("page_number"),
            distance=chunk.get("distance"),
        ).model_dump()
        for chunk in sources
    ]

    _save(db, conversation, "assistant", answer, trimmed_sources or None)

    return {
        "conversation_id": conversation.id,
        "answer": answer,
        "intent": understanding.intent.value,
        "sources": trimmed_sources,
        "actions": [Action(**action).model_dump() for action in actions],
        "data": block.model_dump() if block else None,
        "report": offer.model_dump() if offer else None,
    }
