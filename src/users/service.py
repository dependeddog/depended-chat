from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import utils as auth_utils
from . import models, schemas

LAST_SEEN_THROTTLE_SECONDS = 30

def _as_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


async def get_user_by_username(db: AsyncSession, username: str) -> Optional[models.User]:
    result = await db.execute(select(models.User).where(models.User.username == username))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> Optional[models.User]:
    result = await db.execute(select(models.User).where(models.User.id == UUID(str(user_id))))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, user_in: schemas.UserCreate) -> models.User:
    user = models.User(
        username=user_in.username,
        password=auth_utils.get_password_hash(user_in.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def build_avatar_url(user_id: UUID) -> str:
    return f"/users/{user_id}/avatar"


def serialize_profile(user: models.User) -> schemas.UserProfileRead:
    has_avatar = user.avatar is not None and user.avatar_mime_type is not None
    return schemas.UserProfileRead(
        id=user.id,
        username=user.username,
        bio=user.bio,
        last_seen_at=user.last_seen_at,
        has_avatar=has_avatar,
        avatar_url=build_avatar_url(user.id) if has_avatar else None,
        avatar_mime_type=user.avatar_mime_type if has_avatar else None,
    )


async def update_bio(db: AsyncSession, user: models.User, bio: str | None) -> models.User:
    normalized_bio = bio.strip() if isinstance(bio, str) else None
    user.bio = normalized_bio or None
    await db.commit()
    await db.refresh(user)
    return user


async def save_avatar(db: AsyncSession, user: models.User, avatar: bytes, mime_type: str) -> models.User:
    user.avatar = avatar
    user.avatar_mime_type = mime_type
    await db.commit()
    await db.refresh(user)
    return user


async def remove_avatar(db: AsyncSession, user: models.User) -> models.User:
    user.avatar = None
    user.avatar_mime_type = None
    await db.commit()
    await db.refresh(user)
    return user


async def update_last_seen(
    db: AsyncSession,
    user: models.User,
    *,
    min_interval_seconds: int = LAST_SEEN_THROTTLE_SECONDS,
    force: bool = False,
) -> datetime:
    now = datetime.now(timezone.utc)
    if (
        force
        or user.last_seen_at is None
        or (_as_utc(user.last_seen_at) <= now - timedelta(seconds=min_interval_seconds))
    ):
        user.last_seen_at = now
        await db.commit()
        await db.refresh(user)
    return user.last_seen_at or now
