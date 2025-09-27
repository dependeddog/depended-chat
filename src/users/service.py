from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import utils as auth_utils
from . import models, schemas


async def get_user_by_username(db: AsyncSession, username: str) -> Optional[models.User]:
	result = await db.execute(select(models.User).where(models.User.username == username))
	return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[models.User]:
	result = await db.execute(select(models.User).where(models.User.id == user_id))
	return result.scalar_one_or_none()


async def create_user(db: AsyncSession, user_in: schemas.UserCreate) -> models.User:
	user = models.User(
		username=user_in.username,
		password=auth_utils.get_password_hash(user_in.password),
	)
	db.add(user)
	await db.commit()
	await db.refresh(user)
	return user
