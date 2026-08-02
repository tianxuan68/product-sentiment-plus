"""
前端 Insight 页接口：/jeecg-boot/sentiment/*
字段对齐 front/src/api/sentiment.ts，不改前端。
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.schemas.response import Result
from app.services import sentiment_service

router = APIRouter(prefix="/sentiment", tags=["评论分析"])


class ProductDraft(BaseModel):
    name: str = ""
    category: str = ""
    rating: str = ""
    note: str = ""


class PredictBody(BaseModel):
    content: str = Field(..., min_length=1)
    productId: Optional[str] = None
    product: Optional[ProductDraft] = None


@router.post("/predict")
def predict(body: PredictBody):
    try:
        product = body.product.model_dump() if body.product else None
        data = sentiment_service.predict(
            content=body.content,
            product_id=body.productId,
            product=product,
        )
        return Result.ok(data, "分析完成")
    except ValueError as exc:
        return Result.error(str(exc), 400)
    except Exception as exc:
        return Result.error(f"分析失败: {exc}", 500)


@router.post("/products")
def save_product(body: ProductDraft | dict[str, Any]):
    if isinstance(body, ProductDraft):
        payload = body.model_dump()
    else:
        payload = dict(body or {})
    data = sentiment_service.save_product_draft(payload)
    return Result.ok(data, "商品信息已保存")
