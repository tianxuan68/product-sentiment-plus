"""
案例:
    商品标签墙查询业务
"""

# 导包
import os

import pandas as pd


# 1. 读标签表
def _load_tags():
    product_tags = "./data/processed/product_tags.csv"
    if not os.path.exists(product_tags):
        raise FileNotFoundError(
            f"缺少 {product_tags}，请先调用 /api/tag/run 或跑 dynamic_tagging.py"
        )
    return pd.read_csv(product_tags, encoding="utf-8-sig")


# 2. 查某个商品
def get_product_tags(product_id, top_k=15):
    reviews_csv = "./data/processed/reviews.csv"
    tags = _load_tags()
    sub = tags[tags["product_id"] == product_id].copy()
    if sub.empty:
        raise KeyError(f"商品无标签: {product_id}")
    sub = sub.sort_values(["count", "ratio"], ascending=False).head(top_k)

    info = {"product_id": product_id}
    if os.path.exists(reviews_csv):
        reviews = pd.read_csv(reviews_csv, encoding="utf-8-sig")
        r = reviews[reviews["product_id"] == product_id]
        if len(r):
            info["category"] = str(r.iloc[0].get("category", ""))
            info["product_name"] = str(r.iloc[0].get("product_name", ""))
            info["review_count"] = int(len(r))

    info["tags"] = sub.to_dict(orient="records")
    print(f'商品 {product_id} 标签数: {len(info["tags"])}')
    return info


# 3. 标签提及最多的商品
def top_products(limit=20):
    tags = _load_tags()
    ranking = (
        tags.groupby("product_id")["count"].sum().sort_values(ascending=False).head(limit)
    )
    return [
        {"product_id": pid, "tag_mentions": int(cnt)} for pid, cnt in ranking.items()
    ]
