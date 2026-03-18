from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError

from src.auth import ws_auth
from src.database import SessionLocal
from . import service
from .ws_manager import ws_manager
from .ws_schemas import ChatReadData, ConnectionReadyData, MessageCreatedData, TypingData, WebSocketEnvelope

router = APIRouter(tags=["chat-websocket"])


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

    await ws_manager.connect_chat(chat_id, websocket)
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
        for participant_id in participant_ids:
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
