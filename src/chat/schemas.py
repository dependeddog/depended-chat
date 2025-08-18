from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    CALL = "call"


class MessageCreate(BaseModel):
    user_id: int
    type: MessageType = MessageType.TEXT
    content: str | None = None
    media_url: str | None = None


class MessageRead(BaseModel):
    id: int
    user_id: int
    type: MessageType
    content: str | None = None
    media_url: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True
