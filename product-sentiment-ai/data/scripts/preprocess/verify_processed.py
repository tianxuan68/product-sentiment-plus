"""
案例:
    校验 processed 产出是否符合加强清洗规则。

用法（在 product-sentiment-ai 目录下）:
    python data/scripts/preprocess/verify_processed.py
"""

# 导包
import os
import re

import pandas as pd

_RE_CN = re.compile(r"[\u4e00-\u9fff]")
_RE_HTML = re.compile(r"<[^>]+>")
_RE_URL = re.compile(r"https?://\S+|www\.\S+", re.I)


def check_sources_intact():
    print(f'[1] sources 完整性')
    source_files = [
        "./data/sources/训练集.csv",
        "./data/sources/测试集.csv",
        "./data/sources/商品信息.csv",
        "./data/sources/商品类别列表.csv",
    ]
    for p in source_files:
        assert os.path.exists(p), f"缺少源文件: {p}"
        assert os.path.getsize(p) > 0, f"源文件为空: {p}"
        df = pd.read_csv(p, nrows=2, encoding="utf-8")
        assert len(df.columns) > 0, f"源文件无法解析: {p}"
        print(f'  OK {os.path.basename(p)} ({os.path.getsize(p)} bytes)')


def check_processed():
    print(f'[2] processed 产出与清洗质量')
    processed_files = [
        "./data/processed/reviews.csv",
        "./data/processed/reviews_train.csv",
        "./data/processed/reviews_val.csv",
        "./data/processed/reviews_test.csv",
    ]
    for p in processed_files:
        assert os.path.exists(p), f"缺少产出: {p} ，请先运行 prepare_reviews.py"
        print(f'  OK {os.path.basename(p)}')

    reviews = pd.read_csv("./data/processed/reviews.csv", encoding="utf-8-sig")
    train = pd.read_csv("./data/processed/reviews_train.csv", encoding="utf-8-sig")
    val = pd.read_csv("./data/processed/reviews_val.csv", encoding="utf-8-sig")
    test = pd.read_csv("./data/processed/reviews_test.csv", encoding="utf-8-sig")

    need = {"review_id", "product_id", "category", "sentence", "sentiment", "rating"}
    assert need.issubset(reviews.columns), f"reviews 缺列: {need - set(reviews.columns)}"
    assert reviews["review_id"].is_unique
    assert reviews["sentence"].is_unique, "sentence 未去重"
    assert set(reviews["sentiment"].unique()) <= {0, 1}
    assert len(train) + len(val) == len(reviews)
    assert set(train["review_id"]).isdisjoint(set(val["review_id"]))
    assert "sentiment" not in test.columns

    mid = ((reviews["rating"] > 2) & (reviews["rating"] < 4)).sum()
    assert mid == 0, f"仍有中性评分: {mid}"

    s = reviews["sentence"].astype(str)
    assert (s.str.len() >= 6).all(), "存在过短句"
    assert s.map(lambda x: len(_RE_CN.findall(x)) >= 2).all(), "存在无中文句"
    assert not s.str.contains(_RE_HTML).any(), "仍含 HTML"
    assert not s.str.contains(_RE_URL).any(), "仍含 URL"

    src_n = sum(1 for _ in open("./data/sources/训练集.csv", encoding="utf-8")) - 1
    assert len(reviews) <= src_n, "processed 行数不应超过源训练集"
    assert len(reviews) >= int(src_n * 0.70), f"清洗掉过多: {len(reviews)}/{src_n}"
    assert len(reviews) >= 1000, f"样本量过少: {len(reviews)}"

    print(f'  全量={len(reviews)} train={len(train)} val={len(val)} test={len(test)}')
    print(f'  好评率={reviews["sentiment"].mean():.4f} 品类数={reviews["category"].nunique()}')
    print(f'  评分分布: {reviews["rating"].value_counts().sort_index().to_dict()}')


def main():
    print('-' * 50)
    print(f'verify_processed')
    print('-' * 50)
    check_sources_intact()
    check_processed()
    print('-' * 50)
    print(f'全部校验通过')
    print('-' * 50)


if __name__ == "__main__":
    # 1. 跑校验
    main()
