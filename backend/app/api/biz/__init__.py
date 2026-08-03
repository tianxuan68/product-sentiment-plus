from fastapi import APIRouter

from app.api.biz.category import router as category_router
from app.api.biz.causal import router as causal_router
from app.api.biz.dashboard import router as dashboard_router
from app.api.biz.keyword import router as keyword_router
from app.api.biz.product import router as product_router
from app.api.biz.review import router as review_router

biz_router = APIRouter()
biz_router.include_router(category_router)
biz_router.include_router(product_router)
biz_router.include_router(review_router)
biz_router.include_router(keyword_router)
biz_router.include_router(dashboard_router)
biz_router.include_router(causal_router)
