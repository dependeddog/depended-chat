from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import models, schemas


async def upsert_firebase_token(
    db: AsyncSession,
    user_id: UUID,
    payload: schemas.FirebaseTokenUpsertRequest,
) -> models.FirebaseDeviceToken:
    now = datetime.now(timezone.utc)
    stmt = select(models.FirebaseDeviceToken).where(models.FirebaseDeviceToken.token == payload.token)
    existing = (await db.execute(stmt)).scalar_one_or_none()

    if existing is not None:
        existing.user_id = user_id
        existing.device_id = payload.device_id
        existing.platform = payload.platform
        existing.is_active = True
        existing.last_error = None
        existing.invalidated_at = None
        existing.updated_at = now
        await db.commit()
        await db.refresh(existing)
        return existing

    if payload.device_id:
        stmt = select(models.FirebaseDeviceToken).where(
            models.FirebaseDeviceToken.user_id == user_id,
            models.FirebaseDeviceToken.device_id == payload.device_id,
        )
        device_existing = (await db.execute(stmt)).scalar_one_or_none()
        if device_existing is not None:
            device_existing.token = payload.token
            device_existing.platform = payload.platform
            device_existing.is_active = True
            device_existing.last_error = None
            device_existing.invalidated_at = None
            device_existing.updated_at = now
            await db.commit()
            await db.refresh(device_existing)
            return device_existing

    token = models.FirebaseDeviceToken(
        user_id=user_id,
        token=payload.token,
        device_id=payload.device_id,
        platform=payload.platform,
        is_active=True,
    )
    db.add(token)
    await db.commit()
    await db.refresh(token)
    return token


async def delete_firebase_token(db: AsyncSession, user_id: UUID, token: str) -> bool:
    stmt = select(models.FirebaseDeviceToken).where(
        models.FirebaseDeviceToken.user_id == user_id,
        models.FirebaseDeviceToken.token == token,
    )
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing is None:
        return False

    await db.delete(existing)
    await db.commit()
    return True


async def get_active_tokens(db: AsyncSession, user_id: UUID) -> list[str]:
    stmt = select(models.FirebaseDeviceToken.token).where(
        models.FirebaseDeviceToken.user_id == user_id,
        models.FirebaseDeviceToken.is_active.is_(True),
    )
    return list((await db.execute(stmt)).scalars().all())


async def invalidate_token(db: AsyncSession, token: str, error_message: str | None = None) -> None:
    stmt = select(models.FirebaseDeviceToken).where(models.FirebaseDeviceToken.token == token)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing is None:
        return

    existing.is_active = False
    existing.last_error = error_message
    existing.invalidated_at = datetime.now(timezone.utc)
    await db.commit()
