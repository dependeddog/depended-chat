from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    CALL = "call"


class MessageCreate(BaseModel):
    user_id: UUID
    chat_id: UUID
    type: MessageType = MessageType.TEXT
    content: str | None = None
    media_url: str | None = None


class MessageRead(BaseModel):
    id: UUID
    user_id: UUID
    type: MessageType
    content: str | None = None
    media_url: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class ChatCreate(BaseModel):
    user1_id: Optional[UUID] = None
    user2_id: UUID


class ChatRead(BaseModel):
    id: UUID
    user1_id: UUID
    user2_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
