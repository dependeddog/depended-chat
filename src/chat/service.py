from sqlalchemy import select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.broker.rabbitmq import broker
from . import constants, models, schemas


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


async def create_chat(db: AsyncSession, chat_in: schemas.ChatCreate) -> models.Chat:
    stmt = select(models.Chat).where(
        or_(
            and_(models.Chat.user1_id == chat_in.user1_id, models.Chat.user2_id == chat_in.user2_id),
            and_(models.Chat.user1_id == chat_in.user2_id, models.Chat.user2_id == chat_in.user1_id),
        )
    )
    res = await db.execute(stmt)
    existing = res.scalar_one_or_none()
    if existing:
        return existing

    chat = models.Chat(chat_in.model_dump())
    db.add(chat)
    await db.commit()
    await db.refresh(chat)
    return chat
