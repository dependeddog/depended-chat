from uuid import UUID

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
			and_(models.Chat.user1_id == chat_in.sender_id, models.Chat.user2_id == chat_in.recipient_id),
			and_(models.Chat.user1_id == chat_in.recipient_id, models.Chat.user2_id == chat_in.sender_id),
		)
	)
	res = await db.execute(stmt)
	existing = res.scalar_one_or_none()
	if existing:
		return existing

	data = chat_in.model_dump()

	chat = models.Chat(
		user1_id=data.sender_id,
		user2_id=data.recipient_id,
	)
	db.add(chat)
	await db.commit()
	await db.refresh(chat)
	return chat


async def list_chats(db: AsyncSession, user_id: UUID, limit: int = constants.DEFAULT_LIMIT) -> list[models.Chat]:
	stmt = select(models.Chat).where(
		or_(
			models.Chat.user1_id == user_id,
			models.Chat.user2_id == user_id
		)
	).order_by(models.Chat.created_at).limit(limit)
	res = await db.execute(stmt)
	return res.scalars().all()
