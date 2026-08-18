import json
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

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


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(default=None),
):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="question cannot be empty")

    return await answer_question(
        db,
        request.question,
        conversation_id=request.conversation_id,
        user_context=request.user_context,
        auth_header=authorization,
    )


@router.get("/conversations", response_model=List[ConversationResponse])
def list_conversations(db: Session = Depends(get_db)):
    return db.query(Conversation).order_by(Conversation.created_at.desc()).all()


@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageResponse])
def get_conversation_messages(conversation_id: int, db: Session = Depends(get_db)):
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .all()
    )

    return [
        MessageResponse(
            id=m.id,
            role=m.role,
            content=m.content,
            sources=json.loads(m.sources_json) if m.sources_json else [],
            created_at=m.created_at,
        )
        for m in messages
    ]