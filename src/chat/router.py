from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import dependencies as db_dependencies
from src.core.security import dependencies as security_dependencies
from src.users import models as users_models
from . import schemas, service

router = APIRouter(prefix="/chat", tags=["chat"])

security = HTTPBearer(auto_error=True)


@router.post("/messages", response_model=schemas.MessageRead)
async def send_message(
        message_in: schemas.MessageCreate,
        db: AsyncSession = Depends(db_dependencies.get_db),
        current_user: users_models.User = Depends(security_dependencies.get_current_user),
):
    data = message_in.model_copy(update={"user_id": current_user.id})
    return await service.create_message(db, data)


@router.get("/messages", response_model=list[schemas.MessageRead])
async def get_messages(
        db: AsyncSession = Depends(db_dependencies.get_db),
        # _: users_models.User = Depends(security_dependencies.get_current_user),
        limit: int = 100,
):
    return await service.list_messages(db, limit)


@router.post("/", response_model=schemas.ChatCreate)
async def create_chat(
        chat_in: schemas.ChatCreate,
        creds: HTTPAuthorizationCredentials = Depends(security),
        db: AsyncSession = Depends(db_dependencies.get_db),
):
    current_user: users_models.User = await security_dependencies.get_current_user(creds=creds, db=db)
    data = chat_in.model_copy(update={"user1_id": current_user.id})
    return await service.create_chat(db, data)
