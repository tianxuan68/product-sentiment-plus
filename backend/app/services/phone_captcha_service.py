"""手机短信验证码缓存（MySQL 持久化，避免内存缓存随重启/多进程丢失）。"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

PHONE_CAPTCHA_PREFIX = "phone_captcha:"
CAPTCHA_TTL_SECONDS = 300
_CAPTCHA_TTL = CAPTCHA_TTL_SECONDS
_table_ready = False

_MOBILE_RE = re.compile(r"^1[3-9]\d{9}$")


def normalize_mobile(mobile: str) -> str:
    m = (mobile or "").strip().replace(" ", "").replace("-", "")
    if m.startswith("+86"):
        m = m[3:]
    if m.startswith("86") and len(m) == 13:
        m = m[2:]
    return m


def _cache_key(mobile: str) -> str:
    return f"{PHONE_CAPTCHA_PREFIX}{normalize_mobile(mobile)}"


def _ensure_table(db: Session) -> None:
    global _table_ready
    if _table_ready:
        return
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS `sys_cache` (
              `cache_key` varchar(128) NOT NULL,
              `cache_value` varchar(512) DEFAULT NULL,
              `expire_time` datetime DEFAULT NULL,
              PRIMARY KEY (`cache_key`),
              KEY `idx_expire` (`expire_time`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
    )
    db.commit()
    _table_ready = True


def _purge_expired(db: Session) -> None:
    db.execute(text("DELETE FROM sys_cache WHERE expire_time IS NOT NULL AND expire_time < :now"), {"now": datetime.now()})
    db.commit()


def captcha_validity_minutes() -> int:
    """验证码有效分钟数（与 Spug 模板 number 变量一致）。"""
    return max(1, min(99, CAPTCHA_TTL_SECONDS // 60))


def store_phone_captcha(mobile: str, code: str, ttl: int = _CAPTCHA_TTL) -> None:
    phone = normalize_mobile(mobile)
    if not _MOBILE_RE.match(phone):
        raise ValueError("手机号格式不正确")
    value = str(code).strip()
    expire = datetime.now() + timedelta(seconds=ttl)
    key = _cache_key(phone)

    db = SessionLocal()
    try:
        _ensure_table(db)
        _purge_expired(db)
        db.execute(
            text(
                """
                INSERT INTO sys_cache (cache_key, cache_value, expire_time)
                VALUES (:key, :val, :exp)
                ON DUPLICATE KEY UPDATE cache_value = VALUES(cache_value), expire_time = VALUES(expire_time)
                """
            ),
            {"key": key, "val": value, "exp": expire},
        )
        db.commit()
        logger.info("SMS captcha stored mobile=%s****%s", phone[:3], phone[-4:])
    finally:
        db.close()


def get_phone_captcha(mobile: str) -> Optional[str]:
    phone = normalize_mobile(mobile)
    key = _cache_key(phone)
    db = SessionLocal()
    try:
        _ensure_table(db)
        row = db.execute(
            text("SELECT cache_value, expire_time FROM sys_cache WHERE cache_key = :key"),
            {"key": key},
        ).fetchone()
        if not row:
            return None
        value, expire_time = row[0], row[1]
        if expire_time and expire_time < datetime.now():
            db.execute(text("DELETE FROM sys_cache WHERE cache_key = :key"), {"key": key})
            db.commit()
            return None
        return str(value).strip() if value is not None else None
    finally:
        db.close()


def validate_phone_captcha(mobile: str, captcha: str) -> bool:
    if not captcha:
        return False
    cached = get_phone_captcha(mobile)
    input_code = str(captcha).strip()
    ok = cached is not None and cached == input_code
    if not ok:
        logger.warning(
            "SMS captcha mismatch mobile=%s cached=%s input=%s",
            normalize_mobile(mobile),
            cached,
            input_code,
        )
    return ok


def pop_phone_captcha(mobile: str) -> Optional[str]:
    phone = normalize_mobile(mobile)
    key = _cache_key(phone)
    value = get_phone_captcha(phone)
    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM sys_cache WHERE cache_key = :key"), {"key": key})
        db.commit()
    finally:
        db.close()
    return value
