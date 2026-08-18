from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.dialects.mssql import NVARCHAR
from sqlalchemy.sql import func

from app.database.db import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    filepath = Column(String(500), nullable=False)
    content_type = Column(String(100), nullable=False)
    file_size = Column(Integer, nullable=False)

    # sha256 hex digest of the raw file bytes - used to dedupe by CONTENT,
    # not filename. Uploading the same file under a new name will be
    # rejected as a duplicate.
    content_hash = Column(String(64), nullable=False, unique=True, index=True)

    extracted_text = Column(NVARCHAR(None), nullable=True)  # NVARCHAR(MAX)

    # progress tracking for the chunk -> embed -> store pipeline
    total_chunks = Column(Integer, default=0)
    processed_chunks = Column(Integer, default=0)

    # uploaded -> extracting -> embedding -> indexed  (or -> failed at any step)
    status = Column(String(20), default="uploaded")
    created_at = Column(DateTime(timezone=True), server_default=func.now())