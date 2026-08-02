"""
案例:
    前端 Insight 页专用接口（字段名对齐 front/src/api/sentiment.ts）
"""

# 导包
from fastapi import APIRouter, HTTPException

from api.schemas import FrontPredictReq, FrontPredictResp, OkResp
from api.services import front_predict_service

router = APIRouter(prefix="/api/front", tags=["前端聚合"])


@router.post("/predict", response_model=FrontPredictResp, summary="Insight页：情绪+关键词")
def front_predict(body: FrontPredictReq):
    try:
        product = body.product.model_dump() if body.product else None
        return front_predict_service.predict_for_front(
            content=body.content,
            product_id=body.productId,
            product=product,
        )
    except FileNotFoundError as e:
        raise HTTPException(503, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/products", response_model=OkResp, summary="Insight页：保存商品草稿（占位）")
def front_save_product(body: dict | None = None):
    print(f'前端商品草稿已接收: {body}')
    return OkResp(ok=True, message="商品信息已保存", data=body or {})
