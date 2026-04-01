import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.db import dependencies as db_dependencies
from src.core.security import dependencies as security_dependencies
from src.users import models as users_models
from . import constants, schemas, service, ws_router

router = APIRouter(prefix="/chats", tags=["chats"])
logger = logging.getLogger(__name__)


@router.post("/direct", response_model=schemas.DirectChatResponse)
async def create_direct_chat(
	payload: schemas.CreateDirectChatRequest,
	db: AsyncSession = Depends(db_dependencies.get_db),
	current_user: users_models.User = Depends(security_dependencies.get_current_user),
):
	return await service.create_direct_chat(db, current_user.id, payload)


@router.get("", response_model=list[schemas.ChatListItem])
async def get_chats(
	db: AsyncSession = Depends(db_dependencies.get_db),
	current_user: users_models.User = Depends(security_dependencies.get_current_user),
):
	return await service.list_chats(db, current_user.id)


@router.get("/{chat_id}", response_model=schemas.ChatDetailsResponse)
async def get_chat(
	chat_id: UUID,
	db: AsyncSession = Depends(db_dependencies.get_db),
	current_user: users_models.User = Depends(security_dependencies.get_current_user),
):
	return await service.get_chat_details(db, current_user.id, chat_id)


@router.get("/{chat_id}/messages", response_model=schemas.ChatMessagesResponse)
async def get_chat_messages(
	chat_id: UUID,
	limit: int = Query(default=constants.DEFAULT_LIMIT, ge=1, le=constants.MAX_LIMIT),
	offset: int = Query(default=0, ge=0),
	db: AsyncSession = Depends(db_dependencies.get_db),
	current_user: users_models.User = Depends(security_dependencies.get_current_user),
):
	return await service.get_chat_messages(db, current_user.id, chat_id, limit, offset)


@router.post("/{chat_id}/messages", response_model=schemas.MessageRead)
async def send_message(
	chat_id: UUID,
	payload: schemas.MessageCreateRequest,
	db: AsyncSession = Depends(db_dependencies.get_db),
	current_user: users_models.User = Depends(security_dependencies.get_current_user),
):
	message = await service.send_message(db, current_user.id, chat_id, payload)
	logger.info(message)
	await ws_router.broadcast_message_created(chat_id, message)
	return message


@router.patch("/{chat_id}/messages/{message_id}", response_model=schemas.MessageRead)
async def update_message(
	chat_id: UUID,
	message_id: UUID,
	payload: schemas.MessageUpdateRequest,
	db: AsyncSession = Depends(db_dependencies.get_db),
	current_user: users_models.User = Depends(security_dependencies.get_current_user),
):
	message = await service.update_message(db, current_user.id, chat_id, message_id, payload)
	await ws_router.broadcast_message_updated(chat_id, message)
	return message


@router.delete("/{chat_id}/messages/{message_id}", status_code=204)
async def delete_message(
	chat_id: UUID,
	message_id: UUID,
	db: AsyncSession = Depends(db_dependencies.get_db),
	current_user: users_models.User = Depends(security_dependencies.get_current_user),
):
	await service.delete_message(db, current_user.id, chat_id, message_id)
	await ws_router.broadcast_message_deleted(chat_id, message_id)
	return Response(status_code=204)


@router.delete("/{chat_id}", status_code=204)
async def delete_chat(
	chat_id: UUID,
	db: AsyncSession = Depends(db_dependencies.get_db),
	current_user: users_models.User = Depends(security_dependencies.get_current_user),
):
	participant_ids = await service.delete_chat(db, current_user.id, chat_id)
	await ws_router.broadcast_chat_deleted(chat_id, participant_ids)
	return Response(status_code=204)


@router.post("/{chat_id}/read", response_model=schemas.MarkReadResponse)
async def mark_chat_as_read(
	chat_id: UUID,
	db: AsyncSession = Depends(db_dependencies.get_db),
	current_user: users_models.User = Depends(security_dependencies.get_current_user),
):
	response = await service.mark_chat_as_read(db, current_user.id, chat_id)
	await ws_router.broadcast_chat_read(chat_id, current_user.id, response.read_up_to_message_id)
	return response
