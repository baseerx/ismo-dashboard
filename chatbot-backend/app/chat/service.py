import json
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.models.chat import Conversation, Message
from app.rag.prompt import build_messages
from app.rag.retriever import retrieve_top_chunks
from app.services.llm import generate_reply


def _get_or_create_conversation(
    db: Session, conversation_id: Optional[int]
) -> Conversation:
    if conversation_id:
        conversation = (
            db.query(Conversation).filter(Conversation.id == conversation_id).first()
        )
        if conversation:
            return conversation

    conversation = Conversation()
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation


def answer_question(
    db: Session,
    question: str,
    top_k: int = 5,
    conversation_id: Optional[int] = None,
    document_id: Optional[int] = None,
) -> Dict:
    conversation = _get_or_create_conversation(db, conversation_id)

    # save the user's question first, regardless of what happens next
    db.add(Message(conversation_id=conversation.id, role="user", content=question))
    db.commit()

    chunks = retrieve_top_chunks(question, top_k=top_k, document_id=document_id)

    if not chunks:
        answer = (
            "I couldn't find anything relevant in the uploaded documents "
            "to answer that."
        )
        sources = []
    else:
        messages = build_messages(question, chunks)
        answer = generate_reply(messages)
        sources = [
            {
                "document_id": c["document_id"],
                "filename": c["filename"],
                "chunk_index": c["chunk_index"],
                "distance": c["distance"],
            }
            for c in chunks
        ]

    db.add(
        Message(
            conversation_id=conversation.id,
            role="assistant",
            content=answer,
            sources_json=json.dumps(sources),
        )
    )
    db.commit()

    return {
        "conversation_id": conversation.id,
        "answer": answer,
        "sources": sources,
    }