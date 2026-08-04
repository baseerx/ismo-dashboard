from datetime import datetime

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: int
    filename: str
    content_type: str
    file_size: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    id: int
    filename: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class DocumentStatusResponse(BaseModel):
    id: int
    filename: str
    status: str              # uploaded | extracting | embedding | indexed | failed
    total_chunks: int
    processed_chunks: int
    progress_percent: float  # 0-100

    class Config:
        from_attributes = True