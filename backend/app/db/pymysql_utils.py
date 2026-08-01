"""PyMySQL 直连工具（DDL 迁移等需独立长超时的场景）。"""
from __future__ import annotations

from typing import Any
from urllib.parse import unquote

import pymysql

from app.core.config import settings


def parse_database_url(url: str | None = None) -> dict[str, Any]:
    """解析 SQLAlchemy DATABASE_URL → PyMySQL connect 参数。"""
    raw = (url or settings.database_url).strip()
    if not raw.startswith("mysql"):
        raise ValueError(f"仅支持 MySQL DATABASE_URL，当前: {raw[:32]}...")

    body = raw.split("://", 1)[1]
    auth, hostpart = body.rsplit("@", 1)
    user, password = auth.split(":", 1)
    host_port, database = hostpart.split("/", 1)
    if "?" in database:
        database = database.split("?", 1)[0]

    if ":" in host_port:
        host, port = host_port.rsplit(":", 1)
        port = int(port)
    else:
        host, port = host_port, 3306

    return {
        "host": host,
        "port": port,
        "user": user,
        "password": unquote(password),
        "database": database,
    }


def pymysql_connect(
    *,
    read_timeout: int | None = None,
    write_timeout: int | None = None,
    connect_timeout: int | None = None,
) -> pymysql.connections.Connection:
    cfg = parse_database_url()
    return pymysql.connect(
        host=cfg["host"],
        port=cfg["port"],
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
        charset="utf8mb4",
        autocommit=False,
        connect_timeout=connect_timeout if connect_timeout is not None else settings.db_connect_timeout,
        read_timeout=read_timeout if read_timeout is not None else settings.db_read_timeout,
        write_timeout=write_timeout if write_timeout is not None else settings.db_write_timeout,
    )


def pymysql_migration_connect() -> pymysql.connections.Connection:
    """DDL 迁移专用连接（更长 read/write 超时）。"""
    return pymysql_connect(
        read_timeout=settings.db_migration_read_timeout,
        write_timeout=settings.db_migration_write_timeout,
        connect_timeout=max(settings.db_connect_timeout, 30),
    )
