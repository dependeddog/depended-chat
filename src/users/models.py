from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models import Base

if TYPE_CHECKING:
	from src.chat.models import Message


class User(Base):
	__tablename__ = "users"

	id: Mapped[int] = mapped_column(primary_key=True, index=True)
	username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
	password: Mapped[str] = mapped_column(String(255))
	messages: Mapped[list["Message"]] = relationship(back_populates="user")
