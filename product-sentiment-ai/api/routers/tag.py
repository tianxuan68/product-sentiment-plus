"""
案例:
    动态打标接口：批量刷表 + 单条打标
"""

# 导包
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.schemas import JobResp, TagPredictReq, TagPredictResp, TagRunReq
from api.services import tag_service

router = APIRouter(prefix="/api/tag", tags=["动态打标"])


# 1. 跑动态打标
@router.post("/run", response_model=JobResp, summary="跑动态打标 → product_tags")
def run_tagging(body: TagRunReq | None = None):
    req = body or TagRunReq()
    job_id = tag_service.start_tagging(
        min_count=req.min_count, top_k=req.top_k, mode=req.mode
    )
    print(f'动态打标任务: {job_id} mode={req.mode}')
    return JobResp(
        ok=True,
        job_id=job_id,
        status="pending",
        message=f"已启动动态打标 mode={req.mode}，完成后查 /api/products/{{product_id}}/tags",
    )


# 2. 单条打标：默认标准短标签（分层 BERT）
@router.post("/one", response_model=TagPredictResp, summary="单条评论打标（多标签）")
def tag_one(body: TagPredictReq):
    try:
        return tag_service.predict_tags(
            body.text,
            body.product_id,
            method=body.method,
            category=body.category,
            product_name=body.product_name,
        )
    except FileNotFoundError as e:
        raise HTTPException(503, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
