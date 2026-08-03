"""
案例:
    拼多多式动态打标：评论 → review_tags → 按商品聚合 product_tags。

大白话:
    默认标准短标签（规则词表）；也可 --mode open 走原文短语聚合。

用法:
    python dynamic_tagging.py
    python dynamic_tagging.py --mode rules --min-count 2 --top-k 20
    python dynamic_tagging.py --mode open
"""

# 导包
import argparse
import os
import sys

import pandas as pd

# 同目录规则 + 项目根上的开放抽取
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from tag_rules import build_vocab_rows, extract_tags  # noqa: E402


def _extract_hits(text, category, mode):
    if mode == "rules":
        return [
            {"aspect": a, "tag": t, "polarity": p}
            for a, t, p in extract_tags(text, category=category)
        ]
    # open：从 api 包导入开放抽取
    from api.services.open_tag_extract import extract_open_tags

    return extract_open_tags(text)


def run(min_count, top_k, max_reviews=None, mode="rules"):
    mode = (mode or "rules").strip().lower()
    if mode not in {"open", "rules"}:
        raise ValueError("mode 只能是 open | rules")

    reviews_csv = "./data/processed/reviews.csv"
    vocab_csv = "./data/vocab/category_tag_vocab.csv"
    review_tags_csv = "./data/processed/review_tags.csv"
    product_tags_csv = "./data/processed/product_tags.csv"
    annotated_tags_csv = "./data/annotated/review_tags.csv"

    if not os.path.exists(reviews_csv):
        raise FileNotFoundError(f"缺少 {reviews_csv}，请先 prepare_reviews.py")

    print('-' * 50)
    print(f'动态打标 mode={mode}')
    print('-' * 50)

    df = pd.read_csv(reviews_csv, encoding="utf-8-sig")
    if max_reviews:
        df = df.head(max_reviews).copy()
        print(f"调试模式: 仅处理前 {len(df)} 条")

    tag_rows = []
    for row in df.itertuples(index=False):
        text = str(getattr(row, "sentence", "") or "")
        category = str(getattr(row, "category", "") or "")
        hits = _extract_hits(text, category, mode)
        for h in hits:
            tag_rows.append(
                {
                    "review_id": row.review_id,
                    "product_id": row.product_id,
                    "category": row.category,
                    "aspect": h.get("aspect") or "",
                    "opinion": h.get("tag") or "",
                    "polarity": h.get("polarity") or "neutral",
                    "tag": h.get("tag") or "",
                }
            )

    tag_cols = [
        "review_id",
        "product_id",
        "category",
        "aspect",
        "opinion",
        "polarity",
        "tag",
    ]
    product_cols = ["product_id", "category", "tag", "polarity", "count", "ratio"]
    review_tags = pd.DataFrame(tag_rows, columns=tag_cols)
    print(
        f"评论标签明细: {len(review_tags)} 条 / "
        f"覆盖评论 {review_tags['review_id'].nunique() if len(review_tags) else 0}"
    )

    if review_tags.empty:
        print("警告: 未抽到任何标签，将写出空表（检查规则或数据）")
        product_tags = pd.DataFrame(columns=product_cols)
    else:
        review_cnt = df.groupby("product_id").size().to_dict()
        cat_map = (
            df.drop_duplicates("product_id")
            .set_index("product_id")["category"]
            .to_dict()
        )
        grouped = (
            review_tags.groupby(["product_id", "tag", "polarity"], as_index=False)
            .size()
            .rename(columns={"size": "count"})
        )
        grouped["category"] = grouped["product_id"].map(cat_map)
        grouped["ratio"] = grouped.apply(
            lambda r: r["count"] / max(review_cnt.get(r["product_id"], 1), 1),
            axis=1,
        )
        grouped = grouped[grouped["count"] >= min_count].copy()
        grouped = grouped.sort_values(
            ["product_id", "count", "ratio"], ascending=[True, False, False]
        )
        grouped["rank"] = grouped.groupby("product_id").cumcount() + 1
        grouped = grouped[grouped["rank"] <= top_k].drop(columns=["rank"])
        product_tags = grouped[product_cols].reset_index(drop=True)

    os.makedirs("./data/vocab", exist_ok=True)
    os.makedirs("./data/processed", exist_ok=True)
    os.makedirs("./data/annotated", exist_ok=True)

    def safe_to_csv(df, path):
        try:
            df.to_csv(path, index=False, encoding="utf-8-sig")
            return path
        except PermissionError:
            alt = path.replace(".csv", ".new.csv")
            df.to_csv(alt, index=False, encoding="utf-8-sig")
            print(f'警告: {path} 被占用，已改写到 {alt}，请关闭占用后替换')
            return alt

    # open 模式词表从本批标签动态汇总；rules 仍写静态规矩本
    if mode == "open" and len(review_tags):
        vocab = (
            review_tags[["category", "aspect", "tag", "polarity"]]
            .drop_duplicates()
            .assign(scope="open")
        )
        safe_to_csv(vocab, vocab_csv)
    else:
        safe_to_csv(pd.DataFrame(build_vocab_rows()), vocab_csv)

    safe_to_csv(review_tags, review_tags_csv)
    safe_to_csv(review_tags, annotated_tags_csv)
    safe_to_csv(product_tags, product_tags_csv)

    print(f'词表: {vocab_csv}')
    print(f'评论标签: {review_tags_csv}')
    print(f'商品标签墙: {product_tags_csv} ({len(product_tags)} 行)')
    if len(product_tags):
        top_products = product_tags.groupby("product_id")["count"].sum().nlargest(5)
        print(f'标签提及最多的商品(top5):')
        print(top_products)
        sample_pid = top_products.index[0]
        print(f'\n示例商品标签墙 {sample_pid}:')
        print(product_tags[product_tags["product_id"] == sample_pid].head(10))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="rules", choices=["open", "rules"])
    parser.add_argument("--min-count", type=int, default=1)
    parser.add_argument("--top-k", type=int, default=15)
    parser.add_argument("--max-reviews", type=int, default=None)
    args = parser.parse_args()
    run(args.min_count, args.top_k, args.max_reviews, mode=args.mode)


if __name__ == "__main__":
    main()
