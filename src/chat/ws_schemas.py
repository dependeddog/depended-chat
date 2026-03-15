from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from src.chat import schemas


class WebSocketEnvelope(BaseModel):
    event: str
    data: dict


class ConnectionReadyData(BaseModel):
    scope: str
    chat_id: UUID | None = None


class MessageCreatedData(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    chat_id: UUID
    sender_id: UUID
    text: str
    created_at: datetime


class ChatReadData(BaseModel):
    chat_id: UUID
    user_id: UUID
    read_up_to_message_id: UUID | None = None


class ChatListUpdatedData(BaseModel):
    chat_id: UUID
    unread_count: int
    last_message: schemas.MessageRead | None = None


class TypingData(BaseModel):
    chat_id: UUID
    user_id: UUID
