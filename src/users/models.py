from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models import Base

if TYPE_CHECKING:
	from src.chat.models import Message, Chat


class User(Base):
	__tablename__ = "users"

	id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, index=True)
	username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
	password: Mapped[str] = mapped_column(String(255))

	chats_as_user1: Mapped[list["Chat"]] = relationship(foreign_keys="Chat.user1_id", back_populates="user1")
	chats_as_user2: Mapped[list["Chat"]] = relationship(foreign_keys="Chat.user2_id", back_populates="user2")
	messages: Mapped[list["Message"]] = relationship(back_populates="user", cascade="all, delete-orphan")
