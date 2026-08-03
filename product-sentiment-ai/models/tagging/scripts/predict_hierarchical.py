"""
案例:
    分层 BERT 打标推理。

用法:
    python -m models.tagging.scripts.predict_hierarchical --text "面料不错，发货快" --product-id PRODUCT_1
"""

# 导包
import argparse
import json
import os
import re

import torch
from transformers import AutoTokenizer

from models.common.dataset.load_hierarchical_tags import format_input
from models.tagging.hierarchical_model import HierarchicalTagBERT

_AI_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_DEFAULT_PRETRAINED = os.path.join(
    _AI_ROOT,
    "models",
    "bert",
    "common",
    "pretrained",
    "models",
    "tiansz--bert-base-chinese",
    "snapshots",
    "master",
)


def _is_plain_bert_dir(path: str) -> bool:
    """是否为可用的 BERT 底座目录（有 config + 底座权重，且不是分层 ckpt）。"""
    if not path or not os.path.isdir(path):
        return False
    if not os.path.isfile(os.path.join(path, "config.json")):
        return False
    if os.path.isfile(os.path.join(path, "hier_config.json")):
        return False
    return any(
        os.path.isfile(os.path.join(path, name))
        for name in ("model.safetensors", "pytorch_model.bin", "model.bin")
    )


def _resolve_encoder_source(base_model: str, ckpt_dir: str) -> tuple[str, bool]:
    """返回 (path, config_only)。

    训练机写入的 Windows 绝对路径在 Linux 上无效；优先找本仓库相对 pretrained，
    否则用 ckpt 内 config.json 只建结构（权重由 pytorch_model.bin 灌入）。
    """
    if _is_plain_bert_dir(base_model):
        return os.path.abspath(base_model), False

    # 相对仓库根的路径（推荐写入 hier_config.json）
    if base_model and not os.path.isabs(base_model):
        rel_cand = os.path.join(_AI_ROOT, base_model.replace("\\", "/").lstrip("./"))
        if _is_plain_bert_dir(rel_cand):
            return os.path.abspath(rel_cand), False

    if _is_plain_bert_dir(_DEFAULT_PRETRAINED):
        return _DEFAULT_PRETRAINED, False

    # 从泄漏的绝对路径里抠相对后缀
    norm = (base_model or "").replace("\\", "/")
    key = "models/bert/common/pretrained/"
    if key in norm:
        rel = norm[norm.index(key) :]
        cand = os.path.join(_AI_ROOT, *rel.split("/"))
        if _is_plain_bert_dir(cand):
            return cand, False

    if os.path.isfile(os.path.join(ckpt_dir, "config.json")):
        print(
            f"提示: 未找到底座 pretrained，改用 ckpt 配置建编码器结构: {ckpt_dir}"
        )
        return os.path.abspath(ckpt_dir), True

    raise FileNotFoundError(
        "找不到 BERT 底座目录。请上传:\n"
        f"  {_DEFAULT_PRETRAINED}\n"
        "或保证 ckpt 目录含 config.json（可 config_only 加载）"
    )


def load_hierarchical_bundle(ckpt_dir="./models/tagging/model/bert_hierarchical"):
    cfg_path = os.path.join(ckpt_dir, "hier_config.json")
    weight_path = os.path.join(ckpt_dir, "pytorch_model.bin")
    if not os.path.exists(cfg_path) or not os.path.exists(weight_path):
        raise FileNotFoundError(
            f"缺少分层模型 {ckpt_dir}，请先:\n"
            "  python -m models.tagging.scripts.train_hierarchical"
        )
    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tok = AutoTokenizer.from_pretrained(ckpt_dir, local_files_only=True)
    cat_map = cfg["category_tag_map"]
    encoder_src, config_only = _resolve_encoder_source(cfg.get("base_model") or "", ckpt_dir)
    model = HierarchicalTagBERT(
        encoder_src,
        n_general=len(cfg["general_labels"]),
        category_dims={c: len(labs) for c, labs in cat_map.items()},
        config_only=config_only,
    )
    state = torch.load(weight_path, map_location=device)
    model.load_state_dict(state)
    model.to(device)
    model.eval()
    return {
        "tok": tok,
        "model": model,
        "device": device,
        "general_labels": cfg["general_labels"],
        "category_tag_map": cat_map,
        "tag_meta": cfg.get("tag_meta") or {},
        "threshold": float(cfg.get("threshold", 0.4)),
        # 按标签阈值（训练/tune 脚本写入）；没有则退回全局 threshold
        "thresholds_general": cfg.get("thresholds_general") or {},
        "thresholds_category": cfg.get("thresholds_category") or {},
    }


def split_clauses(text):
    parts = re.split(r"[，。！？；、,\.!\?;]+", text)
    return [p.strip() for p in parts if len(p.strip()) >= 2]


def _filter_grounded(hits, text):
    """丢掉原文撑不住的标签（防模型瞎补「会回购/正品放心」）。"""
    import sys

    annotate = os.path.abspath("./data/scripts/annotate")
    if annotate not in sys.path:
        sys.path.insert(0, annotate)
    from tag_rules import tag_has_text_evidence

    kept = [h for h in hits if tag_has_text_evidence(text, h["tag"])]
    return kept


def _tag_threshold(bundle, tag_name, scope="general"):
    """优先按标签阈值；否则用全局 threshold（上限 0.45，防过松）。"""
    default = min(float(bundle.get("threshold", 0.4)), 0.45)
    if scope == "category":
        return float((bundle.get("thresholds_category") or {}).get(tag_name, default))
    return float((bundle.get("thresholds_general") or {}).get(tag_name, default))


@torch.no_grad()
def predict_one(bundle, text, category=None):
    meta = bundle["tag_meta"]
    tok = bundle["tok"]
    model = bundle["model"]
    device = bundle["device"]
    body = (text or "").strip()
    chunks = [body] + split_clauses(body)
    inputs = [format_input(c, category) for c in chunks]
    cats = [category or ""] * len(inputs)

    enc = tok(inputs, truncation=True, padding=True, max_length=128, return_tensors="pt")
    enc = {k: v.to(device) for k, v in enc.items()}
    gen_logits, cat_logits = model.forward_both(enc["input_ids"], enc["attention_mask"], cats)
    gen_probs = torch.sigmoid(gen_logits).cpu().numpy().max(axis=0)

    hits = []
    for i, name in enumerate(bundle["general_labels"]):
        score = float(gen_probs[i])
        if score < _tag_threshold(bundle, name, "general"):
            continue
        info = meta.get(name, {})
        hits.append(
            {
                "aspect": info.get("aspect", ""),
                "tag": name,
                "polarity": info.get("polarity", ""),
                "score": score,
                "source": "hier_general",
                "scope": "general",
            }
        )

    # 类目头：同类目分句取 max
    cat = category or ""
    labels = bundle["category_tag_map"].get(cat)
    if labels:
        probs = []
        for lg in cat_logits:
            if lg is None:
                continue
            probs.append(torch.sigmoid(lg).cpu().numpy()[0])
        if probs:
            scores = np_max(probs)
            for j, name in enumerate(labels):
                score = float(scores[j])
                if score < _tag_threshold(bundle, name, "category"):
                    continue
                info = meta.get(name, {})
                hits.append(
                    {
                        "aspect": info.get("aspect", ""),
                        "tag": name,
                        "polarity": info.get("polarity", ""),
                        "score": score,
                        "source": "hier_category",
                        "scope": "category",
                    }
                )

    # 文本接地：没提的方面不许出
    hits = _filter_grounded(hits, body)

    # 同方面冲突消解
    best = {}
    for item in hits:
        aspect = item.get("aspect") or item["tag"]
        old = best.get(aspect)
        if old is None or item["score"] > old["score"]:
            best[aspect] = item
    out = list(best.values())
    out.sort(key=lambda x: x["score"], reverse=True)
    return out


def np_max(arrs):
    import numpy as np

    return np.max(np.stack(arrs, axis=0), axis=0)


def lookup_product(product_id):
    import pandas as pd

    path = "./data/processed/reviews.csv"
    if not product_id or not os.path.exists(path):
        return None, None
    df = pd.read_csv(path, encoding="utf-8-sig")
    sub = df[df["product_id"].astype(str) == str(product_id)]
    if sub.empty:
        return None, None
    row = sub.iloc[0]
    return str(row.get("category", "") or ""), str(row.get("product_name", "") or "")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", required=True)
    parser.add_argument("--product-id", default="")
    args = parser.parse_args()
    bundle = load_hierarchical_bundle()
    category, name = lookup_product(args.product_id)
    tags = predict_one(bundle, args.text, category)
    print('-' * 50)
    print(f'分层打标 category={category}')
    print('-' * 50)
    print([t["tag"] for t in tags])
    for t in tags:
        print(f'  - {t["tag"]} ({t["scope"]}) {t["score"]:.3f}')


if __name__ == "__main__":
    main()
