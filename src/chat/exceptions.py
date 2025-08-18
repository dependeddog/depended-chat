class ChatError(Exception):
    """Base exception for chat errors."""


class UserNotFound(ChatError):
    pass
