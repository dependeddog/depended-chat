import pytest


@pytest.mark.asyncio
async def test_register_success(client, user_in_db):
    response = await client.post("/auth/register", json={"username": "alice", "password": "password123"})

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "alice"
    assert "id" in body

    created = await user_in_db("alice")
    assert created is not None


@pytest.mark.asyncio
async def test_register_duplicate_username(client, create_user):
    await create_user("alice")

    response = await client.post("/auth/register", json={"username": "alice", "password": "password123"})

    assert response.status_code == 409
    assert response.json()["error"] == "username_already_registered"


@pytest.mark.asyncio
async def test_register_invalid_payload(client):
    response = await client.post("/auth/register", json={"username": "alice"})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_success(client, create_user):
    await create_user("alice")

    response = await client.post("/auth/login", json={"username": "alice", "password": "password123"})

    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["access_expires_in"] > 0


@pytest.mark.asyncio
async def test_login_wrong_password(client, create_user):
    await create_user("alice")

    response = await client.post("/auth/login", json={"username": "alice", "password": "wrong"})

    assert response.status_code == 401
    assert response.json()["error"] == "invalid_credentials"


@pytest.mark.asyncio
async def test_login_unknown_user(client):
    response = await client.post("/auth/login", json={"username": "ghost", "password": "password123"})

    assert response.status_code == 401
    assert response.json()["error"] == "invalid_credentials"


@pytest.mark.asyncio
async def test_refresh_success(client, create_user, login_user):
    await create_user("alice")
    login_data = await login_user("alice")

    response = await client.post(
        "/auth/refresh",
        headers={"Authorization": f"Bearer {login_data['refresh_token']}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["refresh_token"] != login_data["refresh_token"]


@pytest.mark.asyncio
async def test_refresh_with_access_token_rejected(client, create_user, login_user):
    await create_user("alice")
    login_data = await login_user("alice")

    response = await client.post(
        "/auth/refresh",
        headers={"Authorization": f"Bearer {login_data['access_token']}"},
    )

    assert response.status_code == 400
    assert response.json()["error"] == "refresh_expected"


@pytest.mark.asyncio
async def test_refresh_without_token(client):
    response = await client.post("/auth/refresh")

    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_logout_success(client, create_user, login_user):
    await create_user("alice")
    login_data = await login_user("alice")

    response = await client.post(
        "/auth/logout",
        headers={"Authorization": f"Bearer {login_data['refresh_token']}"},
    )

    assert response.status_code == 204


@pytest.mark.asyncio
async def test_logout_without_token(client):
    response = await client.post("/auth/logout")

    assert response.status_code in (401, 403)
