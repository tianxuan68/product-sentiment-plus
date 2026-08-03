#!/usr/bin/env python3
"""检测 DATABASE_URL 是否可用。

请在 backend 目录下运行:
    python -m scripts.check_db
"""

# 导包
import sys
import time

from app.db.session import ping_db, warmup_db_pool
from app.core.config import settings


def main():
    print("DATABASE_URL:", settings.database_url.split("@")[-1])
    try:
        t = time.perf_counter()
        elapsed = ping_db()
        print(f"OK  ping_db 耗时 {elapsed:.2f}s（总 {time.perf_counter() - t:.2f}s）")
        t = time.perf_counter()
        warmup_db_pool()
        print(f"OK  warmup   耗时 {time.perf_counter() - t:.2f}s")
        return 0
    except Exception as exc:
        print("FAIL:", exc, file=sys.stderr)
        print(
            "\n建议：\n"
            "  1. 确认本地 MySQL 已启动，库 jeecg-boot 可访问\n"
            "  2. 复制 .env.local.example 为 .env.local，填写 DATABASE_URL\n"
            "  3. 首次初始化：python -m scripts.init_slim_db\n"
            "  4. 运行 python run.py 时本地库可设 DEV_RELOAD=true",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
