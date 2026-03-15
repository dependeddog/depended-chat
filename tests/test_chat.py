import pytest
from sqlalchemy import select

from src.chat import models as chat_models


@pytest.mark.asyncio
async def test_create_chat_success(client, create_user, auth_header, db_session):
    await create_user("alice")
    bob = await create_user("bob")

    headers = await auth_header("alice")
    response = await client.post("/chats/direct", json={"user_id": str(bob.id)}, headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "direct"
    assert body["companion"]["id"] == str(bob.id)

    result = await db_session.execute(select(chat_models.Chat))
    assert len(result.scalars().all()) == 1


@pytest.mark.asyncio
async def test_create_chat_duplicate_returns_existing(client, create_user, auth_header, db_session):
    await create_user("alice")
    bob = await create_user("bob")
    headers = await auth_header("alice")

    first = await client.post("/chats/direct", json={"user_id": str(bob.id)}, headers=headers)
    second = await client.post("/chats/direct", json={"user_id": str(bob.id)}, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["chat_id"] == second.json()["chat_id"]

    result = await db_session.execute(select(chat_models.Chat))
    assert len(result.scalars().all()) == 1


@pytest.mark.asyncio
async def test_create_chat_without_auth(client, create_user):
    bob = await create_user("bob")

    response = await client.post("/chats/direct", json={"user_id": str(bob.id)})

    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_get_chats_current_user_only(client, create_user, auth_header):
    await create_user("alice")
    bob = await create_user("bob")
    carol = await create_user("carol")

    alice_headers = await auth_header("alice")
    bob_headers = await auth_header("bob")

    await client.post("/chats/direct", json={"user_id": str(bob.id)}, headers=alice_headers)
    await client.post("/chats/direct", json={"user_id": str(carol.id)}, headers=bob_headers)

    response = await client.get("/chats", headers=alice_headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["companion"]["id"] == str(bob.id)


@pytest.mark.asyncio
async def test_get_chats_without_auth(client):
    response = await client.get("/chats")

    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_send_message_success(client, create_user, auth_header, db_session):
    alice = await create_user("alice")
    bob = await create_user("bob")
    headers = await auth_header("alice")

    chat_response = await client.post("/chats/direct", json={"user_id": str(bob.id)}, headers=headers)
    assert chat_response.status_code == 200
    chat_id = chat_response.json()["chat_id"]

    response = await client.post(
        f"/chats/{chat_id}/messages",
        json={"text": "hello"},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["text"] == "hello"
    assert body["sender_id"] == str(alice.id)

    result = await db_session.execute(select(chat_models.Message))
    assert len(result.scalars().all()) == 1


@pytest.mark.asyncio
async def test_send_message_invalid_payload(client, create_user, auth_header):
    await create_user("alice")
    bob = await create_user("bob")
    headers = await auth_header("alice")

    chat_response = await client.post("/chats/direct", json={"user_id": str(bob.id)}, headers=headers)
    chat_id = chat_response.json()["chat_id"]

    response = await client.post(f"/chats/{chat_id}/messages", json={"content": "hello"}, headers=headers)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_send_message_without_auth(client, create_user, auth_header):
    await create_user("alice")
    bob = await create_user("bob")

    headers = await auth_header("alice")
    chat_response = await client.post("/chats/direct", json={"user_id": str(bob.id)}, headers=headers)
    chat_id = chat_response.json()["chat_id"]

    response = await client.post(f"/chats/{chat_id}/messages", json={"text": "hello"})

    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_get_messages_with_limit(client, create_user, auth_header):
    await create_user("alice")
    bob = await create_user("bob")
    headers = await auth_header("alice")

    chat_response = await client.post("/chats/direct", json={"user_id": str(bob.id)}, headers=headers)
    assert chat_response.status_code == 200
    chat_id = chat_response.json()["chat_id"]

    for idx in range(2):
        await client.post(
            f"/chats/{chat_id}/messages",
            json={"text": f"hello {idx}"},
            headers=headers,
        )

    response = await client.get(f"/chats/{chat_id}/messages", params={"limit": 1}, headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["limit"] == 1


@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
