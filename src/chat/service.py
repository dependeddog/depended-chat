from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.users import models as users_models
from . import constants, models, schemas


def _build_direct_key(user_1: UUID, user_2: UUID) -> str:
    left, right = sorted([str(user_1), str(user_2)])
    return f"{left}:{right}"


async def _get_participant(
    db: AsyncSession,
    chat_id: UUID,
    user_id: UUID,
) -> models.ChatParticipant | None:
    stmt = select(models.ChatParticipant).where(
        models.ChatParticipant.chat_id == chat_id,
        models.ChatParticipant.user_id == user_id,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _get_companion(
    db: AsyncSession,
    chat_id: UUID,
    user_id: UUID,
) -> users_models.User:
    stmt = (
        select(users_models.User)
        .join(models.ChatParticipant, models.ChatParticipant.user_id == users_models.User.id)
        .where(
            models.ChatParticipant.chat_id == chat_id,
            models.ChatParticipant.user_id != user_id,
        )
    )
    result = await db.execute(stmt)
    companion = result.scalar_one_or_none()
    if companion is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Companion not found")
    return companion


async def _get_last_message(db: AsyncSession, chat_id: UUID) -> models.Message | None:
    stmt = (
        select(models.Message)
        .where(models.Message.chat_id == chat_id)
        .order_by(models.Message.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def _get_unread_count(
    db: AsyncSession,
    chat_id: UUID,
    current_user_id: UUID,
    participant: models.ChatParticipant,
) -> int:
    stmt = select(func.count(models.Message.id)).where(
        models.Message.chat_id == chat_id,
        models.Message.sender_id != current_user_id,
        models.Message.created_at > participant.last_read_at,
    )
    result = await db.execute(stmt)
    return int(result.scalar_one() or 0)


async def create_direct_chat(
    db: AsyncSession,
    current_user_id: UUID,
    request: schemas.CreateDirectChatRequest,
) -> schemas.DirectChatResponse:
    if request.user_id == current_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot create chat with yourself")

    user = await db.get(users_models.User, request.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    direct_key = _build_direct_key(current_user_id, request.user_id)
    stmt = select(models.Chat).where(models.Chat.direct_key == direct_key)
    result = await db.execute(stmt)
    chat = result.scalar_one_or_none()

    if chat is None:
        now = datetime.now(timezone.utc)
        chat = models.Chat(type=models.ChatType.DIRECT, direct_key=direct_key, created_at=now, updated_at=now)
        db.add(chat)
        await db.flush()
        db.add_all(
            [
                models.ChatParticipant(chat_id=chat.id, user_id=current_user_id, last_read_at=now),
                models.ChatParticipant(chat_id=chat.id, user_id=request.user_id, last_read_at=now),
            ]
        )
        await db.commit()

    return schemas.DirectChatResponse(
        chat_id=chat.id,
        type=chat.type,
        companion=schemas.UserShort(id=user.id, username=user.username),
    )


async def list_chats(db: AsyncSession, current_user_id: UUID) -> list[schemas.ChatListItem]:
    stmt = (
        select(models.ChatParticipant, models.Chat)
        .join(models.Chat, models.Chat.id == models.ChatParticipant.chat_id)
        .where(models.ChatParticipant.user_id == current_user_id)
        .order_by(models.Chat.updated_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.all()

    items: list[schemas.ChatListItem] = []
    for participant, chat in rows:
        companion = await _get_companion(db, chat.id, current_user_id)
        last_message = await _get_last_message(db, chat.id)
        unread_count = await _get_unread_count(db, chat.id, current_user_id, participant)

        items.append(
            schemas.ChatListItem(
                id=chat.id,
                type=chat.type,
                companion=schemas.UserShort(id=companion.id, username=companion.username),
                last_message=schemas.MessageRead.model_validate(last_message) if last_message else None,
                unread_count=unread_count,
                created_at=chat.created_at,
                updated_at=chat.updated_at,
            )
        )

    return items


async def get_chat_details(db: AsyncSession, current_user_id: UUID, chat_id: UUID) -> schemas.ChatDetailsResponse:
    participant = await _get_participant(db, chat_id, current_user_id)
    if participant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

    chat = await db.get(models.Chat, chat_id)
    if chat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

    companion = await _get_companion(db, chat.id, current_user_id)
    last_message = await _get_last_message(db, chat.id)
    unread_count = await _get_unread_count(db, chat.id, current_user_id, participant)

    return schemas.ChatDetailsResponse(
        chat_id=chat.id,
        type=chat.type,
        companion=schemas.UserShort(id=companion.id, username=companion.username),
        last_message=schemas.MessageRead.model_validate(last_message) if last_message else None,
        unread_count=unread_count,
    )


async def get_chat_messages(
    db: AsyncSession,
    current_user_id: UUID,
    chat_id: UUID,
    limit: int,
    offset: int,
) -> schemas.ChatMessagesResponse:
    participant = await _get_participant(db, chat_id, current_user_id)
    if participant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

    limit = max(1, min(limit, constants.MAX_LIMIT))
    offset = max(0, offset)

    stmt = (
        select(models.Message)
        .where(models.Message.chat_id == chat_id)
        .order_by(models.Message.created_at.asc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    messages = result.scalars().all()

    return schemas.ChatMessagesResponse(
        items=[schemas.MessageRead.model_validate(message) for message in messages],
        limit=limit,
        offset=offset,
    )


async def send_message(
    db: AsyncSession,
    current_user_id: UUID,
    chat_id: UUID,
    payload: schemas.MessageCreateRequest,
) -> schemas.MessageRead:
    participant = await _get_participant(db, chat_id, current_user_id)
    if participant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message text cannot be empty")

    now = datetime.now(timezone.utc)
    message = models.Message(chat_id=chat_id, sender_id=current_user_id, text=text, created_at=now)
    db.add(message)

    chat = await db.get(models.Chat, chat_id)
    if chat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    chat.updated_at = now

    await db.commit()
    await db.refresh(message)

    return schemas.MessageRead.model_validate(message)


async def mark_chat_as_read(db: AsyncSession, current_user_id: UUID, chat_id: UUID) -> schemas.MarkReadResponse:
    participant = await _get_participant(db, chat_id, current_user_id)
    if participant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

    participant.last_read_at = datetime.now(timezone.utc)
    await db.commit()

    return schemas.MarkReadResponse()
