"""
案例:
    动态打标业务：批量任务 + 单条评论打标。

大白话:
    优先 BERT 多标签多分类；没有再退回字符 n-gram；再和规则取并集扛漏标。
"""

# 导包
import json
import os
import re
import sys
from functools import lru_cache

import joblib
import numpy as np
import pandas as pd
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from api.services.job_runner import python_cmd, start_job
from api.services.open_tag_extract import extract_open_tags

# 以仓库根目录定位，避免「从别的 cwd 直接跑脚本」找不到 tag_rules
_AI_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_ANNOTATE_DIR = os.path.join(_AI_ROOT, "data", "scripts", "annotate")
if _ANNOTATE_DIR not in sys.path:
    sys.path.insert(0, _ANNOTATE_DIR)

from tag_rules import extract_tags, tag_has_text_evidence, tag_meta_map  # noqa: E402

TAG_SKLEARN_CKPT = os.path.join(_AI_ROOT, "models", "tagging", "model", "tagging_multilabel.joblib")
TAG_BERT_DIR = os.path.join(_AI_ROOT, "models", "tagging", "model", "bert_multilabel")
TAG_HIER_DIR = os.path.join(_AI_ROOT, "models", "tagging", "model", "bert_hierarchical")


# 1. 启动打标脚本（整表银标 / 开放聚合）
def start_tagging(min_count=1, top_k=15, mode="rules"):
    script = "./data/scripts/annotate/dynamic_tagging.py"
    mode = (mode or "rules").strip().lower()
    print(f'启动打标 mode={mode} min_count={min_count} top_k={top_k}')
    return start_job(
        python_cmd(
            script,
            "--mode",
            mode,
            "--min-count",
            str(min_count),
            "--top-k",
            str(top_k),
        )
    )


# 2. 商品索引
@lru_cache(maxsize=1)
def _load_product_index():
    reviews_csv = "./data/processed/reviews.csv"
    if not os.path.exists(reviews_csv):
        return {}
    df = pd.read_csv(reviews_csv, encoding="utf-8-sig")
    cols = [c for c in ("product_id", "category", "product_name") if c in df.columns]
    if "product_id" not in cols:
        return {}
    sub = df[cols].drop_duplicates("product_id")
    out = {}
    for row in sub.itertuples(index=False):
        out[str(row.product_id)] = {
            "category": str(getattr(row, "category", "") or ""),
            "product_name": str(getattr(row, "product_name", "") or ""),
        }
    print(f'商品索引加载完成: {len(out)} 个')
    return out


@lru_cache(maxsize=1)
def _load_sklearn_tag_model():
    if not os.path.exists(TAG_SKLEARN_CKPT):
        return None
    print(f'加载字符 n-gram 多标签模型: {TAG_SKLEARN_CKPT}')
    return joblib.load(TAG_SKLEARN_CKPT)


@lru_cache(maxsize=1)
def _load_bert_tag_model():
    if not os.path.exists(os.path.join(TAG_BERT_DIR, "config.json")):
        return None
    print(f'加载 BERT 多标签模型: {TAG_BERT_DIR}')
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tok = AutoTokenizer.from_pretrained(TAG_BERT_DIR, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        TAG_BERT_DIR, local_files_only=True
    ).to(device)
    model.eval()
    with open(os.path.join(TAG_BERT_DIR, "label_names.json"), "r", encoding="utf-8") as f:
        labels = json.load(f)
    meta = {}
    meta_path = os.path.join(TAG_BERT_DIR, "tag_meta.json")
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
    thr = 0.35
    thr_path = os.path.join(TAG_BERT_DIR, "threshold.txt")
    if os.path.exists(thr_path):
        with open(thr_path, "r", encoding="utf-8") as f:
            thr = float(f.read().strip())
    return {
        "tok": tok,
        "model": model,
        "device": device,
        "labels": labels,
        "meta": meta,
        "threshold": thr,
    }


@lru_cache(maxsize=1)
def _load_hier_tag_model():
    cfg_path = os.path.join(TAG_HIER_DIR, "hier_config.json")
    weight_path = os.path.join(TAG_HIER_DIR, "pytorch_model.bin")
    if not (os.path.exists(cfg_path) and os.path.exists(weight_path)):
        return None
    print(f'加载分层 BERT 打标模型: {TAG_HIER_DIR}')
    from models.tagging.scripts.predict_hierarchical import load_hierarchical_bundle

    return load_hierarchical_bundle(TAG_HIER_DIR)


def clear_tag_model_cache():
    _load_sklearn_tag_model.cache_clear()
    _load_bert_tag_model.cache_clear()
    _load_hier_tag_model.cache_clear()
    _load_product_index.cache_clear()
    print(f'打标模型缓存已清空')


def _has_any_model():
    """只看文件在不在，避免 open 模式也把大模型加载进内存。"""
    return (
        (
            os.path.exists(os.path.join(TAG_HIER_DIR, "hier_config.json"))
            and os.path.exists(os.path.join(TAG_HIER_DIR, "pytorch_model.bin"))
        )
        or os.path.exists(os.path.join(TAG_BERT_DIR, "config.json"))
        or os.path.exists(TAG_SKLEARN_CKPT)
    )


def _rules_hits(text, category=None):
    meta = tag_meta_map()
    hits = extract_tags(text, category=category)
    return [
        {
            "aspect": aspect,
            "tag": tag,
            "polarity": polarity,
            "score": 1.0,
            "source": "rules",
            "scope": meta.get(tag, {}).get("scope"),
        }
        for aspect, tag, polarity in hits
    ]


def _split_clauses(text):
    parts = re.split(r"[，。！？；、,\.!\?;]+", text)
    return [p.strip() for p in parts if len(p.strip()) >= 2]


def _format_inputs(text, category):
    cat = (category or "").strip()
    chunks = [text] + _split_clauses(text)
    if cat:
        return [f"[品类:{cat}] {c}" for c in chunks]
    return chunks


def _sklearn_hits(text, category):
    bundle = _load_sklearn_tag_model()
    if bundle is None:
        return []
    pipe = bundle["pipe"]
    mlb = bundle["mlb"]
    thr = float(bundle.get("threshold", 0.28))
    meta = bundle.get("tag_meta") or {}
    inputs = _format_inputs(text, category)
    if hasattr(pipe, "predict_proba"):
        proba = np.asarray(pipe.predict_proba(inputs))
    else:
        proba = np.asarray(pipe.predict(inputs)).astype(float)
    scores = proba.max(axis=0)
    hits = []
    for j, name in enumerate(mlb.classes_):
        score = float(scores[j])
        if score < thr:
            continue
        info = meta.get(name, {})
        hits.append(
            {
                "aspect": info.get("aspect", ""),
                "tag": name,
                "polarity": info.get("polarity", ""),
                "score": score,
                "source": "char_ngram",
            }
        )
    return hits


def _resolve_aspect_conflicts(hits):
    """同一方面正负标签冲突时，只留分数更高的那个。"""
    best = {}
    for item in hits:
        aspect = item.get("aspect") or item["tag"]
        old = best.get(aspect)
        if old is None or item["score"] > old["score"]:
            best[aspect] = item
    return list(best.values())


@torch.no_grad()
def _bert_hits(text, category):
    bundle = _load_bert_tag_model()
    if bundle is None:
        return []
    tok = bundle["tok"]
    model = bundle["model"]
    device = bundle["device"]
    labels = bundle["labels"]
    meta = bundle["meta"]
    # 验证集搜到的阈值偏严；线上略降以召回近义说法（发货也挺快）
    thr = min(float(bundle["threshold"]), 0.40)
    inputs = _format_inputs(text, category)
    enc = tok(
        inputs,
        truncation=True,
        padding=True,
        max_length=128,
        return_tensors="pt",
    )
    enc = {k: v.to(device) for k, v in enc.items()}
    probs = torch.sigmoid(model(**enc).logits).detach().cpu().numpy().max(axis=0)
    hits = []
    for j, name in enumerate(labels):
        score = float(probs[j])
        if score < thr:
            continue
        info = meta.get(name, {})
        hits.append(
            {
                "aspect": info.get("aspect", ""),
                "tag": name,
                "polarity": info.get("polarity", ""),
                "score": score,
                "source": "bert",
            }
        )
    return _resolve_aspect_conflicts(hits)


def _hier_hits(text, category):
    bundle = _load_hier_tag_model()
    if bundle is None:
        return []
    from models.tagging.scripts.predict_hierarchical import predict_one

    return predict_one(bundle, text, category)


def _model_hits(text, category):
    """优先分层 BERT；其次扁平 BERT；再字符 n-gram。"""
    if _load_hier_tag_model() is not None:
        hits = _hier_hits(text, category)
        backend = "hier"
    elif _load_bert_tag_model() is not None:
        hits = _bert_hits(text, category)
        backend = "bert"
    else:
        hits = _sklearn_hits(text, category)
        backend = "char_ngram"
    # 分层路径内已接地；扁平/字符路径在此补一道
    if backend != "hier":
        before = len(hits)
        hits = [h for h in hits if tag_has_text_evidence(text, h["tag"])]
        if before != len(hits):
            print(f'文本接地过滤: {before} → {len(hits)}')
    hits.sort(key=lambda x: x["score"], reverse=True)
    print(f'模型打标后端={backend} 命中={len(hits)}')
    return hits


def _merge_hits(rule_hits, model_hits):
    merged = {}
    for item in rule_hits + model_hits:
        name = item["tag"]
        old = merged.get(name)
        if old is None or item["score"] > old["score"]:
            merged[name] = dict(item)
        elif old is not None and item["source"] != old["source"]:
            merged[name]["source"] = "hybrid"
    out = list(merged.values())
    out.sort(key=lambda x: x["score"], reverse=True)
    return out


# 4. 单条：评论 + 商品 → 多标签
def predict_tags(text, product_id, method="model", category=None, product_name=None):
    text = (text or "").strip()
    product_id = (product_id or "").strip() or "DRAFT"
    method = (method or "model").strip().lower()
    if not text:
        raise ValueError("text 不能为空")
    if method not in {"auto", "open", "model", "rules", "hybrid"}:
        raise ValueError("method 只能是: open | model | rules | hybrid | auto")

    info = _load_product_index().get(product_id, {})
    # 前端草稿可直接传 category；库里有商品则优先用库
    category = (info.get("category") or category or "").strip() or None
    product_name = (info.get("product_name") or product_name or "").strip() or None

    has_model = _has_any_model()
    # auto：优先固定标签分层 BERT；无模型再退规则词表
    if method == "auto":
        method = "model" if has_model else "rules"

    if method == "open":
        tags = extract_open_tags(text)
        backend = "open_extract"
    elif method == "rules":
        tags = _resolve_aspect_conflicts(_rules_hits(text, category))
        backend = "rules"
    elif method == "model":
        if not has_model:
            raise FileNotFoundError(
                "缺少多标签模型。请先训练:\n"
                "  python -m models.tagging.scripts.train_hierarchical --refresh-silver\n"
                "或: python -m models.tagging.scripts.train_bert"
            )
        tags = _resolve_aspect_conflicts(_model_hits(text, category))
        backend = "bert_hierarchical" if _load_hier_tag_model() else "model"
    else:  # hybrid = 开放短语 ∪ 分层模型（仍不用规则词表）
        open_hits = extract_open_tags(text)
        model_hits = _model_hits(text, category) if has_model else []
        tags = _merge_hits(open_hits, model_hits)
        tags = _resolve_aspect_conflicts(tags)
        backend = "open+model"

    print(f'单条打标 product={product_id} method={method} backend={backend} 命中={len(tags)}')
    return {
        "text": text,
        "product_id": product_id,
        "category": category,
        "product_name": product_name,
        "tags": [
            {
                "aspect": t["aspect"],
                "tag": t["tag"],
                "polarity": t["polarity"],
                "score": t.get("score"),
                "source": t.get("source"),
                "scope": t.get("scope"),
            }
            for t in tags
        ],
        "tag_names": [t["tag"] for t in tags],
        "method": method,
        "backend": backend,
    }
