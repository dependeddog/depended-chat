import jwt
from fastapi import Depends, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.core.db import dependencies as db_dependencies
from src.core.security import exceptions as security_exceptions
from src.users import models as users_models, service as users_service
from . import exceptions

bearer = HTTPBearer(auto_error=True)


def _decode_access(token: str) -> dict:
	try:
		return jwt.decode(
			token,
			settings.jwt_secret,
			algorithms=[settings.jwt_algorithm],
			audience=settings.jwt_audience,
			issuer=settings.jwt_issuer,
			options={"require": ["exp", "iat", "nbf", "aud", "iss", "type"]},
			leeway=5,  # секунд на рассинхрон
		)
	except jwt.ExpiredSignatureError:
		raise exceptions.TokenExpired()
	except jwt.InvalidTokenError:
		raise exceptions.InvalidToken()


async def get_current_user(
		creds: HTTPAuthorizationCredentials = Security(bearer),
		db: AsyncSession = Depends(db_dependencies.get_db),
) -> users_models.User:
	payload = _decode_access(creds.credentials)

	if payload.get("type") != "access":
		raise security_exceptions.InvalidTokenType()

	user_id = payload.get("id") or payload.get("sub")
	if not user_id:
		raise security_exceptions.MissingSubject()

	user = await users_service.get_user_by_id(db, user_id)
	if not user:
		raise security_exceptions.UserNotFound()

	return user
