"""
案例:
    任务查询：训练/数据处理都是后台任务，用 job_id 查进度。
"""

# 导包
from fastapi import APIRouter, HTTPException

from api.schemas import JobStatusResp
from api.services import job_runner

router = APIRouter(prefix="/api/jobs", tags=["任务"])


# 1. 列出任务
@router.get("", summary="列出最近任务")
def list_jobs():
    jobs = job_runner.list_jobs()
    return {
        "ok": True,
        "items": [
            {
                "job_id": j.job_id,
                "status": j.status,
                "command": j.command,
                "started_at": j.started_at,
                "finished_at": j.finished_at,
            }
            for j in jobs
        ],
    }


# 2. 查单个任务
@router.get("/{job_id}", response_model=JobStatusResp, summary="查任务状态")
def get_job(job_id: str):
    job = job_runner.get_job(job_id)
    if not job:
        raise HTTPException(404, f"任务不存在: {job_id}")
    # 日志太长只回尾巴，方便看
    tail = job.stdout[-3000:] if job.stdout else ""
    return JobStatusResp(
        ok=True,
        job_id=job.job_id,
        status=job.status,
        command=job.command,
        returncode=job.returncode,
        stdout_tail=tail,
        error=job.error,
    )
