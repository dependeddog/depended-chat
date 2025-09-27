from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.broker.rabbitmq import broker

from . import models, schemas, constants


async def create_message(db: AsyncSession, message_in: schemas.MessageCreate) -> models.Message:
    message = models.Message(**message_in.model_dump())
    db.add(message)
    await db.commit()
    await db.refresh(message)
    await broker.publish("chat_messages", schemas.MessageRead.model_validate(message).model_dump_json())
    return message


async def list_messages(db: AsyncSession, limit: int = constants.DEFAULT_LIMIT) -> list[models.Message]:
    result = await db.execute(
        select(models.Message).order_by(models.Message.created_at).limit(limit)
    )
    return result.scalars().all()
