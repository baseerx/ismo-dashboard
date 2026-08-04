import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.chat.schemas import (
    ChatRequest,
    ChatResponse,
    ConversationResponse,
    ConversationUpdate,
    MessageResponse,
)
from app.chat.service import answer_question
from app.database.db import get_db
from app.models.chat import Conversation, Message
from app.services.llm import generate_reply 

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/", response_model=ChatResponse)
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="question cannot be empty")

    return answer_question(
        db,
        request.question,
        top_k=request.top_k,
        conversation_id=request.conversation_id,
        document_id=request.document_id,
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



@router.patch("/conversations/{conversation_id}", response_model=ConversationResponse)
def rename_conversation(
    conversation_id: int, payload: ConversationUpdate, db: Session = Depends(get_db)
):
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conversation.title = payload.title.strip()
    db.commit()
    db.refresh(conversation)
    return conversation


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: int, db: Session = Depends(get_db)):
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    db.delete(conversation)  # cascades to messages via the ORM relationship
    db.commit()


@router.post("/conversations/{conversation_id}/generate-title", response_model=ConversationResponse)
def generate_title(conversation_id: int, db: Session = Depends(get_db)):
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .limit(6)
        .all()
    )
    if not messages:
        return conversation

    convo_text = "\n".join(f"{m.role}: {m.content}" for m in messages)
    prompt = (
        "Write a short 3-6 word title summarizing this conversation. "
        "No quotes, no trailing punctuation.\n\n" + convo_text
    )
    title = generate_reply([{"role": "user", "content": prompt}]).strip().strip('"')[:60]

    conversation.title = title
    db.commit()
    db.refresh(conversation)
    return conversation