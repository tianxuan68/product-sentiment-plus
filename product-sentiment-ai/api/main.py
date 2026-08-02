"""
案例:
    FastAPI 启动入口：只负责「组装路由」，不写具体业务。

大白话:
    路由层收请求 → 业务层干活 → 这里只是把几根水管接起来。

启动:
    cd product-sentiment-ai
    python -m uvicorn api.main:app --reload --port 8001

文档:
    http://127.0.0.1:8001/docs
"""

# 导包
from fastapi import FastAPI                                          # Web框架
from fastapi.middleware.cors import CORSMiddleware                   # 跨域

from api.routers import data, health, jobs, predict, products, tag, train


# 1. 创建应用
app = FastAPI(
    title="product-sentiment-ai API",
    description=(
        "拼多多式商品动态标签 + 情感分类\n\n"
        "建议调用顺序:\n"
        "1) POST /api/data/prepare\n"
        "2) POST /api/tag/run\n"
        "3) POST /api/train/start\n"
        "4) POST /api/predict/one\n"
        "5) GET  /api/products/{product_id}/tags"
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

# 3. 挂路由：一个文件管一类事
app.include_router(health.router)
app.include_router(jobs.router)
app.include_router(data.router)
app.include_router(tag.router)
app.include_router(train.router)
app.include_router(predict.router)
app.include_router(products.router)


# 4. 首页提示
@app.get("/")
def root():
    print(f'访问首页: docs=/docs health=/health')
    return {
        "ok": True,
        "message": "product-sentiment-ai API",
        "docs": "/docs",
        "health": "/health",
    }
