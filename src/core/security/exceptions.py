from __future__ import annotations

from fastapi import status


class SecurityError(Exception):
	code: int = status.HTTP_401_UNAUTHORIZED
	error: str = "auth_error"
	message: str = "Authentication required."
	www_authenticate: str | None = "Bearer"

	def __init__(self, message: str | None = None, *, extra: dict | None = None):
		super().__init__(message or self.message)
		self.extra = extra or {}


class NotAuthenticated(SecurityError):
	error = "not_authenticated"
	message = "Не авторизован."


class TokenExpired(SecurityError):
	error = "token_expired"
	message = "Срок действия токена истёк."


class InvalidToken(SecurityError):
	error = "invalid_token"
	message = "Неверный токен."


class InvalidTokenType(SecurityError):
	error = "invalid_token_type"
	message = "Ожидался access-токен."


class MissingSubject(SecurityError):
	error = "missing_subject"
	message = "В токене отсутствует subject (id)."


class UserNotFound(SecurityError):
	error = "user_not_found"
	message = "Пользователь не найден."
