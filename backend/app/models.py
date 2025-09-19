# backend/app/models.py
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class Job(SQLModel, table=True):
    id: str = Field(primary_key=True, nullable=False)
    status: str = Field(default="queued", nullable=False)   # queued | processing | done | failed
    progress: float = Field(default=0.0, nullable=False)    # 0.0 - 100.0
    input_path: str = Field(nullable=False)
    output_path: Optional[str] = Field(default=None)
    overlay_metadata: Optional[str] = Field(default="[]")  # store JSON string
    message: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
