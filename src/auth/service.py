from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, cast
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.users import models as users_models, service as users_service
from . import exceptions, models, security, utils


async def authenticate_user(
    db: AsyncSession, username: str, password: str
) -> Optional[users_models.User]:
    user = await users_service.get_user_by_username(db, username)
    if not user or not utils.verify_password(password, cast(str, user.password)):
        raise exceptions.InvalidCredentials()
    return user


async def persist_refresh(
        db: AsyncSession,
        token: str,
        user_agent: Optional[str] = None,
        ip: Optional[str] = None,
) -> models.RefreshToken:
    """
    Сохраняет refresh-токен в БД (по факту его jti, exp и SHA256).
    """
    payload = utils.decode_token(token)
    if payload.get("type") != "refresh":
        raise exceptions.NotRefreshToken()

    jti: str = payload["jti"]
    user_id: int = int(payload["id"])
    exp_ts: int = payload["exp"]

    rt = models.RefreshToken(
        id=str(uuid4()),
        user_id=user_id,
        jti=jti,
        token_sha256=security.sha256_hex(token),
        created_at=security.now_utc(),
        expires_at=datetime.fromtimestamp(exp_ts, tz=timezone.utc),
        user_agent=user_agent,
        ip=ip,
    )
    db.add(rt)
    await db.commit()
    return rt


async def ensure_refresh_valid(db: AsyncSession, token: str) -> None:
    """
    Проверка: существует, не просрочен, не отозван и хэш совпадает.
    """
    payload = utils.decode_token(token)
    if payload.get("type") != "refresh":
        raise PermissionError("Invalid token type")
    jti = payload["jti"]

    stmt = select(models.RefreshToken).where(models.RefreshToken.jti == jti)
    res = await db.execute(stmt)
    rt = res.scalar_one_or_none()

    if rt is None:
        raise exceptions.RefreshNotFound()
    if rt.revoked_at is not None:
        raise exceptions.RefreshRevoked()
    if rt.expires_at <= security.now_utc():
        raise exceptions.RefreshExpired()
    if rt.token_sha256 != security.sha256_hex(token):
        raise exceptions.RefreshMismatch()


async def rotate_refresh(db: AsyncSession, token: str) -> str:
    """
    Ротация refresh: помечаем старый как использованный/отозванный и создаём новый.
    Возвращаем НОВЫЙ refresh-токен (строкой).
    """
    payload = utils.decode_token(token)
    if payload.get("type") != "refresh":
        raise exceptions.NotRefreshToken()
    jti = payload["jti"]

    stmt = (select(models.RefreshToken)
            .where(models.RefreshToken.jti == jti)
            .with_for_update())
    res = await db.execute(stmt)
    rt = res.scalar_one_or_none()
    if rt is None:
        raise exceptions.RefreshNotFound()

    if rt.revoked_at is not None or rt.expires_at <= security.now_utc():
        raise exceptions.RefreshInactive()

    # Помечаем текущий refresh как использованный и отозванный
    rt.used_at = security.now_utc()
    rt.revoked_at = security.now_utc()
    await db.flush()

    # Генерируем новый refresh для того же пользователя
    new_refresh, _ttl = utils.create_refresh_token({"id": payload["id"], "username": payload["username"]})

    # Сохраняем новый refresh
    new_payload = utils.decode_token(new_refresh)
    new_rt = models.RefreshToken(
        id=str(uuid4()),
        user_id=int(new_payload["id"]),
        jti=new_payload["jti"],
        token_sha256=security.sha256_hex(new_refresh),
        created_at=security.now_utc(),
        expires_at=datetime.fromtimestamp(new_payload["exp"], tz=timezone.utc),
        rotated_from_id=rt.id,
        user_agent=rt.user_agent,
        ip=rt.ip,
    )
    db.add(new_rt)
    await db.commit()

    return new_refresh


async def revoke_refresh_by_raw(db: AsyncSession, raw_token: str) -> None:
    """
    Идемпотентно отзывает refresh по "сырому" токену.
    Ничего не декодируем; ищем запись по хэш-сумме токена.
    """
    token_hash = security.sha256_hex(raw_token)
    stmt = (select(models.RefreshToken)
            .where(models.RefreshToken.token_sha256 == token_hash)
            .with_for_update())
    res = await db.execute(stmt)
    rt = res.scalar_one_or_none()
    if rt is None:
        return  # ничего делать не надо — уже "вышли"
    if rt.revoked_at is None:
        rt.revoked_at = security.now_utc()
        await db.commit()
