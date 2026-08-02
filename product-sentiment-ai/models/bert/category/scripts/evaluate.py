"""评估：每个类目一条进度条（batch 在跑），不是外层 0/14 卡住不动。"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# 关掉 transformers 加载权重时插进来的 Loading weights 条，避免打断类目进度条
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")

import torch
from torch.utils.data import DataLoader
from transformers import BertTokenizer
from transformers.utils import logging as hf_logging

hf_logging.set_verbosity_error()

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import get_aspect_map, list_trainable_categories, load_config, resolve_path
from dataset import AspectDataset, load_wide_records
from model import CategoryAspectBert
from train import _csv_path, evaluate_loader, safe_subdir, set_seed


def eval_one(cfg: dict, category: str, index: int | None = None, total: int | None = None) -> dict | None:
    aspect_map = get_aspect_map(cfg, category)
    aspects = list(aspect_map.keys())
    if not aspects:
        return None

    data_cfg = cfg["data"]
    test_csv = _csv_path(cfg, "test")
    test_recs = load_wide_records(
        test_csv,
        category=category,
        aspect_map=aspect_map,
        text_col=data_cfg.get("text_col", "评论内容_clean"),
        category_col=data_cfg.get("category_col", "类别"),
        attributes_col=data_cfg.get("attributes_col", "attributes"),
    )
    if not test_recs:
        print(f"[skip] test 为空: {category}")
        return None

    ckpt = resolve_path(cfg["output_dir"]) / safe_subdir(category) / "best"
    if not ckpt.exists():
        print(f"[skip] 无权重: {ckpt}")
        return None

    if index is not None and total is not None:
        print(f"\n[eval] ({index}/{total}) {category}  test={len(test_recs)}")
    else:
        print(f"\n[eval] {category}  test={len(test_recs)}")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = BertTokenizer.from_pretrained(ckpt / "tokenizer")
    model = CategoryAspectBert.from_pretrained(ckpt).to(device)
    ds = AspectDataset(test_recs, tokenizer, aspects, max_length=int(cfg["max_length"]))
    loader = DataLoader(ds, batch_size=int(cfg["batch_size"]), shuffle=False)

    # 每个类目各自一条进度条（内部 batch 在推进）
    metrics = evaluate_loader(
        model,
        loader,
        device,
        aspects,
        desc=f"eval {category}",
        show_pbar=True,
    )

    out = resolve_path(cfg["metrics_dir"]) / f"{safe_subdir(category)}_test_metrics.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {"category": category, "n_test": len(test_recs), **metrics}
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"[eval] {category} done  "
        f"acc={metrics['accuracy']:.4f} f1={metrics['f1_macro']:.4f} -> {out.name}"
    )
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="类目 BERT 评估")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--category", type=str, default=None, help="品类或 all")
    args = parser.parse_args()

    cfg = load_config(args.config)
    set_seed(int(cfg["random_seed"]))
    category = args.category or cfg.get("category") or "all"

    if category == "all":
        cats = list_trainable_categories(cfg)
        print(
            f"[eval] 模式=多类目，共 {len(cats)} 个；"
            f"每个类目一条进度条（跑 batch），不是外层 0/14"
        )
        results = {}
        for i, cat in enumerate(cats, 1):
            r = eval_one(cfg, cat, index=i, total=len(cats))
            if r:
                results[cat] = {
                    "n_test": r["n_test"],
                    "accuracy": r["accuracy"],
                    "f1_macro": r["f1_macro"],
                }
        path = resolve_path(cfg["metrics_dir"]) / "all_categories_test_summary.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n[eval] 多类目汇总 -> {path}")
    else:
        print(f"[eval] 模式=单类目，category={category}")
        eval_one(cfg, category)


if __name__ == "__main__":
    main()
