"""
案例:
    数据相关业务：准备评论 / 校验。
"""

# 导包
import subprocess
import sys
import uuid
from datetime import datetime

from api.services import job_runner


# 1. 只跑 prepare
def start_prepare():
    script = "./data/scripts/preprocess/prepare_reviews.py"
    return job_runner.start_job(job_runner.python_cmd(script))


# 2. 只跑 verify
def start_verify():
    script = "./data/scripts/preprocess/verify_processed.py"
    return job_runner.start_job(job_runner.python_cmd(script))


# 3. 一条后台任务：prepare → verify
def start_prepare_pipeline():
    job_id = uuid.uuid4().hex[:12]
    job = job_runner.Job(
        job_id=job_id,
        command=["pipeline", "prepare+verify"],
        status="pending",
    )
    job_runner.register_job(job)
    print(f'数据流水线任务: {job_id}')

    def _run():
        job.status = "running"
        job.started_at = datetime.now().isoformat(timespec="seconds")
        logs = []
        try:
            scripts = [
                "./data/scripts/preprocess/prepare_reviews.py",
                "./data/scripts/preprocess/verify_processed.py",
            ]
            for script in scripts:
                cmd = [sys.executable, script]
                logs.append(">>> " + " ".join(cmd))
                print(f'执行: {cmd}')
                proc = subprocess.run(
                    cmd,
                    cwd=".",
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="ignore",
                )
                logs.append(proc.stdout or "")
                logs.append(proc.stderr or "")
                if proc.returncode != 0:
                    job.returncode = proc.returncode
                    job.status = "failed"
                    job.error = f"{script} failed"
                    job.stdout = "\n".join(logs)
                    return
            job.returncode = 0
            job.status = "success"
            job.stdout = "\n".join(logs)
            print(f'数据流水线成功 job_id={job_id}')
        except Exception as e:
            job.status = "failed"
            job.error = str(e)
            job.stdout = "\n".join(logs)
            print(f'数据流水线异常 job_id={job_id} err={e}')
        finally:
            job.finished_at = datetime.now().isoformat(timespec="seconds")

    import threading
    threading.Thread(target=_run, daemon=True).start()
    return job_id
