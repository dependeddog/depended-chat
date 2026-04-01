from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UserCreate(BaseModel):
    username: str
    password: str


class UserRead(BaseModel):
    id: UUID
    username: str

    model_config = ConfigDict(from_attributes=True)


class UserLogin(BaseModel):
    username: str
    password: str


class UserProfileRead(BaseModel):
    id: UUID
    username: str
    bio: str | None
    last_seen_at: datetime | None
    has_avatar: bool
    avatar_url: str | None
    avatar_mime_type: str | None


class UserProfileUpdate(BaseModel):
    bio: str | None = Field(default=None, max_length=1000)


class UserLastSeenRead(BaseModel):
    user_id: UUID
    last_seen_at: datetime | None


class AvatarUploadResponse(BaseModel):
    has_avatar: bool
    avatar_url: str | None
    avatar_mime_type: str | None
