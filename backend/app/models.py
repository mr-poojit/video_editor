from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class Job(SQLModel, table=True):
    id: str = Field(primary_key=True)
    status: str = Field(default="queued")   # queued | processing | done | failed
    progress: float = Field(default=0.0)    # 0.0 - 100.0
    input_path: str = Field(default=None)
    output_path: Optional[str] = Field(default=None)
    overlay_metadata: Optional[str] = Field(default=None)  # renamed from 'metadata'
    message: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
