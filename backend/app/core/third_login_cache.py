"""第三方登录临时状态缓存（无 Redis 时的内存实现）。"""
from __future__ import annotations

import secrets
import time
from typing import Any, Dict, Optional, Tuple

_store: Dict[str, Tuple[Any, float]] = {}
DEFAULT_TTL = 600


def _purge() -> None:
    now = time.time()
    expired = [k for k, (_, exp) in _store.items() if exp <= now]
    for key in expired:
        _store.pop(key, None)


def set_value(key: str, value: Any, ttl: int = DEFAULT_TTL) -> None:
    _purge()
    _store[key] = (value, time.time() + ttl)


def get_value(key: str) -> Optional[Any]:
    _purge()
    item = _store.get(key)
    if not item:
        return None
    value, expire_at = item
    if time.time() > expire_at:
        _store.pop(key, None)
        return None
    return value


def pop_value(key: str) -> Optional[Any]:
    value = get_value(key)
    _store.pop(key, None)
    return value


def new_operate_code() -> str:
    return secrets.token_urlsafe(16)
