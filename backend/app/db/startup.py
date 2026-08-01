"""启动后后台探测/重连数据库（避免阻塞 uvicorn 启动）。"""
from __future__ import annotations

import logging
import threading
import time

from app.core.config import settings

logger = logging.getLogger(__name__)
_db_ready = threading.Event()


def is_db_ready() -> bool:
    return _db_ready.is_set()


def mark_db_ready() -> None:
    _db_ready.set()


def mark_db_not_ready() -> None:
    _db_ready.clear()


def start_background_db_connect() -> None:
    if not settings.db_background_connect:
        return

    def _worker() -> None:
        from app.db.session import ping_db

        delays = [2, 3, 5, 8, 12, 20]
        for index, delay in enumerate(delays, start=1):
            if delay:
                time.sleep(delay)
            try:
                elapsed = ping_db(retries=1)
                mark_db_ready()
                logger.info("数据库连接成功（后台第 %s 次尝试），耗时 %.2fs", index, elapsed)
                return
            except Exception as exc:
                logger.warning("数据库后台连接第 %s/%s 次失败: %s", index, len(delays), exc)

        mark_db_not_ready()
        logger.error(
            "数据库多次连接失败。请检查远程 MySQL 网络/白名单，"
            "或在 .env 改用本地 MySQL：DATABASE_URL=mysql+pymysql://root:密码@127.0.0.1:3306/jeecg-boot?charset=utf8mb4"
        )

    threading.Thread(target=_worker, name="db-background-connect", daemon=True).start()
