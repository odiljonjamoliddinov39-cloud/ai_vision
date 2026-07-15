"""Small in-memory TTL cache for product recognition results."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


@dataclass
class _CacheEntry:
    value: Any
    expires_at: float


class RecognitionCache:
    def __init__(self, expiration_seconds: int = 1800):
        self.expiration_seconds = max(1, int(expiration_seconds))
        self._items: dict[str, _CacheEntry] = {}

    def get(self, key: str):
        entry = self._items.get(key)
        if entry is None:
            return None
        if entry.expires_at < time.time():
            self._items.pop(key, None)
            return None
        return entry.value

    def set(self, key: str, value) -> None:
        self._items[key] = _CacheEntry(
            value=value,
            expires_at=time.time() + self.expiration_seconds,
        )

    def clear(self) -> None:
        self._items.clear()
