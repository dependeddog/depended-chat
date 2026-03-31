from __future__ import annotations

import logging
from dataclasses import dataclass

from src.config import settings

logger = logging.getLogger(__name__)

try:
    import firebase_admin
    from firebase_admin import credentials, messaging
except Exception:  # pragma: no cover
    firebase_admin = None
    credentials = None
    messaging = None


@dataclass
class FirebasePushPayload:
    title: str
    body: str
    data: dict[str, str]


class FirebasePushService:
    def __init__(self) -> None:
        self._initialized = False

    def _init_app(self) -> bool:
        if self._initialized:
            return True

        if not settings.firebase_enabled:
            return False

        if firebase_admin is None or credentials is None or messaging is None:
            logger.warning("Firebase SDK is not available, push delivery disabled")
            return False

        if not settings.firebase_credentials_path:
            logger.warning("FIREBASE_CREDENTIALS_PATH is not set, push delivery disabled")
            return False

        cred = credentials.Certificate(settings.firebase_credentials_path)
        firebase_admin.initialize_app(cred, {"projectId": settings.firebase_project_id or None})
        self._initialized = True
        return True

    async def send_to_tokens(self, tokens: list[str], payload: FirebasePushPayload) -> tuple[list[str], list[str]]:
        if not tokens:
            return [], []

        if not self._init_app():
            return [], []

        message = messaging.MulticastMessage(
            tokens=tokens,
            notification=messaging.Notification(title=payload.title, body=payload.body),
            data=payload.data,
        )
        response = messaging.send_each_for_multicast(message)

        successful: list[str] = []
        invalid: list[str] = []
        for index, result in enumerate(response.responses):
            token = tokens[index]
            if result.success:
                successful.append(token)
                continue

            error_code = getattr(getattr(result.exception, "code", None), "value", "") or str(result.exception)
            if "registration-token-not-registered" in error_code or "invalid-registration-token" in error_code:
                invalid.append(token)

        return successful, invalid


firebase_push_service = FirebasePushService()
