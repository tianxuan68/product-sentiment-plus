"""
案例:
    拼多多式动态打标：评论 → review_tags → 按商品聚合 product_tags。

大白话:
    规则抽「方面+观点」，再按商品数人头，挂到标签墙上。

用法:
    python dynamic_tagging.py
    python dynamic_tagging.py --min-count 2 --top-k 20
"""

# 导包
import argparse
import os
import re

import pandas as pd

# (aspect, tag, polarity, patterns)
# patterns: 命中任一即抽该标签
TAG_RULES: list[tuple[str, str, str, list[str]]] = [
    ("质量", "质量好", "positive", [r"质量好", r"品质好", r"质量不错", r"质量很棒", r"做工好", r"做工细致", r"做工精致"]),
    ("质量", "质量差", "negative", [r"质量差", r"质量不好", r"品质差", r"做工差", r"做工粗糙", r"太差了", r"垃圾"]),
    ("物流", "发货快", "positive", [r"发货快", r"物流快", r"快递快", r"送货快", r"很快就到", r"隔天到", r"第二天到"]),
    ("物流", "物流慢", "negative", [r"发货慢", r"物流慢", r"快递慢", r"等了好久", r"迟迟不到"]),
    ("包装", "包装好", "positive", [r"包装好", r"包装不错", r"包装严实", r"包装完好"]),
    ("包装", "包装差", "negative", [r"包装差", r"包装简陋", r"包装破", r"破损", r"压坏"]),
    ("价格", "性价比高", "positive", [r"性价比高", r"很划算", r"超值", r"便宜又好", r"物美价廉", r"值得买"]),
    ("价格", "价格贵", "negative", [r"价格贵", r"太贵", r"偏贵", r"不便宜", r"贵了"]),
    ("客服", "客服好", "positive", [r"客服好", r"客服不错", r"服务态度好", r"回复及时"]),
    ("客服", "客服差", "negative", [r"客服差", r"没人管", r"不回消息", r"态度差", r"售后差"]),
    ("正品", "正品放心", "positive", [r"正品", r"正版", r"官方", r"放心"]),
    ("正品", "疑似假货", "negative", [r"假货", r"假的", r"不是正品", r"盗版", r"山寨"]),
    ("外观", "外观好看", "positive", [r"好看", r"漂亮", r"美观", r"颜值高", r"很洋气"]),
    ("外观", "外观一般", "negative", [r"难看", r"不好看", r"丑"]),
    ("内容", "内容不错", "positive", [r"内容好", r"内容不错", r"写得很好", r"很有用", r"干货", r"受益"]),
    ("内容", "内容一般", "negative", [r"内容空洞", r"没什么内容", r"太浅", r"浪费钱", r"不值"]),
    ("味道", "味道不错", "positive", [r"味道好", r"味道不错", r"好吃", r"好喝", r"香"]),
    ("味道", "味道一般", "negative", [r"味道差", r"不好吃", r"难喝", r"怪怪的"]),
    ("耐用", "很耐用", "positive", [r"耐用", r"结实", r"耐用性好"]),
    ("耐用", "容易坏", "negative", [r"容易坏", r"坏了", r"用不了", r"故障", r"死机"]),
    ("尺码", "尺码合适", "positive", [r"尺码合适", r"大小合适", r"合身"]),
    ("尺码", "尺码不准", "negative", [r"尺码不准", r"偏小", r"偏大", r"建议买大", r"建议买小"]),
    ("面料", "面料不错", "positive", [r"面料好", r"面料不错", r"料子好", r"布料好"]),
    ("面料", "面料差", "negative", [r"面料差", r"料子差", r"布料差", r"廉价感"]),
    ("续航", "续航久", "positive", [r"续航久", r"续航好", r"电池耐用"]),
    ("续航", "续航差", "negative", [r"续航差", r"不耐用", r"费电"]),
    ("新鲜", "很新鲜", "positive", [r"新鲜", r"很新"]),
    ("推荐", "会回购", "positive", [r"回购", r"还会买", r"推荐购买", r"值得推荐", r"五星"]),
    ("推荐", "不推荐", "negative", [r"不推荐", r"别买", r"坑", r"后悔"]),
]


def compile_rules():
    return [
        (aspect, tag, polarity, [re.compile(p) for p in patterns])
        for aspect, tag, polarity, patterns in TAG_RULES
    ]


def extract_tags(text: str, compiled) -> list[tuple[str, str, str]]:
    hits = []
    seen = set()
    for aspect, tag, polarity, regs in compiled:
        if any(r.search(text) for r in regs):
            if tag not in seen:
                seen.add(tag)
                hits.append((aspect, tag, polarity))
    return hits


def build_vocab_rows() -> list[dict]:
    rows = []
    for aspect, tag, polarity, _ in TAG_RULES:
        rows.append(
            {
                "category": "*",
                "aspect": aspect,
                "tag": tag,
                "polarity": polarity,
            }
        )
    return rows


def run(min_count, top_k, max_reviews=None):
    reviews_csv = "./data/processed/reviews.csv"
    vocab_csv = "./data/vocab/category_tag_vocab.csv"
    review_tags_csv = "./data/processed/review_tags.csv"
    product_tags_csv = "./data/processed/product_tags.csv"
    annotated_tags_csv = "./data/annotated/review_tags.csv"

    if not os.path.exists(reviews_csv):
        raise FileNotFoundError(f"缺少 {reviews_csv}，请先 prepare_reviews.py")

    print('-' * 50)
    print(f'动态打标')
    print('-' * 50)

    df = pd.read_csv(reviews_csv, encoding="utf-8-sig")
    if max_reviews:
        df = df.head(max_reviews).copy()
        print(f"调试模式: 仅处理前 {len(df)} 条")

    compiled = compile_rules()
    tag_rows = []
    for row in df.itertuples(index=False):
        text = str(getattr(row, "sentence", "") or "")
        hits = extract_tags(text, compiled)
        for aspect, tag, polarity in hits:
            tag_rows.append(
                {
                    "review_id": row.review_id,
                    "product_id": row.product_id,
                    "category": row.category,
                    "aspect": aspect,
                    "opinion": tag,
                    "polarity": polarity,
                    "tag": tag,
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
        # 商品评论总数（分母）
        review_cnt = df.groupby("product_id").size().to_dict()
        cat_map = (
            df.drop_duplicates("product_id")
            .set_index("product_id")["category"]
            .to_dict()
        )

        # 聚合
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
        """文件被 Excel 占用时写到 .new.csv，避免整段失败。"""
        try:
            df.to_csv(path, index=False, encoding="utf-8-sig")
            return path
        except PermissionError:
            alt = path.replace(".csv", ".new.csv")
            df.to_csv(alt, index=False, encoding="utf-8-sig")
            print(f'警告: {path} 被占用，已改写到 {alt}，请关闭占用后替换')
            return alt

    safe_to_csv(pd.DataFrame(build_vocab_rows()), vocab_csv)
    safe_to_csv(review_tags, review_tags_csv)
    safe_to_csv(review_tags, annotated_tags_csv)
    safe_to_csv(product_tags, product_tags_csv)

    print(f'词表: {vocab_csv}')
    print(f'评论标签: {review_tags_csv}')
    print(f'商品标签墙: {product_tags_csv} ({len(product_tags)} 行)')
    if len(product_tags):
        top_products = (
            product_tags.groupby("product_id")["count"].sum().nlargest(5)
        )
        print(f'标签提及最多的商品(top5):')
        print(top_products)
        sample_pid = top_products.index[0]
        print(f'\n示例商品标签墙 {sample_pid}:')
        print(product_tags[product_tags["product_id"] == sample_pid].head(10))


def main():
    # 1. 解析参数
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-count", type=int, default=1)       # 参1: 标签至少出现次数
    parser.add_argument("--top-k", type=int, default=15)          # 参2: 每商品最多标签数
    parser.add_argument("--max-reviews", type=int, default=None)  # 参3: 调试限量
    args = parser.parse_args()
    # 2. 跑打标
    run(args.min_count, args.top_k, args.max_reviews)


if __name__ == "__main__":
    # 1. 动态打标入口
    main()
