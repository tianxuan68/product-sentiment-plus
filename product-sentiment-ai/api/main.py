"""
案例:
    FastAPI 启动入口：只负责「组装路由」，不写具体业务。

大白话:
    路由层收请求 → 业务层干活 → 这里只是把几根水管接起来。
    预测/打标等重依赖路由缺失时跳过，保证因果等轻量接口仍可启动。

启动:
    cd product-sentiment-ai
    python -m uvicorn api.main:app --reload --port 8001

文档:
    http://127.0.0.1:8001/docs
"""

# 导包
import importlib
import traceback

from fastapi import FastAPI                                          # Web框架
from fastapi.middleware.cors import CORSMiddleware                   # 跨域


# 1. 创建应用
app = FastAPI(
    title="product-sentiment-ai API",
    description=(
        "拼多多式商品动态标签 + 情感分类\n\n"
        "建议调用顺序:\n"
        "1) POST /api/data/prepare\n"
        "2) POST /api/tag/run {\"mode\":\"rules\"}  ← 批量标准短标签→商品标签墙\n"
        "3) POST /api/tag/one                     ← 单条打标（默认 model 标准短标签）\n"
        "4) POST /api/train/start {\"model\":\"tagging_hier\"}  ← 可选：分层BERT\n"
        "5) POST /api/predict/one      ← 好评/差评二分类\n"
        "6) POST /api/front/predict    ← 前端Insight（keywords 走标准短标签）\n"
        "7) GET  /api/products/{product_id}/tags\n"
        "8) POST /api/causal/prepare   ← 评论→因果表\n"
        "9) POST /api/causal/analyze   ← 按类目因果分析"
    ),
    version="1.0.0",
)

# 2. 跨域（前端随便调）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_loaded_routers: list[str] = []
_skipped_routers: dict[str, str] = {}


def _include(module_name: str) -> bool:
    """挂载路由；依赖缺失时跳过，不拖垮整站。"""
    try:
        mod = importlib.import_module(f"api.routers.{module_name}")
        app.include_router(mod.router)
        _loaded_routers.append(module_name)
        print(f"router ok: {module_name}")
        return True
    except Exception as exc:
        _skipped_routers[module_name] = f"{type(exc).__name__}: {exc}"
        print(f"router skip: {module_name} -> {exc}")
        traceback.print_exc()
        return False


# 3. 挂路由：轻量优先，重依赖可选
for name in ("health", "jobs", "data", "causal", "tag", "train", "predict", "products", "front"):
    _include(name)


# 4. 首页提示
@app.get("/")
def root():
    print(f'访问首页: docs=/docs health=/health')
    return {
        "ok": True,
        "message": "product-sentiment-ai API",
        "docs": "/docs",
        "health": "/health",
        "causal": ["/api/causal/prepare", "/api/causal/analyze"],
        "routers": _loaded_routers,
        "skipped": _skipped_routers,
    }
