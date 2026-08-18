from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class SourceChunk(BaseModel):
    document_id: int
    filename: str
    chunk_index: int
    distance: Optional[float] = None


class Action(BaseModel):
    type: str  # "navigate" for now, extensible later
    path: str
    label: str


class ChatRequest(BaseModel):
    question: str
    conversation_id: Optional[int] = None
    document_id: Optional[int] = None
    # The frontend's cached user object (localStorage "user") - name,
    # erpid, department, role, manager, whatever fields you already have.
    user_context: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    conversation_id: int
    answer: str
    sources: List[SourceChunk] = []
    actions: List[Action] = []


class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    sources: List[SourceChunk] = []
    created_at: datetime


class ConversationResponse(BaseModel):
    id: int
    title: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True