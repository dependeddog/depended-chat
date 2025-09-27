import hashlib
from datetime import datetime, timezone


def now_utc():
	return datetime.now(timezone.utc)


def sha256_hex(s: str) -> str:
	return hashlib.sha256(s.encode("utf-8")).hexdigest()
