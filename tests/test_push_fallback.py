from __future__ import annotations

import pytest

from src.devices import service as devices_service
from src.notifications import firebase_service


async def _register_token(client, headers, token: str, device_id: str):
    response = await client.post(
        "/devices/firebase-token",
        json={"token": token, "device_id": device_id, "platform": "web"},
        headers=headers,
    )
    assert response.status_code == 200


async def _create_two_users_chat(client, create_user, auth_header):
    await create_user("alice")
    await create_user("bob")
    alice_headers = await auth_header("alice")
    bob_headers = await auth_header("bob")
    chat_response = await client.post("/chats/direct", json={"username": "bob"}, headers=alice_headers)
    assert chat_response.status_code == 200
    return chat_response.json()["chat_id"], alice_headers, bob_headers


@pytest.mark.asyncio
async def test_send_message_uses_push_fallback_for_recipient_not_in_chat(
    client,
    create_user,
    auth_header,
    monkeypatch,
    db_session,
    user_in_db,
):
    chat_id, alice_headers, bob_headers = await _create_two_users_chat(client, create_user, auth_header)
    await _register_token(client, bob_headers, "fcm-token-fallback-1234567890", "bob-device")

    bob = await user_in_db("bob")
    tokens_before = await devices_service.get_active_tokens(db_session, bob.id)
    assert len(tokens_before) == 1

    calls: list[tuple[list[str], str, str, dict[str, str]]] = []

    async def fake_send_to_tokens(tokens, payload):
        calls.append((tokens, payload.title, payload.body, payload.data))
        return tokens, []

    monkeypatch.setattr(firebase_service.firebase_push_service, "send_to_tokens", fake_send_to_tokens)

    response = await client.post(
        f"/chats/{chat_id}/messages",
        json={"text": "offline push"},
        headers=alice_headers,
    )

    assert response.status_code == 200
    message = response.json()
    assert len(calls) == 1
    called_tokens, title, body, data = calls[0]
    assert called_tokens == tokens_before
    assert title == "alice"
    assert body == "offline push"
    assert data["type"] == "new_message"
    assert data["chat_id"] == chat_id
    assert data["message_id"] == message["id"]


@pytest.mark.asyncio
async def test_send_message_does_not_use_push_when_recipient_in_chat(
    ws_client,
    ws_connect,
    ws_two_users_chat,
    monkeypatch,
):
    alice, bob, chat_id = ws_two_users_chat()

    register_response = ws_client.post(
        "/devices/firebase-token",
        json={"token": "fcm-token-online-1234567890", "device_id": "bob-device", "platform": "web"},
        headers=bob["headers"],
    )
    assert register_response.status_code == 200

    calls: list[list[str]] = []

    async def fake_send_to_tokens(tokens, payload):
        calls.append(tokens)
        return tokens, []

    monkeypatch.setattr(firebase_service.firebase_push_service, "send_to_tokens", fake_send_to_tokens)

    with ws_connect(f"/ws/chats/{chat_id}", bob["access_token"]) as bob_chat_ws:
        bob_chat_ws.receive_json()

        response = ws_client.post(
            f"/chats/{chat_id}/messages",
            json={"text": "in chat"},
            headers=alice["headers"],
        )
        assert response.status_code == 200
        message_event = bob_chat_ws.receive_json()
        assert message_event["event"] == "message.created"

    assert calls == []
