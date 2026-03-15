import os
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
os.environ.setdefault("REFRESH_TOKEN_EXPIRE_DAYS", "7")
os.environ.setdefault("JWT_ISSUER", "depended-chat-tests")
os.environ.setdefault("JWT_AUDIENCE", "depended-chat-tests")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./.tmp-ignore.db")
os.environ.setdefault("RABBITMQ_URL", "amqp://guest:guest@localhost/")

from src.core.db.dependencies import get_db
from src.main import app
from src.models import Base
from src.users import models as user_models


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

    async def fake_publish(queue: str, message: str) -> None:
        return None

    app.dependency_overrides[get_db] = override_get_db

    from src.broker.rabbitmq import broker

    original_publish = broker.publish
    broker.publish = fake_publish

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client

    broker.publish = original_publish
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
        rec = await create_user(recipient)
        headers = await auth_header(owner)
        response = await client.post("/chats/direct", json={"user_id": str(rec.id)}, headers=headers)
        assert response.status_code == 200
        return response.json(), headers

    return _create
