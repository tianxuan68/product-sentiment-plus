from __future__ import annotations

import logging
import time
from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

logger = logging.getLogger(__name__)

# 远程 MySQL 常在 wait_timeout 后断开；定期回收避免拿到死连接
_POOL_RECYCLE_SECONDS = 1800


def _build_engine():
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_recycle=_POOL_RECYCLE_SECONDS,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        connect_args={
            "connect_timeout": settings.db_connect_timeout,
            "read_timeout": settings.db_read_timeout,
            "write_timeout": settings.db_write_timeout,
        },
    )


engine = _build_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def _open_session():
    """取 Session。pool_pre_ping 会在检出连接时自动探测，无需每次 SELECT 1。"""
    if not settings.db_session_ping:
        return SessionLocal()

    max_attempts = max(1, settings.db_connect_retries)
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            return db
        except OperationalError as exc:
            last_exc = exc
            db.close()
            logger.warning("获取数据库连接失败（%s/%s）: %s", attempt, max_attempts, exc)
            if attempt < max_attempts:
                time.sleep(settings.db_connect_retry_delay * attempt)
        except Exception:
            db.close()
            raise
    assert last_exc is not None
    raise last_exc


def ping_db(*, retries: Optional[int] = None, delay: Optional[float] = None) -> float:
    """执行 SELECT 1，失败时重试。返回耗时（秒）。"""
    max_attempts = retries if retries is not None else settings.db_connect_retries
    wait = delay if delay is not None else settings.db_connect_retry_delay
    last_exc: Exception | None = None
    started = time.perf_counter()

    for attempt in range(1, max_attempts + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return time.perf_counter() - started
        except OperationalError as exc:
            last_exc = exc
            logger.warning("数据库连接失败（第 %s/%s 次）: %s", attempt, max_attempts, exc)
            if attempt < max_attempts:
                time.sleep(wait * attempt)
        except Exception as exc:
            last_exc = exc
            logger.warning("数据库连接失败（第 %s/%s 次）: %s", attempt, max_attempts, exc)
            if attempt < max_attempts:
                time.sleep(wait * attempt)

    assert last_exc is not None
    raise last_exc


def get_db():
    """FastAPI 依赖：每个请求一个 Session，结束时关闭归还连接池。"""
    db = _open_session()
    try:
        yield db
    finally:
        db.close()


def warmup_db_pool() -> float:
    """启动时预热连接池（远程库默认仅 1 条连接 + 重试）。"""
    if not settings.db_warmup_enabled:
        return ping_db()

    started = time.perf_counter()
    warmup_count = max(1, min(settings.db_warmup_connections, settings.db_pool_size))
    conns = []
    try:
        for i in range(warmup_count):
            for attempt in range(1, settings.db_connect_retries + 1):
                try:
                    conn = engine.connect()
                    conn.execute(text("SELECT 1"))
                    conns.append(conn)
                    break
                except OperationalError as exc:
                    logger.warning(
                        "连接池预热 %s/%s 失败（第 %s 次）: %s",
                        i + 1,
                        warmup_count,
                        attempt,
                        exc,
                    )
                    if attempt >= settings.db_connect_retries:
                        raise
                    time.sleep(settings.db_connect_retry_delay * attempt)
            if i + 1 < warmup_count:
                time.sleep(0.3)
    finally:
        for conn in conns:
            conn.close()
    return time.perf_counter() - started


def is_db_healthy() -> tuple[bool, float | None]:
    try:
        elapsed = ping_db(retries=1)
        return True, round(elapsed * 1000, 1)
    except Exception:
        return False, None
