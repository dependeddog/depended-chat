from __future__ import annotations

import jwt
from fastapi import WebSocket, status

from src.auth import utils as auth_utils
from src.core.security import exceptions as security_exceptions
from src.database import SessionLocal
from src.users import models as users_models, service as users_service


class WebSocketAuthError(Exception):
    pass


async def get_current_user_ws(websocket: WebSocket) -> users_models.User:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        raise WebSocketAuthError("Missing token")

    try:
        payload = auth_utils.decode_token(token)
    except jwt.ExpiredSignatureError as exc:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        raise WebSocketAuthError("Expired token") from exc
    except jwt.InvalidTokenError as exc:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        raise WebSocketAuthError("Invalid token") from exc

    if payload.get("type") != "access":
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        raise WebSocketAuthError(security_exceptions.InvalidTokenType.message)

    user_id = payload.get("id") or payload.get("sub")
    if not user_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        raise WebSocketAuthError(security_exceptions.MissingSubject.message)

    async with SessionLocal() as db:
        user = await users_service.get_user_by_id(db, user_id)

    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        raise WebSocketAuthError(security_exceptions.UserNotFound.message)

    return user
