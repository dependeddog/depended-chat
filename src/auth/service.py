from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.chat import models

from . import schemas, utils


async def get_user_by_username(db: AsyncSession, username: str) -> models.User | None:
    result = await db.execute(select(models.User).where(models.User.username == username))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, user_in: schemas.UserCreate) -> models.User:
    user = models.User(
        username=user_in.username,
        password=utils.get_password_hash(user_in.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(
    db: AsyncSession, username: str, password: str
) -> models.User | None:
    user = await get_user_by_username(db, username)
    if not user or not utils.verify_password(password, user.password):
        return None
    return user
