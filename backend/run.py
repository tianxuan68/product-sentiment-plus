"""
启动后端（请在 backend 目录下运行）:
    python run.py
"""

# 导包
import os

import uvicorn
from dotenv import load_dotenv


def main():
    # 读环境变量（相对当前工作目录）
    load_dotenv(".env")
    load_dotenv(".env.local", override=True)

    reload = os.getenv("DEV_RELOAD", "false").lower() in ("1", "true", "yes")
    # Windows + 远程 MySQL：reload=True 会频繁重启子进程，远端易重置连接(WinError 10054)
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8005"))
    uvicorn.run("app.main:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    main()
