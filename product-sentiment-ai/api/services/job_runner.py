"""
案例:
    后台任务运行器：把「跑脚本」和「查状态」拆开。

大白话:
    训练很慢，不能堵在 HTTP 请求里；起个线程跑，前端拿 job_id 来轮询。
"""

# 导包
import subprocess
import sys
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

# 1. 任务对象
@dataclass
class Job:
    job_id: str
    command: list
    status: str = "pending"  # pending/running/success/failed
    returncode: Optional[int] = None
    stdout: str = ""
    error: str = ""
    started_at: str = ""
    finished_at: str = ""
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)


# 2. 内存任务表（进程内有效；重启 API 会清空）
_JOBS = {}
_JOBS_LOCK = threading.Lock()


# 3. 定义函数, 启动后台任务
def start_job(command, cwd=None):
    job_id = uuid.uuid4().hex[:12]
    job = Job(job_id=job_id, command=command, status="pending")
    with _JOBS_LOCK:
        _JOBS[job_id] = job

    print(f'启动任务 job_id={job_id} cmd={command}')
    thread = threading.Thread(
        target=_run,
        args=(job, cwd or "."),
        daemon=True,
    )
    thread.start()
    return job_id


# 4. 定义函数, 查任务 / 列表 / 注册
def get_job(job_id):
    with _JOBS_LOCK:
        return _JOBS.get(job_id)


def list_jobs():
    with _JOBS_LOCK:
        return list(_JOBS.values())


def register_job(job):
    with _JOBS_LOCK:
        _JOBS[job.job_id] = job


# 5. 定义函数, 线程里真正执行命令
def _run(job, cwd):
    job.status = "running"
    job.started_at = datetime.now().isoformat(timespec="seconds")
    try:
        proc = subprocess.run(
            job.command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
        job.returncode = proc.returncode
        job.stdout = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode == 0:
            job.status = "success"
            print(f'任务成功 job_id={job.job_id}')
        else:
            job.status = "failed"
            job.error = f"returncode={proc.returncode}"
            print(f'任务失败 job_id={job.job_id} {job.error}')
    except Exception as e:
        job.status = "failed"
        job.error = str(e)
        print(f'任务异常 job_id={job.job_id} err={e}')
    finally:
        job.finished_at = datetime.now().isoformat(timespec="seconds")


# 6. 定义函数, 拼 python 命令（跑 .py 文件）
def python_cmd(script, *args):
    return [sys.executable, str(script), *args]


# 7. 定义函数, 拼 python -m 模块命令（包导包）
def python_module(module, *args):
    return [sys.executable, "-m", module, *args]
