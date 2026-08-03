"""
案例:
    分层多标签数据：通用标签 y_gen + 类目标签 y_cat。
"""

# 导包
import os
import sys
from collections import defaultdict

from models.common.dataset.load_reviews import load_split

_ANNOTATE_DIR = os.path.abspath("./data/scripts/annotate")
if _ANNOTATE_DIR not in sys.path:
    sys.path.insert(0, _ANNOTATE_DIR)

from tag_rules import (  # noqa: E402
    category_tag_map,
    general_tag_names,
    tag_meta_map,
)


def format_input(text, category=None):
    text = (text or "").strip()
    cat = (category or "").strip()
    if cat:
        return f"[品类:{cat}] {text}"
    return text


def _variant_phrases(seed: str) -> list[str]:
    if len(seed) < 2:
        return []
    head, tail = seed[:-1], seed[-1]
    variants = [
        head + "很" + tail,
        head + "挺" + tail,
        head + "也" + tail,
        head + "也挺" + tail,
        head + "非常" + tail,
        head + "比较" + tail,
    ]
    out, seen = [], set()
    for v in variants:
        if v != seed and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def _inject_seed_examples():
    """
    人为灌一批「标签原型句 + 多观点组合句」，专治「发货也挺快」这类 OOV。
    """
    from tag_rules import CATEGORY_RULES, GENERAL_RULES

    texts, cats, y_gen, y_cat = [], [], [], []
    carrier_cats = ["图书音像", "手机/数码", "美妆个护", "电脑/办公", "服饰服装"]

    def push(phrase, cat, g_labs, c_labs):
        texts.append(format_input(phrase, cat))
        cats.append(cat)
        y_gen.append(list(g_labs))
        y_cat.append(list(c_labs))

    for _, tag, _, patterns in GENERAL_RULES:
        clean = [p for p in patterns if "\\" not in p and "[" not in p and len(p) >= 2][:4]
        for p in clean:
            phrases = [p] + _variant_phrases(p)  # 全量近义
            for phrase in phrases:
                for cat in carrier_cats:
                    push(phrase, cat, [tag], [])

    for cat_list, _, tag, _, patterns in CATEGORY_RULES:
        clean = [p for p in patterns if "\\" not in p and "[" not in p and len(p) >= 2][:4]
        for p in clean:
            phrases = [p] + _variant_phrases(p)
            for phrase in phrases:
                for cat in cat_list:
                    push(phrase, cat, [], [tag])

    # 多观点组合：训练「长句多标签」能力（和线上分句互补）
    combos = [
        ("质量很好，发货也挺快，包装有点破损", ["质量好", "发货快", "包装差"], []),
        ("质量挺好，发货很快，包装破损", ["质量好", "发货快", "包装差"], []),
        ("物流很慢，客服态度差，不推荐", ["物流慢", "客服差", "不推荐"], []),
        ("性价比很高，还会回购", ["性价比高", "会回购"], []),
        ("内容不错，很有干货，物流慢", ["物流慢"], ["内容不错"]),
        ("续航很久，屏幕清晰，质量不错", ["质量好"], ["续航久", "屏幕清晰"]),
        ("面料不错，款式好看，尺码合适", [], ["面料不错", "款式好看", "尺码合适"]),
    ]
    for phrase, g_labs, c_labs in combos:
        for cat in carrier_cats:
            # 类目标签只灌给允许该类目的样本
            if c_labs:
                allowed = set(category_tag_map().get(cat, []))
                use_c = [t for t in c_labs if t in allowed]
                if not use_c and c_labs:
                    continue
                push(phrase, cat, g_labs, use_c)
            else:
                push(phrase, cat, g_labs, [])

    print(f'注入标签原型句: {len(texts)} 条')
    return texts, cats, y_gen, y_cat


def _augment_hierarchical(texts, categories, y_gen, y_cat):
    """近义改写：同时扩通用/类目标签，抗 OOV。"""
    from tag_rules import CATEGORY_RULES, GENERAL_RULES

    seeds = []
    for _, tag, _, patterns in GENERAL_RULES:
        for p in patterns:
            if "\\" in p or "[" in p or "(" in p:
                continue
            if len(p) >= 2:
                seeds.append((p, tag, "general"))
    for _, _, tag, _, patterns in CATEGORY_RULES:
        for p in patterns:
            if "\\" in p or "[" in p or "(" in p:
                continue
            if len(p) >= 2:
                seeds.append((p, tag, "category"))

    ax, ac, ag, ak = [], [], [], []
    for text, cat, g_labs, c_labs in zip(texts, categories, y_gen, y_cat):
        # format_input 后的文本里找种子；改写时改整串
        all_labs = set(g_labs) | set(c_labs)
        if not all_labs:
            continue
        n_add = 0
        for seed, tag, scope in seeds:
            if tag not in all_labs or seed not in text:
                continue
            for var in _variant_phrases(seed):
                new = text.replace(seed, var, 1)
                if new == text:
                    continue
                ax.append(new)
                ac.append(cat)
                ag.append(list(g_labs))
                ak.append(list(c_labs))
                n_add += 1
                break
            if n_add >= 2:
                break
    return ax, ac, ag, ak


def load_hierarchical(name="train", max_samples=None, augment=True):
    """
    返回:
      texts, categories,
      y_gen_lists (通用标签名列表),
      y_cat_lists (类目专属标签名列表),
      rows
    """
    import pandas as pd

    tags_csv = "./data/processed/review_tags.csv"
    if not os.path.exists(tags_csv):
        raise FileNotFoundError(
            f"缺少 {tags_csv}，请先跑 dynamic_tagging.py 生成银标"
        )

    df = load_split(name)
    tags = pd.read_csv(tags_csv, encoding="utf-8-sig")
    by_rid = defaultdict(set)
    for row in tags.itertuples(index=False):
        by_rid[str(row.review_id)].add(str(row.tag))

    gen_set = set(general_tag_names())
    cat_map = category_tag_map()
    meta = tag_meta_map()

    texts, categories, y_gen, y_cat, rows = [], [], [], [], []
    for row in df.itertuples(index=False):
        rid = str(row.review_id)
        sentence = str(getattr(row, "sentence", "") or "")
        category = str(getattr(row, "category", "") or "")
        product_id = str(getattr(row, "product_id", "") or "")
        hit_tags = by_rid.get(rid, set())

        # 按词表拆成通用 / 类目；类目标签还要属于该类目
        allowed_cat = set(cat_map.get(category, []))
        g_labels = sorted(t for t in hit_tags if t in gen_set)
        c_labels = sorted(
            t
            for t in hit_tags
            if meta.get(t, {}).get("scope") == "category" and t in allowed_cat
        )

        texts.append(format_input(sentence, category))
        categories.append(category)
        y_gen.append(g_labels)
        y_cat.append(c_labels)
        rows.append(
            {
                "review_id": rid,
                "product_id": product_id,
                "category": category,
                "sentence": sentence,
            }
        )

    if max_samples:
        # 优先保留「有类目标签」的样本，避免类目头被图书海量样本淹没
        order = sorted(
            range(len(texts)),
            key=lambda i: (0 if y_cat[i] else 1, 0 if y_gen[i] else 1, i),
        )
        keep = order[:max_samples]
        texts = [texts[i] for i in keep]
        categories = [categories[i] for i in keep]
        y_gen = [y_gen[i] for i in keep]
        y_cat = [y_cat[i] for i in keep]
        rows = [rows[i] for i in keep]

    if augment and name == "train":
        import re

        # 先对「原始有标签长评」做分句弱监督，再注入近义原型（避免数据爆炸）
        cx, cc, cg, ck = [], [], [], []
        for text, cat, g_labs, c_labs in zip(texts, categories, y_gen, y_cat):
            if not g_labs and not c_labs:
                continue
            body = text
            prefix = ""
            if text.startswith("[品类:") and "] " in text:
                prefix, body = text.split("] ", 1)
                prefix = prefix + "] "
            parts = [
                p.strip()
                for p in re.split(r"[，。！？；、,\.!\?;]+", body)
                if len(p.strip()) >= 2
            ]
            if len(parts) <= 1:
                continue
            for p in parts[:3]:
                cx.append(prefix + p if prefix else format_input(p, cat))
                cc.append(cat)
                cg.append(list(g_labs))
                ck.append(list(c_labs))
        print(f'分句弱监督样本: +{len(cx)} 条')
        texts.extend(cx)
        categories.extend(cc)
        y_gen.extend(cg)
        y_cat.extend(ck)

        sx, sc, sg, sk = _inject_seed_examples()
        texts.extend(sx)
        categories.extend(sc)
        y_gen.extend(sg)
        y_cat.extend(sk)
        ax, ac, ag, ak = _augment_hierarchical(texts, categories, y_gen, y_cat)
        print(f'分层近义改写: +{len(ax)} 条')
        texts.extend(ax)
        categories.extend(ac)
        y_gen.extend(ag)
        y_cat.extend(ak)

    n_g = sum(1 for x in y_gen if x)
    n_c = sum(1 for x in y_cat if x)
    print(
        f'分层数据 {name}: total={len(texts)} '
        f'有通用标={n_g} 有类目标={n_c} 通用维={len(gen_set)} 类目数={len(cat_map)}'
    )
    return texts, categories, y_gen, y_cat, rows
