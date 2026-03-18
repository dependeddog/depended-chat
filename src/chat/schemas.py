from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChatType(str, Enum):
    DIRECT = "direct"


class UserShort(BaseModel):
    id: UUID
    username: str


class CreateDirectChatRequest(BaseModel):
    username: str = Field(min_length=1, max_length=255)


class MessageCreateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    chat_id: UUID
    sender_id: UUID
    text: str
    created_at: datetime
    is_own: bool
    read_by_companion: bool


class ChatListItem(BaseModel):
    id: UUID
    type: ChatType
    companion: UserShort
    last_message: MessageRead | None = None
    unread_count: int
    created_at: datetime
    updated_at: datetime


class DirectChatResponse(BaseModel):
    chat_id: UUID
    type: ChatType
    companion: UserShort


class ChatDetailsResponse(BaseModel):
    chat_id: UUID
    type: ChatType
    companion: UserShort
    last_message: MessageRead | None = None
    unread_count: int


class ChatMessagesResponse(BaseModel):
    items: list[MessageRead]
    limit: int
    offset: int


class MarkReadResponse(BaseModel):
    status: str = "ok"
    read_up_to_message_id: UUID | None = None
