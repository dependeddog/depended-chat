from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import dependencies as db_dependencies
from src.core.security import dependencies as security_dependencies
from src.users import models as users_models

from . import schemas, service

router = APIRouter(prefix="/devices", tags=["devices"])


@router.post("/firebase-token", response_model=schemas.FirebaseTokenResponse)
async def upsert_firebase_token(
    payload: schemas.FirebaseTokenUpsertRequest,
    db: AsyncSession = Depends(db_dependencies.get_db),
    current_user: users_models.User = Depends(security_dependencies.get_current_user),
):
    await service.upsert_firebase_token(db, current_user.id, payload)
    return schemas.FirebaseTokenResponse()


@router.delete("/firebase-token", response_model=schemas.FirebaseTokenResponse)
async def delete_firebase_token(
    payload: schemas.FirebaseTokenDeleteRequest,
    db: AsyncSession = Depends(db_dependencies.get_db),
    current_user: users_models.User = Depends(security_dependencies.get_current_user),
):
    await service.delete_firebase_token(db, current_user.id, payload.token)
    return schemas.FirebaseTokenResponse()
