"""
案例:
    因果分析路由：处理评论数据 + 按类目做因果估计。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from api.schemas import OkResp
from api.services import causal_service

router = APIRouter(prefix="/api/causal", tags=["因果分析"])


class CausalPrepareReq(BaseModel):
    reviews: List[Dict[str, Any]] = Field(default_factory=list, description="原始评论列表")


class CausalAnalyzeReq(BaseModel):
    reviews: Optional[List[Dict[str, Any]]] = Field(default=None, description="原始评论；与 prepared 二选一")
    prepared: Optional[List[Dict[str, Any]]] = Field(default=None, description="prepare 接口输出的因果表")
    categoryName: Optional[str] = Field(default=None, description="只分析该类目；空=全部类目分别估计")


@router.post("/prepare", response_model=OkResp)
def prepare(body: CausalPrepareReq):
    """处理输入评论 → 因果变量表。"""
    print(f"causal prepare reviews={len(body.reviews or [])}")
    rows = causal_service.prepare_reviews(body.reviews or [])
    return OkResp(ok=True, message=f"已处理 {len(rows)} 条", data={"rows": rows, "count": len(rows)})


@router.post("/analyze", response_model=OkResp)
def analyze(body: CausalAnalyzeReq):
    """因果分析：可先 prepare，也可直接传 reviews。按类目输出 ATE。"""
    if body.prepared is not None:
        print(f"causal analyze prepared={len(body.prepared)} category={body.categoryName}")
        data = causal_service.analyze_prepared(body.prepared, category_name=body.categoryName)
    else:
        reviews = body.reviews or []
        print(f"causal analyze reviews={len(reviews)} category={body.categoryName}")
        data = causal_service.prepare_and_analyze(reviews, category_name=body.categoryName)
    return OkResp(ok=True, message="分析完成", data=data)
