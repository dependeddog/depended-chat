from __future__ import annotations

from uuid import uuid4

import pytest
from starlette.websockets import WebSocketDisconnect

from src.auth import utils as auth_utils


def _assert_connection_ready(payload: dict) -> None:
    assert payload["event"] == "connection.ready"
    assert payload["data"]["scope"] == "events"
    assert payload["data"]["chat_id"] is None


def test_ws_events_connect_success(ws_connect, ws_register_and_login):
    user = ws_register_and_login("events_user")

    with ws_connect("/ws/events", user["access_token"]) as websocket:
        ready = websocket.receive_json()
        _assert_connection_ready(ready)


def test_ws_events_connect_without_token_rejected(ws_connect):
    with pytest.raises(WebSocketDisconnect) as exc:
        with ws_connect("/ws/events"):
            pass

    assert exc.value.code == 1008


def test_ws_events_connect_with_invalid_token_rejected(ws_connect):
    with pytest.raises(WebSocketDisconnect) as exc:
        with ws_connect("/ws/events", "invalid-token"):
            pass

    assert exc.value.code == 1008


def test_ws_events_connect_with_token_for_missing_user_rejected(ws_connect):
    ghost_token, _ = auth_utils.create_access_token({"id": str(uuid4()), "username": "ghost"})

    with pytest.raises(WebSocketDisconnect) as exc:
        with ws_connect("/ws/events", ghost_token):
            pass

    assert exc.value.code == 1008
