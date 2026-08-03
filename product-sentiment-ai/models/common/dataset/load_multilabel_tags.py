"""
案例:
    多标签打标数据：评论 → 多个方面标签（银标来自规则明细）。

大白话:
    review_tags 里有的标签当正样本；没抽到的评论当全 0 负样本。
    再做一点近义改写，减轻「质量很好」这种 OOV。
"""

# 导包
import os
import sys
from collections import defaultdict

import pandas as pd

from models.common.dataset.load_reviews import load_split

_ANNOTATE_DIR = os.path.abspath("./data/scripts/annotate")
if _ANNOTATE_DIR not in sys.path:
    sys.path.insert(0, _ANNOTATE_DIR)

from tag_rules import TAG_RULES  # noqa: E402


# 1. 标签元信息（tag → aspect / polarity）
def tag_meta_map():
    return {tag: {"aspect": aspect, "polarity": polarity} for aspect, tag, polarity, _ in TAG_RULES}


def all_tag_names():
    return [tag for _, tag, _, _ in TAG_RULES]


# 2. 近义改写：程度词 / 语气词插入，专门打「质量很好」「发货也挺快」这类 OOV
def _variant_phrases(seed: str) -> list[str]:
    if len(seed) < 2:
        return []
    head, tail = seed[:-1], seed[-1]
    variants = [
        head + "很" + tail,          # 质量很好
        head + "挺" + tail,          # 质量挺好
        head + "非常" + tail,
        head + "比较" + tail,
        head + "也" + tail,          # 发货也快
        head + "也很" + tail,
        head + "也挺" + tail,        # 发货也挺快
        head + "还" + tail,
        head + "还算" + tail,
    ]
    # 去重且别等于原文
    out, seen = [], set()
    for v in variants:
        if v != seed and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _augment_texts(texts, label_lists):
    seeds = []
    for _, tag, _, patterns in TAG_RULES:
        for p in patterns:
            # 跳过带正则元字符的复杂式子
            if "\\" in p or "[" in p or "(" in p:
                continue
            if len(p) >= 2:
                seeds.append((p, tag))

    aug_x, aug_y = [], []
    for text, labels in zip(texts, label_lists):
        for seed, tag in seeds:
            if seed not in text or tag not in labels:
                continue
            # 每条原文每个种子最多扩 2 个变体，控数据膨胀
            n_add = 0
            for var in _variant_phrases(seed):
                new = text.replace(seed, var, 1)
                if new == text:
                    continue
                aug_x.append(new)
                aug_y.append(list(labels))
                n_add += 1
                if n_add >= 2:
                    break
    return aug_x, aug_y


# 3. 拼输入：带上品类，给模型一点商品上下文
def format_input(text, category=None):
    text = (text or "").strip()
    cat = (category or "").strip()
    if cat:
        return f"[品类:{cat}] {text}"
    return text


# 4. 读多标签切分
def load_multilabel(name="train", max_samples=None, augment=True):
    reviews_path_ok = {
        "train": "./data/processed/reviews_train.csv",
        "val": "./data/processed/reviews_val.csv",
        "all": "./data/processed/reviews.csv",
    }
    if name not in reviews_path_ok:
        raise ValueError("name 只能是 train | val | all")

    tags_csv = "./data/processed/review_tags.csv"
    if not os.path.exists(tags_csv):
        raise FileNotFoundError(
            f"缺少 {tags_csv}，请先跑 data/scripts/annotate/dynamic_tagging.py"
        )

    df = load_split(name)
    tags = pd.read_csv(tags_csv, encoding="utf-8-sig")
    by_rid = defaultdict(set)
    for row in tags.itertuples(index=False):
        by_rid[str(row.review_id)].add(str(row.tag))

    texts, label_lists, rows = [], [], []
    for row in df.itertuples(index=False):
        rid = str(row.review_id)
        sentence = str(getattr(row, "sentence", "") or "")
        category = str(getattr(row, "category", "") or "")
        product_id = str(getattr(row, "product_id", "") or "")
        texts.append(format_input(sentence, category))
        label_lists.append(sorted(by_rid.get(rid, set())))
        rows.append(
            {
                "review_id": rid,
                "product_id": product_id,
                "category": category,
                "sentence": sentence,
            }
        )

    if max_samples:
        texts = texts[:max_samples]
        label_lists = label_lists[:max_samples]
        rows = rows[:max_samples]

    if augment and name == "train":
        ax, ay = _augment_texts(texts, label_lists)
        print(f'近义改写扩充: +{len(ax)} 条')
        texts.extend(ax)
        label_lists.extend(ay)

    n_pos = sum(1 for lbs in label_lists if lbs)
    print(f'多标签数据 {name}: total={len(texts)} 有标签={n_pos} 标签数={len(all_tag_names())}')
    return texts, label_lists, rows
