import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.identity import Identity, current_identity
from app.chat.schemas import (
    ChatRequest,
    ChatResponse,
    ConversationResponse,
    MessageResponse,
)
from app.chat.service import answer_question
from app.database.db import get_db
from app.models.chat import Conversation, Message

router = APIRouter(prefix="/chat", tags=["chat"])


def _own_conversation(db: Session, conversation_id: int, identity: Identity) -> Conversation:
    """A conversation belonging to the caller, or 404.

    404 rather than 403 on someone else's thread: a "forbidden" reply confirms
    the thread exists, which is itself something the caller should not learn.
    """
    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.owner_erp_id == identity.erp_id,
        )
        .first()
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    identity: Identity = Depends(current_identity),
):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="question cannot be empty")

    return await answer_question(
        db,
        request.question.strip(),
        identity=identity,
        conversation_id=request.conversation_id,
        document_id=request.document_id,
    )


@router.get("/conversations", response_model=List[ConversationResponse])
def list_conversations(
    db: Session = Depends(get_db),
    identity: Identity = Depends(current_identity),
):
    return (
        db.query(Conversation)
        .filter(Conversation.owner_erp_id == identity.erp_id)
        .order_by(Conversation.created_at.desc())
        .limit(50)
        .all()
    )


@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageResponse])
def get_conversation_messages(
    conversation_id: int,
    db: Session = Depends(get_db),
    identity: Identity = Depends(current_identity),
):
    conversation = _own_conversation(db, conversation_id, identity)

    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.asc(), Message.id.asc())
        .all()
    )

    return [
        MessageResponse(
            id=message.id,
            role=message.role,
            content=message.content,
            sources=json.loads(message.sources_json) if message.sources_json else [],
            created_at=message.created_at,
        )
        for message in messages
    ]


@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    identity: Identity = Depends(current_identity),
):
    conversation = _own_conversation(db, conversation_id, identity)
    db.delete(conversation)
    db.commit()
    return {"detail": "Conversation deleted"}
