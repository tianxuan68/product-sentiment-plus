"""
案例:
    健康检查：看服务活着没、模型文件在不在。
"""

# 导包
import os

from fastapi import APIRouter

router = APIRouter(tags=["健康检查"])


@router.get("/health")
def health():
    print(f'health 检查')
    return {
        "ok": True,
        "has_fasttext": os.path.exists("./models/fasttext/model/fasttext_style.joblib"),
        "has_baseline": os.path.exists("./models/baseline/model/baseline.joblib"),
        "has_bert": os.path.exists("./models/bert/common/model/bert_all"),
        "has_product_tags": os.path.exists("./data/processed/product_tags.csv"),
    }
