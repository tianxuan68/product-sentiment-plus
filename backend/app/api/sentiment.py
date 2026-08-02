"""
前端 Insight 页接口：/jeecg-boot/sentiment/*
字段对齐 front/src/api/sentiment.ts，不改前端。
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_optional_user
from app.db.session import get_db
from app.models.entities import SysUser
from app.schemas.response import Result
from app.services import sentiment_service

router = APIRouter(prefix="/sentiment", tags=["评论分析"])


class ProductDraft(BaseModel):
    name: str = ""
    category: str = ""
    rating: str = ""
    note: str = ""
    # 扩展字段（前端可不传）
    categoryId: Optional[str] = None
    brand: Optional[str] = None
    sku: Optional[str] = None
    price: Optional[float] = None
    originalPrice: Optional[float] = None
    coverUrl: Optional[str] = None
    description: Optional[str] = None
    unit: Optional[str] = None
    stock: Optional[int] = None
    currency: Optional[str] = None


class PredictBody(BaseModel):
    content: str = Field(..., min_length=1)
    productId: Optional[str] = None
    product: Optional[ProductDraft] = None


@router.post("/predict")
def predict(
    body: PredictBody,
    db: Session = Depends(get_db),
    user: Optional[SysUser] = Depends(get_optional_user),
):
    try:
        product = body.product.model_dump(exclude_none=True) if body.product else None
        data = sentiment_service.predict_and_save(
            db,
            content=body.content,
            product_id=body.productId,
            product=product,
            user_id=user.id if user else None,
            username=user.username if user else None,
            persist_product=False,
        )
        return Result.ok(data, "分析完成")
    except ValueError as exc:
        return Result.error(str(exc), 400)
    except Exception as exc:
        return Result.error(f"分析失败: {exc}", 500)


@router.post("/products")
def save_product(
    body: ProductDraft | dict[str, Any],
    db: Session = Depends(get_db),
    user: Optional[SysUser] = Depends(get_optional_user),
):
    if isinstance(body, ProductDraft):
        payload = body.model_dump(exclude_none=True)
    else:
        payload = dict(body or {})
    try:
        data = sentiment_service.save_product_draft(
            db,
            payload,
            user_id=user.id if user else None,
            username=user.username if user else None,
        )
        return Result.ok(data, "商品信息已保存")
    except ValueError as exc:
        return Result.error(str(exc), 400)
    except Exception as exc:
        return Result.error(f"保存失败: {exc}", 500)
