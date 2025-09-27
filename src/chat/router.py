from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import dependencies as db_dependencies
from src.core.security import dependencies as security_dependencies
from src.users import models as users_models
from . import schemas, service

router = APIRouter(prefix="/messages", tags=["messages"])


@router.post("/", response_model=schemas.MessageRead)
async def send_message(
        message_in: schemas.MessageCreate,
        db: AsyncSession = Depends(db_dependencies.get_db),
        current_user: users_models.User = Depends(security_dependencies.get_current_user),
):
    data = message_in.model_copy(update={"user_id": current_user.id})
    return await service.create_message(db, data)


@router.get("/", response_model=list[schemas.MessageRead])
async def get_messages(
        db: AsyncSession = Depends(db_dependencies.get_db),
        # _: users_models.User = Depends(security_dependencies.get_current_user),
        limit: int = 100,
):
    return await service.list_messages(db, limit)
