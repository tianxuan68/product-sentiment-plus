"""
案例:
    BERT 多标签打标推理。

用法:
    python -m models.tagging.scripts.predict_bert --text "质量很好，发货也挺快" --product-id PRODUCT_60357
"""

# 导包
import argparse
import json
import os
import re

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from models.common.dataset.load_multilabel_tags import format_input


def load_bundle(ckpt_dir="./models/tagging/model/bert_multilabel"):
    if not os.path.exists(os.path.join(ckpt_dir, "config.json")):
        raise FileNotFoundError(
            f"缺少 {ckpt_dir}，请先:\n  python -m models.tagging.scripts.train_bert"
        )
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tok = AutoTokenizer.from_pretrained(ckpt_dir, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        ckpt_dir, local_files_only=True
    ).to(device)
    model.eval()
    with open(os.path.join(ckpt_dir, "label_names.json"), "r", encoding="utf-8") as f:
        labels = json.load(f)
    meta_path = os.path.join(ckpt_dir, "tag_meta.json")
    meta = {}
    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
    thr = 0.35
    thr_path = os.path.join(ckpt_dir, "threshold.txt")
    if os.path.exists(thr_path):
        with open(thr_path, "r", encoding="utf-8") as f:
            thr = float(f.read().strip())
    return tok, model, device, labels, meta, thr


def split_clauses(text):
    parts = re.split(r"[，。！？；、,\.!\?;]+", text)
    return [p.strip() for p in parts if len(p.strip()) >= 2]


@torch.no_grad()
def predict_one(tok, model, device, labels, meta, thr, text, category=None):
    body = (text or "").strip()
    chunks = [body] + split_clauses(body)
    inputs = [format_input(c, category) for c in chunks]
    enc = tok(
        inputs,
        truncation=True,
        padding=True,
        max_length=128,
        return_tensors="pt",
    )
    enc = {k: v.to(device) for k, v in enc.items()}
    probs = torch.sigmoid(model(**enc).logits).cpu().numpy().max(axis=0)

    tags = []
    for i, name in enumerate(labels):
        score = float(probs[i])
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
    return tags


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

    tok, model, device, labels, meta, thr = load_bundle()
    category, product_name = lookup_product(args.product_id)
    tags = predict_one(tok, model, device, labels, meta, thr, args.text, category)
    print('-' * 50)
    print(f'BERT 多标签预测 thr={thr:.2f}')
    print('-' * 50)
    print(f'文本: {args.text}')
    print(f'商品: {args.product_id} | 品类: {category} | {product_name}')
    print(f'标签: {[t["tag"] for t in tags]}')
    for t in tags:
        print(f'  - {t["tag"]} score={t["score"]:.3f}')


if __name__ == "__main__":
    main()
