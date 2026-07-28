"""Redis cache store implementation (in-memory for testing).

Implements CacheStore for get/set/delete with TTL support.
Uses in-memory dict with expiry tracking to allow testing
without requiring a real Redis instance.
"""

import time
from typing import Any

from data_quality_engine.storage.interfaces import CacheStore


class RedisCacheStore(CacheStore):
    """In-memory implementation of CacheStore (to be backed by Redis).

    Stores key-value pairs with optional TTL-based expiration.
    Uses a dict with (value, expire_at) tuples for expiry tracking.
    """

    def __init__(self) -> None:
        # Storage: key -> (value, expire_at_timestamp_or_None)
        self._store: dict[str, tuple[Any, float | None]] = {}

    def _is_expired(self, key: str) -> bool:
        """Check if a key has expired."""
        if key not in self._store:
            return True
        _, expire_at = self._store[key]
        if expire_at is None:
            return False
        return time.time() > expire_at

    def _cleanup_expired(self, key: str) -> None:
        """Remove key if expired."""
        if key in self._store and self._is_expired(key):
            del self._store[key]

    async def get(self, key: str) -> Any | None:
        """Get a value by key. Returns None if not found or expired."""
        self._cleanup_expired(key)
        if key not in self._store:
            return None
        value, _ = self._store[key]
        return value

    async def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        """Set a value with optional TTL (time-to-live) in seconds."""
        expire_at: float | None = None
        if ttl_seconds is not None:
            expire_at = time.time() + ttl_seconds
        self._store[key] = (value, expire_at)

    async def delete(self, key: str) -> bool:
        """Delete a key. Returns True if the key existed and was not expired."""
        self._cleanup_expired(key)
        if key in self._store:
            del self._store[key]
            return True
        return False

    async def exists(self, key: str) -> bool:
        """Check if a key exists and has not expired."""
        self._cleanup_expired(key)
        return key in self._store

    async def clear(self) -> None:
        """Clear all cached entries."""
        self._store.clear()
