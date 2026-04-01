from __future__ import annotations

from uuid import uuid4

import pytest
from starlette.websockets import WebSocketDisconnect


def _assert_connection_ready(payload: dict, chat_id: str) -> None:
    assert payload["event"] == "connection.ready"
    assert payload["data"]["scope"] == "chat"
    assert payload["data"]["chat_id"] == chat_id


def test_ws_chat_connect_success_for_participant(ws_connect, ws_two_users_chat):
    alice, _, chat_id = ws_two_users_chat()

    with ws_connect(f"/ws/chats/{chat_id}", alice["access_token"]) as websocket:
        ready = websocket.receive_json()
        _assert_connection_ready(ready, chat_id)


def test_ws_chat_connect_without_token_rejected(ws_connect, ws_two_users_chat):
    _, _, chat_id = ws_two_users_chat()

    with pytest.raises(WebSocketDisconnect) as exc:
        with ws_connect(f"/ws/chats/{chat_id}"):
            pass

    assert exc.value.code == 1008


def test_ws_chat_connect_with_invalid_token_rejected(ws_connect, ws_two_users_chat):
    _, _, chat_id = ws_two_users_chat()

    with pytest.raises(WebSocketDisconnect) as exc:
        with ws_connect(f"/ws/chats/{chat_id}", "invalid-token"):
            pass

    assert exc.value.code == 1008


def test_ws_chat_connect_nonexistent_chat_rejected(ws_connect, ws_register_and_login):
    user = ws_register_and_login("chat_user")

    with pytest.raises(WebSocketDisconnect) as exc:
        with ws_connect(f"/ws/chats/{uuid4()}", user["access_token"]):
            pass

    assert exc.value.code == 1008


def test_ws_chat_connect_non_participant_rejected(ws_connect, ws_two_users_chat, ws_register_and_login):
    _, _, chat_id = ws_two_users_chat()
    outsider = ws_register_and_login("outsider")

    with pytest.raises(WebSocketDisconnect) as exc:
        with ws_connect(f"/ws/chats/{chat_id}", outsider["access_token"]):
            pass

    assert exc.value.code == 1008
