from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class EmailJob:
    id: int
    template_name: str
    status: str
    payload: dict
    error_message: Optional[str] = None
    sent_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
