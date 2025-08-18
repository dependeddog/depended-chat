from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from . import schemas, service
from .dependencies import get_db

router = APIRouter(prefix="/messages", tags=["messages"])


@router.post("/", response_model=schemas.MessageRead)
async def send_message(
    message_in: schemas.MessageCreate, db: AsyncSession = Depends(get_db)
):
    return await service.create_message(db, message_in)


@router.get("/", response_model=list[schemas.MessageRead])
async def get_messages(
    db: AsyncSession = Depends(get_db), limit: int = 100
):
    return await service.list_messages(db, limit)
