"""
案例:
    数据相关接口：清洗 / 校验
"""

# 导包
from fastapi import APIRouter

from api.schemas import JobResp
from api.services import data_service

router = APIRouter(prefix="/api/data", tags=["数据"])


# 1. 清洗评论（prepare → verify）
@router.post("/prepare", response_model=JobResp, summary="清洗评论（sources→processed）")
def prepare():
    job_id = data_service.start_prepare_pipeline()
    print(f'数据清洗任务: {job_id}')
    return JobResp(
        ok=True,
        job_id=job_id,
        status="pending",
        message="已启动：prepare_reviews → verify_processed，用 /api/jobs/{job_id} 查进度",
    )


# 2. 只跑校验
@router.post("/verify", response_model=JobResp, summary="只跑数据校验")
def verify():
    job_id = data_service.start_verify()
    return JobResp(
        ok=True,
        job_id=job_id,
        status="pending",
        message="已启动校验任务",
    )
