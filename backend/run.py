import os
from pathlib import Path

import uvicorn
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent
load_dotenv(_ROOT / ".env")
load_dotenv(_ROOT / ".env.local", override=True)

if __name__ == "__main__":
    """
    启动命令：uvicorn app.main:app --host 0.0.0.0 --port 8005 --reload
    """
    reload = os.getenv("DEV_RELOAD", "false").lower() in ("1", "true", "yes")
    # Windows + 远程 MySQL：reload=True 会频繁重启子进程，远端易重置连接(WinError 10054)
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8005"))
    uvicorn.run("app.main:app", host=host, port=port, reload=reload)
