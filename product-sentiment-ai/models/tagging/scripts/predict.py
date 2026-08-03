"""
案例:
    多标签打标推理。

用法:
    python -m models.tagging.scripts.predict --text "质量很好，发货也挺快" --product-id PRODUCT_60357
    python -m models.tagging.scripts.predict --eval-val
"""

# 导包
import argparse
import os

import joblib
import numpy as np

from models.common.dataset.load_multilabel_tags import (
    format_input,
    load_multilabel,
    tag_meta_map,
)
from models.common.metrics.evaluate import save_metrics
from models.common.metrics.evaluate_multilabel import compute_multilabel_metrics


def load_bundle():
    ckpt = "./models/tagging/model/tagging_multilabel.joblib"
    if not os.path.exists(ckpt):
        raise FileNotFoundError(
            f"缺少 {ckpt}，请先训练:\n  python -m models.tagging.scripts.train"
        )
    return joblib.load(ckpt)


def _split_clauses(text):
    import re

    # 去掉可能的品类前缀再切
    raw = text
    if raw.startswith("[品类:") and "] " in raw:
        raw = raw.split("] ", 1)[1]
    parts = re.split(r"[，。！？；、,\.!\?;]+", raw)
    return [p.strip() for p in parts if len(p.strip()) >= 2]


def predict_texts(bundle, texts, threshold=None, clause_max=True):
    pipe = bundle["pipe"]
    mlb = bundle["mlb"]
    thr = bundle.get("threshold", 0.28) if threshold is None else threshold
    meta = bundle.get("tag_meta") or tag_meta_map()

    results = []
    for text in texts:
        chunks = [text]
        if clause_max:
            # 分句推理时保留原品类前缀
            prefix = ""
            body = text
            if text.startswith("[品类:") and "] " in text:
                prefix, body = text.split("] ", 1)
                prefix = prefix + "] "
            for c in _split_clauses(text):
                chunks.append(prefix + c)

        if hasattr(pipe, "predict_proba"):
            proba = np.asarray(pipe.predict_proba(chunks)).max(axis=0)
        else:
            proba = np.asarray(pipe.predict(chunks)).astype(float).max(axis=0)

        tags = []
        for j, name in enumerate(mlb.classes_):
            score = float(proba[j])
            if score < thr:
                continue
            info = meta.get(name, {})
            tags.append(
                {
                    "aspect": info.get("aspect", ""),
                    "tag": name,
                    "polarity": info.get("polarity", ""),
                    "score": score,
                }
            )
        tags.sort(key=lambda x: x["score"], reverse=True)
        results.append(tags)
    return results


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
    parser.add_argument("--text", type=str, default=None)
    parser.add_argument("--product-id", type=str, default="")
    parser.add_argument("--eval-val", action="store_true")
    parser.add_argument("--threshold", type=float, default=None)
    args = parser.parse_args()

    bundle = load_bundle()

    if args.eval_val or not args.text:
        if not args.text:
            print(f'未指定 --text，默认 --eval-val')
        x_val, y_val_lists, _ = load_multilabel("val", augment=False)
        mlb = bundle["mlb"]
        y_true = mlb.transform(y_val_lists)
        thr = args.threshold if args.threshold is not None else bundle.get("threshold", 0.35)
        proba = np.asarray(bundle["pipe"].predict_proba(x_val))
        y_pre = (proba >= thr).astype(int)
        metrics = compute_multilabel_metrics(y_true, y_pre, label_names=list(mlb.classes_))
        print(metrics["report"])
        save_metrics(
            metrics,
            "./models/tagging/results/metrics_eval.json",
            {"model": "tagging_multilabel", "threshold": thr, "train_size": "eval_only"},
        )

    if args.text:
        category, product_name = lookup_product(args.product_id)
        inp = format_input(args.text, category)
        tags = predict_texts(bundle, [inp], threshold=args.threshold)[0]
        print('-' * 50)
        print(f'单条多标签预测')
        print('-' * 50)
        print(f'文本: {args.text}')
        print(f'商品: {args.product_id} | 品类: {category} | {product_name}')
        print(f'标签: {[t["tag"] for t in tags]}')
        for t in tags:
            print(f'  - {t["tag"]} ({t["aspect"]}/{t["polarity"]}) score={t["score"]:.3f}')


if __name__ == "__main__":
    main()
