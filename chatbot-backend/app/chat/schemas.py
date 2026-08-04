from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class SourceChunk(BaseModel):
    document_id: int
    filename: str
    chunk_index: int
    distance: Optional[float] = None


class ChatRequest(BaseModel):
    question: str
    top_k: int = 5
    conversation_id: Optional[int] = None  # omit to start a new conversation
    document_id: Optional[int] = None  # omit to search across all documents


class ChatResponse(BaseModel):
    conversation_id: int
    answer: str
    sources: List[SourceChunk]


class MessageResponse(BaseModel):
    id: int
    role: str  # "user" | "assistant"
    content: str
    sources: List[SourceChunk]
    created_at: datetime


class ConversationResponse(BaseModel):
    id: int
    title: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

class ConversationUpdate(BaseModel):
    title: str        