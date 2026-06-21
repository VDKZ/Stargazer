import time
from typing import Any


class TTLCache:
    """In-memory cache with a per-entry TTL.

    Entries are kept even after they expire: their ETag can then still be used
    for a conditional revalidation (a 304 is cheap and does not consume quota).
    `get` reports whether the value is still *fresh*, so the caller can serve it
    directly without any network round-trip.
    """

    def __init__(self, ttl_seconds: int):
        self._ttl = ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str) -> tuple[Any, bool] | None:
        """Return (value, is_fresh), or None if the key is unknown."""
        entry = self._store.get(key)
        if entry is None:
            return None
        expires_at, value = entry
        return value, time.monotonic() < expires_at

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.monotonic() + self._ttl, value)
