from __future__ import annotations

import jwt
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.auth.exceptions import AuthError, TokenDecodeError
from src.core.security.exceptions import SecurityError


def register_exception_handlers(app: FastAPI) -> None:
	@app.exception_handler(AuthError)
	async def auth_error_handler(_: Request, exc: AuthError):
		# Единый JSON-ответ для всех наших доменных ошибок
		payload = {"detail": exc.message, "error": exc.error}
		# можно прокидывать дополнительную информацию
		if exc.extra:
			payload.update(exc.extra)
		return JSONResponse(status_code=exc.code, content=payload)

	@app.exception_handler(SecurityError)
	async def security_error_handler(_: Request, exc: SecurityError):
		headers = {}
		if exc.www_authenticate:
			headers["WWW-Authenticate"] = exc.www_authenticate
		payload = {"detail": exc.message, "error": exc.error}
		if exc.extra:
			payload.update(exc.extra)
		return JSONResponse(status_code=exc.code, content=payload, headers=headers)

	@app.exception_handler(jwt.InvalidTokenError)  # type: ignore[attr-defined]
	async def jwt_invalid_handler(_: Request, __: Exception):
		return JSONResponse(
			status_code=TokenDecodeError.code,
			content={"detail": TokenDecodeError.message, "error": TokenDecodeError.error},
		)
