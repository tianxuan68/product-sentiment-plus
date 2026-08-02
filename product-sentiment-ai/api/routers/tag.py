"""
案例:
    动态打标接口
"""

# 导包
from __future__ import annotations

from fastapi import APIRouter

from api.schemas import JobResp, TagRunReq
from api.services import tag_service

router = APIRouter(prefix="/api/tag", tags=["动态打标"])


# 1. 跑动态打标
@router.post("/run", response_model=JobResp, summary="跑动态打标 → product_tags")
def run_tagging(body: TagRunReq | None = None):
    req = body or TagRunReq()
    # 参1: min_count 最少提及次数  参2: top_k 每商品最多标签数
    job_id = tag_service.start_tagging(min_count=req.min_count, top_k=req.top_k)
    print(f'动态打标任务: {job_id}')
    return JobResp(
        ok=True,
        job_id=job_id,
        status="pending",
        message="已启动动态打标，完成后查 /api/products/{product_id}/tags",
    )
