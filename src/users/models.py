from typing import TYPE_CHECKING
import uuid

from sqlalchemy import String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models import Base

if TYPE_CHECKING:
    from src.chat.models import ChatParticipant, Message


class User(Base):
    __tablename__ = "users"

	id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, index=True, default=uuid.uuid4)
	username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
	password: Mapped[str] = mapped_column(String(255))

    chat_participants: Mapped[list["ChatParticipant"]] = relationship(back_populates="user")
    sent_messages: Mapped[list["Message"]] = relationship(back_populates="sender", cascade="all, delete-orphan")
