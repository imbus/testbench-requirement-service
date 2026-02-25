"""Lightweight TTL-based cache for single values."""

import time
from datetime import timedelta
from typing import Generic, TypeVar

T = TypeVar("T")

# Default time-to-live in seconds (5 minutes).
DEFAULT_TTL: float = 300.0


class TTLCache(Generic[T]):
    """A simple single-value cache that expires after a configurable TTL.

    Usage::

        cache: TTLCache[list[dict]] = TTLCache(ttl=300.0)

        # Store a value
        cache.set(data)

        # Retrieve (returns None when expired or unset)
        value = cache.get()

        # Force refresh on next access
        cache.invalidate()
    """

    __slots__ = ("_is_set", "_timestamp", "_ttl", "_value")

    def __init__(self, ttl: float | timedelta = DEFAULT_TTL) -> None:
        if isinstance(ttl, timedelta):
            self._ttl = ttl.total_seconds()
        else:
            self._ttl = ttl
        self._value: T | None = None
        self._timestamp: float = 0.0
        self._is_set: bool = False

    @property
    def is_valid(self) -> bool:
        """Return True if the cache holds a value that has not expired."""
        return self._is_set and (time.monotonic() - self._timestamp) < self._ttl

    def get(self) -> T | None:
        """Return the cached value if still valid, otherwise ``None``."""
        return self._value if self.is_valid else None

    @property
    def stale_value(self) -> T | None:
        """Return the cached value regardless of expiry (for graceful degradation)."""
        return self._value

    def set(self, value: T) -> None:
        """Store *value* and reset the expiry timer."""
        self._value = value
        self._timestamp = time.monotonic()
        self._is_set = True

    def invalidate(self) -> None:
        """Mark the cache as expired, forcing a fresh fetch on the next access."""
        self._is_set = False
        self._timestamp = 0.0

    def __repr__(self) -> str:
        remaining = max(0.0, self._ttl - (time.monotonic() - self._timestamp))
        return f"TTLCache(valid={self.is_valid}, ttl={self._ttl}s, remaining={remaining:.1f}s)"
