import json
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.chat.context import build_user_context_block
from app.chat.tools.registry import TOOL_DEFINITIONS, dispatch_tool_call
from app.models.chat import Conversation, Message
from app.services.llm import chat_with_tools

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = """You are the HR Assistant for this company's internal system.

{user_context}

IMPORTANT: If the user asks about their own name, ID, or department (e.g.
"what is my name", "who am I"), answer DIRECTLY from the information above
in your very next sentence. Do not say you lack a way to know this, and do
not suggest navigating anywhere to find it - it is already given to you.

You have tools available to look up the current user's own leave balance,
attendance, and official work balance - use them when asked about "my"
data. Use search_documents for policy/SOP questions. Use navigate when
the user wants to DO something (apply for leave, go to attendance, etc)
rather than just ask about it.

For casual conversation or general questions about what you can do, just
answer directly - do not call any tool unless the question actually needs
one. Keep answers natural and concise."""

MAX_TOOL_ROUNDS = 3


def _get_or_create_conversation(db: Session, conversation_id: Optional[int]) -> Conversation:
    if conversation_id:
        conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if conversation:
            logger.info("answer_question: continuing conversation_id=%s", conversation.id)
            return conversation

    conversation = Conversation()
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    logger.info("answer_question: created new conversation_id=%s", conversation.id)
    return conversation


def _load_history(db: Session, conversation: Conversation, limit: int = 10) -> List[Dict[str, str]]:
    """Feeds recent turns back into the LLM so follow-up questions work."""
    recent = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.desc())
        .limit(limit)
        .all()
    )
    recent.reverse()
    logger.info("answer_question: loaded %d prior message(s) as history", len(recent))
    return [{"role": m.role, "content": m.content} for m in recent]


async def answer_question(
    db: Session,
    question: str,
    conversation_id: Optional[int],
    user_context: Optional[Dict[str, Any]],
    auth_header: Optional[str],
) -> Dict:
    logger.info("answer_question: question=%r user=%s auth_present=%s",
                question,
                (user_context or {}).get("username", "unknown"),
                bool(auth_header))
    logger.info("answer_question: RAW user_context received=%s", user_context)

    conversation = _get_or_create_conversation(db, conversation_id)

    db.add(Message(conversation_id=conversation.id, role="user", content=question))
    db.commit()

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        user_context=build_user_context_block(user_context)
    )
    logger.info("answer_question: system prompt built (%d chars)", len(system_prompt))
    logger.info("answer_question: FULL system prompt:\n%s", system_prompt)

    messages = [{"role": "system", "content": system_prompt}]
    messages += _load_history(db, conversation)
    messages.append({"role": "user", "content": question})

    sources: List[Dict] = []
    actions: List[Dict] = []
    answer = "I wasn't able to finish processing that - could you try rephrasing?"

    for round_num in range(MAX_TOOL_ROUNDS):
        logger.info("answer_question: round %d - calling LLM with %d message(s), %d tool(s) available",
                    round_num, len(messages), len(TOOL_DEFINITIONS))

        message = chat_with_tools(messages, tools=TOOL_DEFINITIONS)
        tool_calls = message.get("tool_calls")

        if not tool_calls:
            answer = message.get("content", "")
            logger.info("answer_question: round %d - no tool calls, final answer (%d chars): %r",
                        round_num, len(answer), answer[:200])
            break

        tool_names = [c["function"]["name"] for c in tool_calls]
        logger.info("answer_question: round %d - model requested %d tool call(s): %s",
                    round_num, len(tool_calls), tool_names)

        messages.append(message)

        for call in tool_calls:
            name = call["function"]["name"]
            args = call["function"].get("arguments", {})
            logger.info("answer_question: dispatching tool=%s args=%s", name, args)

            result = await dispatch_tool_call(name, args, auth_header)
            logger.info("answer_question: tool=%s returned: %s", name,
                        _summarize_for_log(result))

            if name == "search_documents" and isinstance(result, list):
                sources.extend(
                    {
                        "document_id": c["document_id"],
                        "filename": c["filename"],
                        "chunk_index": c["chunk_index"],
                        "distance": c["distance"],
                    }
                    for c in result
                )
            elif name == "navigate" and result:
                actions.append(result)

            messages.append({
                "role": "tool",
                "content": json.dumps(result, default=str),
            })
    else:
        logger.warning("answer_question: hit MAX_TOOL_ROUNDS=%d without a final answer", MAX_TOOL_ROUNDS)

    db.add(Message(
        conversation_id=conversation.id,
        role="assistant",
        content=answer,
        sources_json=json.dumps(sources) if sources else None,
    ))
    db.commit()

    logger.info("answer_question: done - %d source(s), %d action(s)", len(sources), len(actions))

    return {
        "conversation_id": conversation.id,
        "answer": answer,
        "sources": sources,
        "actions": actions,
    }


def _summarize_for_log(result: Any, max_len: int = 300) -> str:
    """Keeps tool-result log lines readable instead of dumping full chunk text."""
    text = json.dumps(result, default=str)
    return text if len(text) <= max_len else text[:max_len] + f"... ({len(text)} chars total)"