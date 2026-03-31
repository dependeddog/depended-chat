from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.users import models as users_models, service as users_service
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


async def user_has_chat_access(db: AsyncSession, chat_id: UUID, user_id: UUID) -> bool:
    chat = await db.get(models.Chat, chat_id)
    if chat is None:
        return False
    participant = await _get_participant(db, chat_id, user_id)
    return participant is not None


async def get_chat_participant_ids(db: AsyncSession, chat_id: UUID) -> list[UUID]:
    stmt = select(models.ChatParticipant.user_id).where(models.ChatParticipant.chat_id == chat_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


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
        .where(models.Message.chat_id == chat_id, models.Message.is_deleted.is_(False))
        .order_by(models.Message.created_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


def _build_message_read(
    message: models.Message,
    current_user_id: UUID,
    companion_last_read_at: datetime,
) -> schemas.MessageRead:
    is_own = message.sender_id == current_user_id
    read_by_companion = bool(is_own and message.created_at <= companion_last_read_at)
    return schemas.MessageRead(
        id=message.id,
        chat_id=message.chat_id,
        sender_id=message.sender_id,
        text=message.text,
        created_at=message.created_at,
        is_edited=message.is_edited,
        edited_at=message.edited_at,
        is_own=is_own,
        read_by_companion=read_by_companion,
    )


async def _get_chat_and_participant(
    db: AsyncSession,
    chat_id: UUID,
    current_user_id: UUID,
) -> tuple[models.Chat, models.ChatParticipant]:
    participant = await _get_participant(db, chat_id, current_user_id)
    if participant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

    chat = await db.get(models.Chat, chat_id)
    if chat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    return chat, participant


async def _get_message_in_chat(db: AsyncSession, chat_id: UUID, message_id: UUID) -> models.Message:
    stmt = select(models.Message).where(models.Message.id == message_id, models.Message.chat_id == chat_id)
    result = await db.execute(stmt)
    message = result.scalar_one_or_none()
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    return message


async def _get_companion_last_read_at(db: AsyncSession, chat_id: UUID, current_user_id: UUID) -> datetime:
    stmt = select(models.ChatParticipant.last_read_at).where(
        models.ChatParticipant.chat_id == chat_id,
        models.ChatParticipant.user_id != current_user_id,
    )
    result = await db.execute(stmt)
    companion_last_read_at = result.scalar_one_or_none()
    if companion_last_read_at is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Companion not found")
    return companion_last_read_at


async def _get_unread_count(
    db: AsyncSession,
    chat_id: UUID,
    current_user_id: UUID,
    participant: models.ChatParticipant,
) -> int:
    stmt = select(func.count(models.Message.id)).where(
        models.Message.chat_id == chat_id,
        models.Message.sender_id != current_user_id,
        models.Message.is_deleted.is_(False),
        models.Message.created_at > participant.last_read_at,
    )
    result = await db.execute(stmt)
    return int(result.scalar_one() or 0)


async def get_chat_list_update_payload(
    db: AsyncSession,
    current_user_id: UUID,
    chat_id: UUID,
) -> schemas.ChatListItem:
    chat, participant = await _get_chat_and_participant(db, chat_id, current_user_id)

    companion = await _get_companion(db, chat.id, current_user_id)
    last_message = await _get_last_message(db, chat.id)
    unread_count = await _get_unread_count(db, chat.id, current_user_id, participant)

    companion_last_read_at = await _get_companion_last_read_at(db, chat.id, current_user_id)
    return schemas.ChatListItem(
        id=chat.id,
        type=chat.type,
        companion=schemas.UserShort(id=companion.id, username=companion.username),
        last_message=_build_message_read(last_message, current_user_id, companion_last_read_at) if last_message else None,
        unread_count=unread_count,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
    )


async def create_direct_chat(
    db: AsyncSession,
    current_user_id: UUID,
    request: schemas.CreateDirectChatRequest,
) -> schemas.DirectChatResponse:
    companion = await users_service.get_user_by_username(db, request.username)
    if companion is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if companion.id == current_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot create chat with yourself")

    direct_key = _build_direct_key(current_user_id, companion.id)
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
                models.ChatParticipant(chat_id=chat.id, user_id=companion.id, last_read_at=now),
            ]
        )
        await db.commit()

    return schemas.DirectChatResponse(
        chat_id=chat.id,
        type=chat.type,
        companion=schemas.UserShort(id=companion.id, username=companion.username),
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
        companion_last_read_at = await _get_companion_last_read_at(db, chat.id, current_user_id)
        unread_count = await _get_unread_count(db, chat.id, current_user_id, participant)

        items.append(
            schemas.ChatListItem(
                id=chat.id,
                type=chat.type,
                companion=schemas.UserShort(id=companion.id, username=companion.username),
                last_message=(
                    _build_message_read(last_message, current_user_id, companion_last_read_at)
                    if last_message
                    else None
                ),
                unread_count=unread_count,
                created_at=chat.created_at,
                updated_at=chat.updated_at,
            )
        )

    return items


async def get_chat_details(db: AsyncSession, current_user_id: UUID, chat_id: UUID) -> schemas.ChatDetailsResponse:
    chat, participant = await _get_chat_and_participant(db, chat_id, current_user_id)

    companion = await _get_companion(db, chat.id, current_user_id)
    last_message = await _get_last_message(db, chat.id)
    companion_last_read_at = await _get_companion_last_read_at(db, chat.id, current_user_id)
    unread_count = await _get_unread_count(db, chat.id, current_user_id, participant)

    return schemas.ChatDetailsResponse(
        chat_id=chat.id,
        type=chat.type,
        companion=schemas.UserShort(id=companion.id, username=companion.username),
        last_message=_build_message_read(last_message, current_user_id, companion_last_read_at) if last_message else None,
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
        .where(models.Message.chat_id == chat_id, models.Message.is_deleted.is_(False))
        .order_by(models.Message.created_at.asc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    messages = result.scalars().all()
    companion_last_read_at = await _get_companion_last_read_at(db, chat_id, current_user_id)

    return schemas.ChatMessagesResponse(
        items=[_build_message_read(message, current_user_id, companion_last_read_at) for message in messages],
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

    companion_last_read_at = await _get_companion_last_read_at(db, chat_id, current_user_id)
    return _build_message_read(message, current_user_id, companion_last_read_at)


async def update_message(
    db: AsyncSession,
    current_user_id: UUID,
    chat_id: UUID,
    message_id: UUID,
    payload: schemas.MessageUpdateRequest,
) -> schemas.MessageRead:
    chat, _ = await _get_chat_and_participant(db, chat_id, current_user_id)
    message = await _get_message_in_chat(db, chat_id, message_id)

    if message.sender_id != current_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot edit others messages")
    if message.is_deleted:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message is deleted")

    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message text cannot be empty")

    now = datetime.now(timezone.utc)
    message.text = text
    message.is_edited = True
    message.edited_at = now
    chat.updated_at = now

    await db.commit()
    await db.refresh(message)

    companion_last_read_at = await _get_companion_last_read_at(db, chat_id, current_user_id)
    return _build_message_read(message, current_user_id, companion_last_read_at)


async def delete_message(
    db: AsyncSession,
    current_user_id: UUID,
    chat_id: UUID,
    message_id: UUID,
) -> None:
    chat, _ = await _get_chat_and_participant(db, chat_id, current_user_id)
    message = await _get_message_in_chat(db, chat_id, message_id)

    if message.sender_id != current_user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot delete others messages")

    if message.is_deleted:
        return

    now = datetime.now(timezone.utc)
    message.is_deleted = True
    message.deleted_at = now
    chat.updated_at = now
    await db.commit()


async def delete_chat(db: AsyncSession, current_user_id: UUID, chat_id: UUID) -> list[UUID]:
    _, _ = await _get_chat_and_participant(db, chat_id, current_user_id)
    participant_ids = await get_chat_participant_ids(db, chat_id)

    chat = await db.get(models.Chat, chat_id)
    if chat is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

    await db.delete(chat)
    await db.commit()
    return participant_ids


async def mark_chat_as_read(db: AsyncSession, current_user_id: UUID, chat_id: UUID) -> schemas.MarkReadResponse:
    participant = await _get_participant(db, chat_id, current_user_id)
    if participant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")

    latest_message = await _get_last_message(db, chat_id)
    if latest_message is not None:
        participant.last_read_at = max(participant.last_read_at, latest_message.created_at)
    else:
        participant.last_read_at = datetime.now(timezone.utc)
    await db.commit()

    return schemas.MarkReadResponse(read_up_to_message_id=latest_message.id if latest_message else None)
