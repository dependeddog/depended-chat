from fastapi import APIRouter, Body, Depends, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db.dependencies import get_db
from src.users import schemas as users_schemas, service as users_service
from . import exceptions, schemas, service, utils

router = APIRouter(prefix="/auth", tags=["auth"])

access_bearer = HTTPBearer(auto_error=True)


@router.post("/register", response_model=users_schemas.UserRead)
async def register(user_in: users_schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    """Регистрация нового пользователя."""
    existing = await users_service.get_user_by_username(db, user_in.username)
    if existing:
        raise exceptions.UsernameAlreadyRegistered()
    return await users_service.create_user(db, user_in)


@router.post("/login", response_model=schemas.TokenPair)
async def login(user_in: users_schemas.UserLogin, request: Request, db: AsyncSession = Depends(get_db)):
    """
    Логин: выдаём access и refresh, refresh сохраняем в БД.
    """
    user = await service.authenticate_user(db, user_in.username, user_in.password)
    access, access_ttl = utils.create_access_token({"id": str(user.id), "username": user.username})
    refresh, _ = utils.create_refresh_token({"id": str(user.id), "username": user.username})

    # Сохраняем refresh в БД с контекстом
    ua = request.headers.get("user-agent")
    ip = request.client.host if request.client else None
    await service.persist_refresh(db, token=refresh, user_agent=ua, ip=ip)

    return schemas.TokenPair(
        access_token=access,
        access_expires_in=access_ttl,
        refresh_token=refresh,
    )


@router.post("/refresh", response_model=schemas.TokenPair)
async def refresh_token(
        _: Request,
        refresh_token_param: str = Body(..., embed=True, min_length=1),
        db: AsyncSession = Depends(get_db),
):
    """
    Обновляем access по-валидному refresh + РОТИРУЕМ refresh.
    Возвращаем НОВЫЙ refresh, чтобы клиент не потерял «нить».
    """
    payload = utils.decode_token(refresh_token_param)
    if payload.get("type") != "refresh":
        raise exceptions.RefreshExpected()

    await service.ensure_refresh_valid(db, refresh_token_param)

    # Ротация refresh -> получаем НОВЫЙ refresh и сохраняем его контекстом текущего запроса
    new_refresh = await service.rotate_refresh(db, refresh_token_param)

    # Создаём новый access
    access, access_ttl = utils.create_access_token({"id": str(payload["id"]), "username": payload["username"]})

    return schemas.TokenPair(
        access_token=access,
        access_expires_in=access_ttl,
        refresh_token=new_refresh,
    )


@router.post("/logout", status_code=204)
async def logout(creds: HTTPAuthorizationCredentials = Depends(access_bearer),
				 db: AsyncSession = Depends(get_db), ):
    """
    Логаут: идемпотентный отзыв текущего refresh.
    """
    await service.revoke_refresh_by_raw(db, creds.credentials)
    return Response(status_code=204)
