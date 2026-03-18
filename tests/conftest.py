import os
import asyncio
from pathlib import Path
import sys
from uuid import UUID

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.ext.compiler import compiles


@compiles(INET, "sqlite")
def _compile_inet_sqlite(type_, compiler, **kw):
    return "VARCHAR"


os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
os.environ.setdefault("REFRESH_TOKEN_EXPIRE_DAYS", "7")
os.environ.setdefault("JWT_ISSUER", "depended-chat-tests")
os.environ.setdefault("JWT_AUDIENCE", "depended-chat-tests")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./.tmp-ignore.db")

from src.core.db.dependencies import get_db
from src.main import app
from src.models import Base
from src.users import models as user_models
from src.chat.ws_manager import ws_manager


@pytest_asyncio.fixture()
async def db_session(tmp_path: Path) -> AsyncSession:
    db_file = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}", future=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture()
async def client(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    from src.auth import ws_auth
    from src.chat import ws_router

    original_ws_auth_session_local = ws_auth.SessionLocal
    original_ws_router_session_local = ws_router.SessionLocal

    test_session_factory = async_sessionmaker(db_session.bind, expire_on_commit=False)
    ws_auth.SessionLocal = test_session_factory
    ws_router.SessionLocal = test_session_factory

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client

    ws_auth.SessionLocal = original_ws_auth_session_local
    ws_router.SessionLocal = original_ws_router_session_local
    app.dependency_overrides.clear()


@pytest_asyncio.fixture()
async def create_user(db_session: AsyncSession):
    async def _create_user(username: str, password: str = "password123") -> user_models.User:
        from src.users import schemas as user_schemas
        from src.users import service as users_service

        return await users_service.create_user(
            db_session,
            user_schemas.UserCreate(username=username, password=password),
        )

    return _create_user


@pytest_asyncio.fixture()
async def login_user(client: AsyncClient):
    async def _login(username: str, password: str = "password123") -> dict:
        response = await client.post("/auth/login", json={"username": username, "password": password})
        assert response.status_code == 200
        return response.json()

    return _login


@pytest_asyncio.fixture()
async def auth_header(login_user):
    async def _auth_header(username: str, password: str = "password123") -> dict[str, str]:
        data = await login_user(username, password)
        return {"Authorization": f"Bearer {data['access_token']}"}

    return _auth_header


@pytest_asyncio.fixture()
async def refresh_header(login_user):
    async def _refresh_header(username: str, password: str = "password123") -> dict[str, str]:
        data = await login_user(username, password)
        return {"Authorization": f"Bearer {data['refresh_token']}"}

    return _refresh_header


@pytest_asyncio.fixture()
async def user_in_db(db_session: AsyncSession):
    async def _get(username: str) -> user_models.User | None:
        result = await db_session.execute(select(user_models.User).where(user_models.User.username == username))
        return result.scalar_one_or_none()

    return _get


@pytest_asyncio.fixture()
async def create_chat(client: AsyncClient, create_user, auth_header):
    async def _create(owner: str, recipient: str):
        await create_user(owner)
        await create_user(recipient)
        headers = await auth_header(owner)
        response = await client.post("/chats/direct", json={"username": recipient}, headers=headers)
        assert response.status_code == 200
        return response.json(), headers

    return _create


@pytest.fixture(autouse=True)
def reset_ws_manager_state():
    ws_manager._user_connections.clear()
    ws_manager._chat_connections.clear()
    yield
    ws_manager._user_connections.clear()
    ws_manager._chat_connections.clear()


@pytest.fixture()
def ws_client(tmp_path: Path):
    db_file = tmp_path / "test_ws.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}", future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _prepare_db() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_prepare_db())

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    from src.auth import ws_auth
    from src.chat import ws_router

    original_ws_auth_session_local = ws_auth.SessionLocal
    original_ws_router_session_local = ws_router.SessionLocal

    ws_auth.SessionLocal = session_factory
    ws_router.SessionLocal = session_factory

    with TestClient(app) as client:
        yield client

    ws_auth.SessionLocal = original_ws_auth_session_local
    ws_router.SessionLocal = original_ws_router_session_local
    app.dependency_overrides.clear()
    asyncio.run(engine.dispose())


@pytest.fixture()
def ws_register_and_login(ws_client: TestClient):
    def _register_and_login(username: str, password: str = "password123") -> dict:
        register_response = ws_client.post("/auth/register", json={"username": username, "password": password})
        assert register_response.status_code == 200

        login_response = ws_client.post("/auth/login", json={"username": username, "password": password})
        assert login_response.status_code == 200

        auth_payload = login_response.json()
        return {
            "id": UUID(register_response.json()["id"]),
            "username": username,
            "access_token": auth_payload["access_token"],
            "headers": {"Authorization": f"Bearer {auth_payload['access_token']}"},
        }

    return _register_and_login


@pytest.fixture()
def ws_create_direct_chat(ws_client: TestClient):
    def _create(owner_headers: dict[str, str], recipient_username: str) -> str:
        response = ws_client.post("/chats/direct", json={"username": recipient_username}, headers=owner_headers)
        assert response.status_code == 200
        return response.json()["chat_id"]

    return _create


@pytest.fixture()
def ws_connect(ws_client: TestClient):
    def _connect(path: str, token: str | None = None):
        target = path if token is None else f"{path}?token={token}"
        return ws_client.websocket_connect(target)

    return _connect


@pytest.fixture()
def ws_two_users_chat(ws_register_and_login, ws_create_direct_chat):
    def _setup():
        alice = ws_register_and_login("alice")
        bob = ws_register_and_login("bob")
        chat_id = ws_create_direct_chat(alice["headers"], bob["username"])
        return alice, bob, chat_id

    return _setup


def assert_connection_ready(payload: dict, expected_scope: str, expected_chat_id: str | None = None) -> None:
    assert payload["event"] == "connection.ready"
    assert payload["data"]["scope"] == expected_scope
    assert payload["data"]["chat_id"] == expected_chat_id
