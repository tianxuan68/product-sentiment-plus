"""
启动后端:
    python run.py
也可绝对路径启动（会自动切到 backend 目录读 .env）。
"""

# 导包
import os
import sys
from pathlib import Path

# 固定工作目录到 backend/，避免 IDE 绝对路径启动时找不到 .env / 相对路径资源
_BACKEND_DIR = Path(__file__).resolve().parent
os.chdir(_BACKEND_DIR)
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

try:
    import uvicorn
    from dotenv import load_dotenv
except ModuleNotFoundError as exc:
    missing = getattr(exc, "name", None) or str(exc)
    print(
        f"缺少依赖: {missing}\n"
        f"请先安装: pip install -r {_BACKEND_DIR.parent / 'requirements.txt'}",
        file=sys.stderr,
    )
    raise SystemExit(1) from exc


def main():
    load_dotenv(".env")
    load_dotenv(".env.local", override=True)

    reload = os.getenv("DEV_RELOAD", "false").lower() in ("1", "true", "yes")
    # Windows + 远程 MySQL：reload=True 会频繁重启子进程，远端易重置连接(WinError 10054)
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8005"))
    uvicorn.run("app.main:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    main()
