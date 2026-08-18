from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.mssql import NVARCHAR
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.db import Base


class Conversation(Base):
    """One chat thread, owned by the employee who started it.

    `owner_erp_id` is what stops a conversation being readable by anyone who
    guesses its id: every read is filtered by the ERP id in the caller's
    verified token. Chat threads quote leave and attendance figures, so they are
    as private as the records themselves.
    """

    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    owner_erp_id = Column(Integer, nullable=True, index=True)
    title = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    messages = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)
    role = Column(String(20), nullable=False)  # "user" | "assistant"
    content = Column(NVARCHAR(None), nullable=False)  # NVARCHAR(MAX)
    sources_json = Column(NVARCHAR(None), nullable=True)  # JSON-serialised list
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    conversation = relationship("Conversation", back_populates="messages")
