from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
import uuid

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import INET, UUID

from src.models import Base


class RefreshToken(Base):
	__tablename__ = "auth_refresh_tokens"

	id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
	user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)

	# Уникальный идентификатор из payload (jti) + защита от подбора — храним только хэш токена
	jti: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, index=True)
	token_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

	# Аудит/жизненный цикл
	created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
												 nullable=False)
	expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
	used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
	revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

	rotated_from_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("auth_refresh_tokens.id"))

	# Контекст
	user_agent: Mapped[Optional[str]] = mapped_column(String)
	ip: Mapped[Optional[str]] = mapped_column(INET)

	user = relationship("User")  # если у вас класс User уже объявлен
	rotated_from = relationship("RefreshToken", remote_side=[id])

	__table_args__ = (
		UniqueConstraint("token_sha256", name="uq_refresh_token_sha256"),
	)
