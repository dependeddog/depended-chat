from __future__ import annotations

from fastapi import status


class AuthError(Exception):
	code: int = status.HTTP_400_BAD_REQUEST
	error: str = "auth_error"
	message: str = "Authentication/authorization error"

	def __init__(self, message: str | None = None, *, extra: dict | None = None):
		super().__init__(message or self.message)
		self.extra = extra or {}


# Учётные данные / пользователи
class InvalidCredentials(AuthError):
	code = status.HTTP_401_UNAUTHORIZED
	error = "invalid_credentials"
	message = "Неверный логин или пароль."


class UsernameAlreadyExists(AuthError):
	code = status.HTTP_409_CONFLICT
	error = "username_taken"
	message = "Пользователь с таким именем уже существует."


# JWT / refresh
class NotRefreshToken(AuthError):
	code = status.HTTP_400_BAD_REQUEST
	error = "not_refresh_token"
	message = "Ожидался refresh-токен."


class TokenDecodeError(AuthError):
	code = status.HTTP_401_UNAUTHORIZED
	error = "token_decode_error"
	message = "Некорректный JWT."


class RefreshNotFound(AuthError):
	code = status.HTTP_401_UNAUTHORIZED
	error = "refresh_not_found"
	message = "Refresh-токен не найден."


class RefreshRevoked(AuthError):
	code = status.HTTP_401_UNAUTHORIZED
	error = "refresh_revoked"
	message = "Refresh-токен отозван."


class RefreshExpired(AuthError):
	code = status.HTTP_401_UNAUTHORIZED
	error = "refresh_expired"
	message = "Срок действия refresh-токена истёк."


class RefreshMismatch(AuthError):
	code = status.HTTP_401_UNAUTHORIZED
	error = "refresh_mismatch"
	message = "Refresh-токен не соответствует записи."


class RefreshInactive(AuthError):
	code = status.HTTP_401_UNAUTHORIZED
	error = "refresh_inactive"
	message = "Refresh-токен недействителен."


class UsernameAlreadyRegistered(AuthError):
	code = status.HTTP_409_CONFLICT
	error = "username_already_registered"
	message = "Пользователь с таким именем уже зарегистрирован."


class RefreshExpected(AuthError):
	code = status.HTTP_400_BAD_REQUEST
	error = "refresh_expected"
	message = "Ожидался refresh-токен при обновлении."
