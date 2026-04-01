from __future__ import annotations

from logging import Logger
from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError

from src.auth import ws_auth
from src.devices import service as devices_service
from src.database import SessionLocal
from src.notifications.firebase_service import FirebasePushPayload, firebase_push_service
from src.logger import configure_logs
from . import service
from .ws_manager import ws_manager
from .ws_schemas import (
	ChatDeletedData,
	ChatReadData,
	ConnectionReadyData,
	MessageCreatedData,
	MessageDeletedData,
	MessageUpdatedData,
	TypingData,
	WebSocketEnvelope,
)

router = APIRouter(tags=["chat-websocket"])
logger: Logger = configure_logs(__name__)


def _event_payload(event: str, data: dict) -> dict:
	return WebSocketEnvelope(event=event, data=data).model_dump(mode="json")


@router.websocket("/ws/events")
async def websocket_user_events(websocket: WebSocket) -> None:
	try:
		current_user = await ws_auth.get_current_user_ws(websocket)
	except ws_auth.WebSocketAuthError:
		return

	await ws_manager.connect_user(current_user.id, websocket)
	await websocket.send_json(
		_event_payload(
			"connection.ready",
			ConnectionReadyData(scope="events").model_dump(mode="json"),
		)
	)

	try:
		while True:
			await websocket.receive_text()
	except WebSocketDisconnect:
		pass
	finally:
		await ws_manager.disconnect_user(current_user.id, websocket)


@router.websocket("/ws/chats/{chat_id}")
async def websocket_chat_events(websocket: WebSocket, chat_id: UUID) -> None:
	try:
		current_user = await ws_auth.get_current_user_ws(websocket)
	except ws_auth.WebSocketAuthError:
		return

	async with SessionLocal() as db:
		has_access = await service.user_has_chat_access(db, chat_id, current_user.id)

	if not has_access:
		await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
		return

	await ws_manager.connect_chat(chat_id, current_user.id, websocket)
	await websocket.send_json(
		_event_payload(
			"connection.ready",
			ConnectionReadyData(scope="chat", chat_id=chat_id).model_dump(mode="json"),
		)
	)

	try:
		while True:
			raw_payload = await websocket.receive_json()
			try:
				payload = WebSocketEnvelope.model_validate(raw_payload)
			except ValidationError:
				await websocket.send_json(_event_payload("error", {"detail": "Invalid payload"}))
				continue

			if payload.event == "typing.start":
				await ws_manager.broadcast_to_chat(
					chat_id,
					_event_payload(
						"typing.started",
						TypingData(chat_id=chat_id, user_id=current_user.id).model_dump(mode="json"),
					),
				)
				continue

			if payload.event == "typing.stop":
				await ws_manager.broadcast_to_chat(
					chat_id,
					_event_payload(
						"typing.stopped",
						TypingData(chat_id=chat_id, user_id=current_user.id).model_dump(mode="json"),
					),
				)
				continue

			await websocket.send_json(_event_payload("error", {"detail": "Unsupported event"}))
	except WebSocketDisconnect:
		pass
	finally:
		await ws_manager.disconnect_chat(chat_id, websocket)


async def broadcast_message_created(chat_id: UUID, message) -> None:
	message_payload = MessageCreatedData(
		id=message.id,
		chat_id=message.chat_id,
		sender_id=message.sender_id,
		text=message.text,
		created_at=message.created_at,
	).model_dump(mode="json")

	await ws_manager.broadcast_to_chat(
		chat_id,
		_event_payload("message.created", message_payload),
	)

	async with SessionLocal() as db:
		participant_ids = await service.get_chat_participant_ids(db, chat_id)
		sender = await service.get_user_short_by_id(db, message.sender_id)
		for participant_id in participant_ids:
			if participant_id != message.sender_id:
				is_in_chat = await ws_manager.is_user_active_in_chat(participant_id, chat_id)
				if not is_in_chat:
					tokens = await devices_service.get_active_tokens(db, participant_id)
					if tokens:
						logger.info("service %s", message)
						payload = FirebasePushPayload(
							title=sender.username,
							body=message.text.strip() if message.text.strip() else "Новое сообщение",
							data={
								"type": "new_message",
								"chat_id": str(message.chat_id),
								"message_id": str(message.id),
								"sender_id": str(message.sender_id),
							},
						)
						_, invalid_tokens = await firebase_push_service.send_to_tokens(tokens, payload)
						for invalid_token in invalid_tokens:
							await devices_service.invalidate_token(db, invalid_token, "invalid_firebase_token")
			update = await service.get_chat_list_update_payload(db, participant_id, chat_id)
			await ws_manager.send_to_user(
				participant_id,
				_event_payload("chat.list.updated", update.model_dump(mode="json")),
			)


async def broadcast_chat_read(chat_id: UUID, user_id: UUID, read_up_to_message_id: UUID | None) -> None:
	await ws_manager.broadcast_to_chat(
		chat_id,
		_event_payload(
			"chat.read",
			ChatReadData(
				chat_id=chat_id,
				user_id=user_id,
				read_up_to_message_id=read_up_to_message_id,
			).model_dump(mode="json"),
		),
	)

	async with SessionLocal() as db:
		participant_ids = await service.get_chat_participant_ids(db, chat_id)
		for participant_id in participant_ids:
			update = await service.get_chat_list_update_payload(db, participant_id, chat_id)
			await ws_manager.send_to_user(
				participant_id,
				_event_payload("chat.list.updated", update.model_dump(mode="json")),
			)


async def broadcast_message_updated(chat_id: UUID, message) -> None:
	payload = MessageUpdatedData(chat_id=chat_id, message=message).model_dump(mode="json")
	await ws_manager.broadcast_to_chat(chat_id, _event_payload("message.updated", payload))

	async with SessionLocal() as db:
		participant_ids = await service.get_chat_participant_ids(db, chat_id)
		for participant_id in participant_ids:
			update = await service.get_chat_list_update_payload(db, participant_id, chat_id)
			await ws_manager.send_to_user(
				participant_id,
				_event_payload("chat.list.updated", update.model_dump(mode="json")),
			)


async def broadcast_message_deleted(chat_id: UUID, message_id: UUID) -> None:
	await ws_manager.broadcast_to_chat(
		chat_id,
		_event_payload(
			"message.deleted",
			MessageDeletedData(chat_id=chat_id, message_id=message_id).model_dump(mode="json"),
		),
	)

	async with SessionLocal() as db:
		participant_ids = await service.get_chat_participant_ids(db, chat_id)
		for participant_id in participant_ids:
			update = await service.get_chat_list_update_payload(db, participant_id, chat_id)
			await ws_manager.send_to_user(
				participant_id,
				_event_payload("chat.list.updated", update.model_dump(mode="json")),
			)


async def broadcast_chat_deleted(chat_id: UUID, participant_ids: list[UUID]) -> None:
	payload = _event_payload("chat.deleted", ChatDeletedData(chat_id=chat_id).model_dump(mode="json"))
	await ws_manager.broadcast_to_chat(chat_id, payload)
	for participant_id in participant_ids:
		await ws_manager.send_to_user(participant_id, payload)
