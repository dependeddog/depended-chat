from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user

from . import models, schemas, service
from .dependencies import get_db

router = APIRouter(prefix="/messages", tags=["messages"])


@router.post("/", response_model=schemas.MessageRead)
async def send_message(
    message_in: schemas.MessageCreate,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    message_in = message_in.model_copy(update={"user_id": current_user.id})
    return await service.create_message(db, message_in)


@router.get("/", response_model=list[schemas.MessageRead])
async def get_messages(
    db: AsyncSession = Depends(get_db),
    limit: int = 100,
    current_user: models.User = Depends(get_current_user),
):
    return await service.list_messages(db, limit)
