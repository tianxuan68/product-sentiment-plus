"""
案例:
    商品标签墙接口
"""

# 导包
from fastapi import APIRouter, HTTPException, Query

from api.services import product_service

router = APIRouter(prefix="/api/products", tags=["商品标签墙"])


# 1. 热门商品
@router.get("/top", summary="标签提及最多的商品")
def top_products(limit: int = Query(20, ge=1, le=100)):
    try:
        items = product_service.top_products(limit=limit)
    except FileNotFoundError as e:
        raise HTTPException(503, str(e)) from e
    print(f'热门商品条数: {len(items)}')
    return {"ok": True, "items": items}


# 2. 某个商品的标签墙
@router.get("/{product_id}/tags", summary="查某个商品的动态标签墙")
def product_tags(product_id: str, top_k: int = Query(15, ge=1, le=50)):
    try:
        data = product_service.get_product_tags(product_id, top_k=top_k)
    except FileNotFoundError as e:
        raise HTTPException(503, str(e)) from e
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    return {"ok": True, **data}
