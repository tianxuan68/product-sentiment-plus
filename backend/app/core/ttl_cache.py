"""轻量 TTL 内存缓存（无第三方依赖）。"""
from __future__ import annotations

import threading
import time
from typing import Generic, Hashable, Optional, TypeVar

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


class TTLCache(Generic[K, V]):
    def __init__(self, maxsize: int = 512, ttl_seconds: int = 300) -> None:
        self._maxsize = max(1, maxsize)
        self._ttl = max(1, ttl_seconds)
        self._data: dict[K, tuple[float, V]] = {}
        self._lock = threading.Lock()

    def get(self, key: K) -> Optional[V]:
        now = time.time()
        with self._lock:
            entry = self._data.get(key)
            if not entry:
                return None
            expires_at, value = entry
            if expires_at <= now:
                del self._data[key]
                return None
            return value

    def set(self, key: K, value: V) -> None:
        expires_at = time.time() + self._ttl
        with self._lock:
            if key not in self._data and len(self._data) >= self._maxsize:
                oldest_key = min(self._data, key=lambda k: self._data[k][0])
                del self._data[oldest_key]
            self._data[key] = (expires_at, value)

    def delete(self, key: K) -> None:
        with self._lock:
            self._data.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
