"""
校验 processed 产出是否符合加强清洗规则。

用法：
  python verify_processed.py
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ROOT / "sources"
PROCESSED = ROOT / "processed"

SOURCE_FILES = [
    SOURCES / "训练集.csv",
    SOURCES / "测试集.csv",
    SOURCES / "商品信息.csv",
    SOURCES / "商品类别列表.csv",
]

PROCESSED_FILES = [
    PROCESSED / "reviews.csv",
    PROCESSED / "reviews_train.csv",
    PROCESSED / "reviews_val.csv",
    PROCESSED / "reviews_test.csv",
]

_RE_CN = re.compile(r"[\u4e00-\u9fff]")
_RE_HTML = re.compile(r"<[^>]+>")
_RE_URL = re.compile(r"https?://\S+|www\.\S+", re.I)


def check_sources_intact() -> None:
    print("[1] sources 完整性")
    for p in SOURCE_FILES:
        assert p.exists(), f"缺少源文件: {p}"
        assert p.stat().st_size > 0, f"源文件为空: {p}"
        df = pd.read_csv(p, nrows=2, encoding="utf-8")
        assert len(df.columns) > 0, f"源文件无法解析: {p}"
        print(f"  OK {p.name} ({p.stat().st_size} bytes)")


def check_processed() -> None:
    print("[2] processed 产出与清洗质量")
    for p in PROCESSED_FILES:
        assert p.exists(), f"缺少产出: {p} ，请先运行 prepare_reviews.py"
        print(f"  OK {p.name}")

    reviews = pd.read_csv(PROCESSED / "reviews.csv", encoding="utf-8-sig")
    train = pd.read_csv(PROCESSED / "reviews_train.csv", encoding="utf-8-sig")
    val = pd.read_csv(PROCESSED / "reviews_val.csv", encoding="utf-8-sig")
    test = pd.read_csv(PROCESSED / "reviews_test.csv", encoding="utf-8-sig")

    need = {"review_id", "product_id", "category", "sentence", "sentiment", "rating"}
    assert need.issubset(reviews.columns), f"reviews 缺列: {need - set(reviews.columns)}"
    assert reviews["review_id"].is_unique
    assert reviews["sentence"].is_unique, "sentence 未去重"
    assert set(reviews["sentiment"].unique()) <= {0, 1}
    assert len(train) + len(val) == len(reviews)
    assert set(train["review_id"]).isdisjoint(set(val["review_id"]))
    assert "sentiment" not in test.columns

    # 中性分必须已剔除
    mid = ((reviews["rating"] > 2) & (reviews["rating"] < 4)).sum()
    assert mid == 0, f"仍有中性评分: {mid}"

    s = reviews["sentence"].astype(str)
    assert (s.str.len() >= 6).all(), "存在过短句"
    assert s.map(lambda x: len(_RE_CN.findall(x)) >= 2).all(), "存在无中文句"
    assert not s.str.contains(_RE_HTML).any(), "仍含 HTML"
    assert not s.str.contains(_RE_URL).any(), "仍含 URL"

    src_n = sum(1 for _ in open(SOURCES / "训练集.csv", encoding="utf-8")) - 1
    assert len(reviews) <= src_n, "processed 行数不应超过源训练集"
    # 丢掉中性分 + 文本清洗后通常保留约 85%~90%；下限防过度清洗
    assert len(reviews) >= int(src_n * 0.70), f"清洗掉过多: {len(reviews)}/{src_n}"
    assert len(reviews) >= 1000, f"样本量过少: {len(reviews)}"

    print(f"  全量={len(reviews)} train={len(train)} val={len(val)} test={len(test)}")
    print(f"  好评率={reviews['sentiment'].mean():.4f} 品类数={reviews['category'].nunique()}")
    print(f"  评分分布: {reviews['rating'].value_counts().sort_index().to_dict()}")


def main() -> None:
    print("=" * 50)
    print("verify_processed")
    print("=" * 50)
    check_sources_intact()
    check_processed()
    print("=" * 50)
    print("全部校验通过")
    print("=" * 50)


if __name__ == "__main__":
    main()
