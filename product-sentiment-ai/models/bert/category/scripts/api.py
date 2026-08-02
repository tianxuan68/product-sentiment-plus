"""类目 BERT 预测 API（FastAPI），供前端调用。

启动（在本 scripts 目录）:
  uvicorn api:app --host 0.0.0.0 --port 8101 --reload

文档:
  http://127.0.0.1:8101/docs
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import get_aspect_map, list_trainable_categories, load_config, resolve_path
from predict_fun import predict_batch, predict_fun
from train import safe_subdir

app = FastAPI(
    title="category-bert-api",
    version="0.1.0",
    description="类目专属多属性情感预测（1/0/null）",
)

# 前端本地开发跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PredictRequest(BaseModel):
    category: str = Field(..., description="品类，与训练一致，如 服饰服装")
    text: str = Field(..., min_length=1, description="评论文本")


class BatchPredictRequest(BaseModel):
    items: list[PredictRequest] = Field(..., min_length=1, description="批量预测列表")


class BatchPredictResponse(BaseModel):
    results: list[dict[str, Any]]


class CategoriesResponse(BaseModel):
    categories: dict[str, list[str]]
    ready: dict[str, bool]


def _checkpoint_ready(category: str) -> bool:
    cfg = load_config()
    ckpt = resolve_path(cfg["output_dir"]) / safe_subdir(category) / "best"
    return ckpt.exists() and (ckpt / "aspect_heads.pt").exists()


@app.get("/")
def root():
    return {
        "service": "category-bert-api",
        "docs": "/docs",
        "health": "/health",
        "predict": "POST /api/category/predict",
        "batch": "POST /api/category/predict/batch",
        "categories": "GET /api/category/list",
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/category/list", response_model=CategoriesResponse)
def list_categories():
    """返回品类→英文属性列表，以及本地是否已有该品类权重。"""
    cfg = load_config()
    cats = list_trainable_categories(cfg)
    mapping = {c: list(get_aspect_map(cfg, c).keys()) for c in cats}
    ready = {c: _checkpoint_ready(c) for c in cats}
    return CategoriesResponse(categories=mapping, ready=ready)


@app.post("/api/category/predict")
def predict_one(body: PredictRequest) -> dict[str, Any]:
    """
    单条预测（响应体即宽表 JSON，方便前端直接用）。

    请求:
      {"category": "服饰服装", "text": "面料很软，版型偏大"}
    响应:
      {"category":"服饰服装","text":"...","size":null,"fabric":1,"fit":0,...}
    """
    if not _checkpoint_ready(body.category):
        raise HTTPException(
            status_code=404,
            detail=f"未找到品类权重，请先训练: {body.category}",
        )
    try:
        return predict_fun({"category": body.category, "text": body.text})
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"未知品类或配置错误: {e}") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/category/predict/batch", response_model=BatchPredictResponse)
def predict_many(body: BatchPredictRequest):
    """批量预测，items 内可混多个品类。"""
    missing = sorted({x.category for x in body.items if not _checkpoint_ready(x.category)})
    if missing:
        raise HTTPException(
            status_code=404,
            detail=f"以下品类尚未训练权重: {missing}",
        )
    try:
        results = predict_batch(
            [{"category": x.category, "text": x.text} for x in body.items]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return BatchPredictResponse(results=results)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="0.0.0.0", port=8101, reload=True)
