from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class SourceChunk(BaseModel):
    """A passage from a trained document that an answer was drawn from."""

    document_id: Optional[int] = None
    filename: Optional[str] = None
    chunk_index: Optional[int] = None
    page_number: Optional[int] = None
    distance: Optional[float] = None


class Action(BaseModel):
    type: str  # "navigate"
    path: str
    label: str


class Column(BaseModel):
    key: str
    label: str


class DataBlock(BaseModel):
    """Rows the widget renders as a table rather than as prose.

    Numbers a person may act on belong in a table they can scan, not buried in
    a paragraph — and keeping them out of the prose also keeps the language
    model from restating them inexactly.
    """

    title: str
    columns: List[Column]
    rows: List[Dict[str, Any]]
    summary: Dict[str, Any] = {}
    note: Optional[str] = None


class ReportOffer(BaseModel):
    """Everything the frontend needs to ask for the file it just saw offered."""

    subject: str                     # leave | attendance | official_work
    erp_id: int
    start: date
    end: date
    label: str                       # "August 2026", "the last 7 days"
    employee_name: Optional[str] = None
    formats: List[str] = ["excel", "pdf"]
    # Set when the question already named one ("...in excel"), so the widget
    # can start that download instead of asking again.
    preferred_format: Optional[str] = None


class ChatRequest(BaseModel):
    question: str
    conversation_id: Optional[int] = None
    # Scopes retrieval to one trained document; omitted means search them all.
    document_id: Optional[int] = None


class ChatResponse(BaseModel):
    conversation_id: int
    answer: str
    intent: Optional[str] = None
    sources: List[SourceChunk] = []
    actions: List[Action] = []
    data: Optional[DataBlock] = None
    report: Optional[ReportOffer] = None


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


class ReportRequest(BaseModel):
    subject: str                     # leave | attendance | official_work
    start: date
    end: date
    report_format: str               # excel | pdf
    # Only an administrator may name someone else; anyone else is answered
    # about themselves whatever they send.
    erp_id: Optional[int] = None
