"""类目 BERT 训练（默认一次训全部类目；小样本=每类目随机抽 N 条）。

用法:
  python train.py
  python train.py --max_train_samples 200
  python train.py --category 服饰服装
  python train.py --category all --max_train_samples null   # 全量（需配置也为 ~）
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import accuracy_score, f1_score
from torch.optim import AdamW
from torch.utils.data import DataLoader
from tqdm import tqdm
from transformers import BertTokenizer, get_linear_schedule_with_warmup

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    get_aspect_map,
    get_aspects,
    list_trainable_categories,
    load_config,
    resolve_model_name,
    resolve_path,
)
from dataset import AspectDataset, load_wide_records, random_sample_records
from model import CategoryAspectBert


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def parse_maybe_int(v) -> int | None:
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip().lower()
        if s in {"", "null", "none", "~"}:
            return None
        return int(s)
    return int(v)


def iter_batches(loader, desc: str, show_pbar: bool = True):
    """每个类目一条进度条：终端原地刷新；IDE(非TTY)约每 5% 打一行，避免每个 batch 刷一行。"""
    if not show_pbar:
        yield from loader
        return

    total = len(loader)
    # 真终端：tqdm 原地更新一条
    if sys.stdout.isatty():
        yield from tqdm(
            loader,
            desc=desc,
            total=total,
            leave=True,
            dynamic_ncols=True,
            mininterval=0.3,
            file=sys.stdout,
        )
        return

    # PyCharm Run 等非 TTY：用简易条，节点输出，看起来像「一条在跑」且不刷 300 行
    bar_w = 24
    next_pct = 0

    def _print(i: int) -> None:
        pct = int(100 * i / max(total, 1))
        filled = int(bar_w * i / max(total, 1))
        bar = "#" * filled + "-" * (bar_w - filled)
        print(f"{desc}: {pct:3d}%|{bar}| {i}/{total}", flush=True)

    _print(0)
    for i, batch in enumerate(loader, 1):
        yield batch
        pct = int(100 * i / max(total, 1))
        if pct >= next_pct or i == total:
            _print(i)
            next_pct = ((pct // 5) + 1) * 5


@torch.no_grad()
def evaluate_loader(
    model,
    loader,
    device,
    aspects: list[str],
    desc: str = "eval",
    show_pbar: bool = True,
) -> dict:
    """评估一个 DataLoader；默认显示该类目一条进度条。"""
    model.eval()
    all_preds, all_labels = [], []
    per_aspect_preds = {a: [] for a in aspects}
    per_aspect_labels = {a: [] for a in aspects}
    total_loss, n = 0.0, 0

    for batch in iter_batches(loader, desc=desc, show_pbar=show_pbar):
        batch = {k: v.to(device) for k, v in batch.items()}
        out = model(
            input_ids=batch["input_ids"],
            attention_mask=batch.get("attention_mask"),
            token_type_ids=batch.get("token_type_ids"),
            labels=batch["labels"],
        )
        bs = batch["labels"].size(0)
        total_loss += float(out["loss"].item()) * bs
        n += bs
        preds = out["logits"].argmax(dim=-1).cpu().numpy()
        labels = batch["labels"].cpu().numpy()
        all_preds.extend(preds.reshape(-1).tolist())
        all_labels.extend(labels.reshape(-1).tolist())
        for i, a in enumerate(aspects):
            per_aspect_preds[a].extend(preds[:, i].tolist())
            per_aspect_labels[a].extend(labels[:, i].tolist())

    acc = accuracy_score(all_labels, all_preds) if all_labels else 0.0
    f1 = f1_score(all_labels, all_preds, average="macro", zero_division=0) if all_labels else 0.0
    per_aspect = {
        a: {
            "accuracy": float(
                accuracy_score(per_aspect_labels[a], per_aspect_preds[a])
                if per_aspect_labels[a]
                else 0.0
            )
        }
        for a in aspects
    }
    return {
        "loss": total_loss / max(n, 1),
        "accuracy": float(acc),
        "f1_macro": float(f1),
        "per_aspect": per_aspect,
    }


def safe_subdir(name: str) -> str:
    return name.replace("/", "_").replace("\\", "_")


def _csv_path(cfg: dict, split: str) -> Path:
    data_cfg = cfg["data"]
    processed = resolve_path(data_cfg["processed_dir"])
    key = {"train": "train_file", "val": "val_file", "test": "test_file"}[split]
    return processed / data_cfg.get(key, f"{split}.csv")


def train_one_category(
    cfg: dict,
    category: str,
    max_train_samples: int | None,
    max_val_samples: int | None,
) -> dict:
    aspect_map = get_aspect_map(cfg, category)
    aspects = list(aspect_map.keys())
    if not aspects:
        print(f"[skip] 品类无属性: {category}")
        return {}

    data_cfg = cfg["data"]
    train_csv = _csv_path(cfg, "train")
    val_csv = _csv_path(cfg, "val")

    train_recs = load_wide_records(
        train_csv,
        category=category,
        aspect_map=aspect_map,
        text_col=data_cfg.get("text_col", "评论内容_clean"),
        category_col=data_cfg.get("category_col", "类别"),
        attributes_col=data_cfg.get("attributes_col", "attributes"),
    )
    val_recs = load_wide_records(
        val_csv,
        category=category,
        aspect_map=aspect_map,
        text_col=data_cfg.get("text_col", "评论内容_clean"),
        category_col=data_cfg.get("category_col", "类别"),
        attributes_col=data_cfg.get("attributes_col", "attributes"),
    )

    seed = int(cfg["random_seed"])
    # 每类目内随机抽，避免「文件前部都是图书」导致小样本只见一类
    train_recs = random_sample_records(train_recs, max_train_samples, seed)
    val_recs = random_sample_records(val_recs, max_val_samples, seed + 1)

    print(
        f"[data] 品类={category} train={len(train_recs)} val={len(val_recs)} "
        f"属性={aspects}"
    )
    if len(train_recs) < 2:
        print(f"[skip] 样本过少: {category}")
        return {}

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model_name = resolve_model_name(cfg)
    if not Path(model_name).exists():
        raise FileNotFoundError(
            f"本地预训练不存在: {model_name}\n"
            f"请把 1.0 的 bert-base-chinese 拷到 models/pretrained/bert-base-chinese/"
        )

    tokenizer = BertTokenizer.from_pretrained(model_name)
    train_ds = AspectDataset(train_recs, tokenizer, aspects, int(cfg["max_length"]))
    val_ds = AspectDataset(val_recs, tokenizer, aspects, int(cfg["max_length"]))
    train_loader = DataLoader(train_ds, batch_size=int(cfg["batch_size"]), shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=int(cfg["batch_size"]), shuffle=False)

    model = CategoryAspectBert(model_name, aspects=aspects).to(device)
    optimizer = AdamW(
        model.parameters(),
        lr=float(cfg["learning_rate"]),
        weight_decay=float(cfg.get("weight_decay", 0.01)),
    )
    epochs = int(cfg["epochs"])
    total_steps = max(len(train_loader), 1) * epochs
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=int(total_steps * float(cfg.get("warmup_ratio", 0.1))),
        num_training_steps=total_steps,
    )

    out_dir = resolve_path(cfg["output_dir"]) / safe_subdir(category) / "best"
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    best_f1 = -1.0
    history = []

    for epoch in range(1, epochs + 1):
        model.train()
        running = 0.0
        pbar = tqdm(train_loader, desc=f"{category} epoch {epoch}/{epochs}")
        for batch in pbar:
            batch = {k: v.to(device) for k, v in batch.items()}
            out = model(
                input_ids=batch["input_ids"],
                attention_mask=batch.get("attention_mask"),
                token_type_ids=batch.get("token_type_ids"),
                labels=batch["labels"],
            )
            loss = out["loss"]
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            scheduler.step()
            running += float(loss.item())
            pbar.set_postfix(loss=f"{loss.item():.4f}")

        train_loss = running / max(len(train_loader), 1)
        # 训练中的 val 不打 batch 条，避免和 epoch 条叠在一起刷屏
        val_metrics = evaluate_loader(
            model, val_loader, device, aspects, desc=f"{category} val", show_pbar=False
        )
        record = {
            "epoch": epoch,
            "train_loss": train_loss,
            "val_loss": val_metrics["loss"],
            "val_accuracy": val_metrics["accuracy"],
            "val_f1_macro": val_metrics["f1_macro"],
            "val_per_aspect": val_metrics["per_aspect"],
        }
        history.append(record)
        print(
            f"[epoch {epoch}] train_loss={train_loss:.4f} "
            f"val_acc={val_metrics['accuracy']:.4f} val_f1={val_metrics['f1_macro']:.4f}"
        )

        if val_metrics["f1_macro"] >= best_f1:
            best_f1 = val_metrics["f1_macro"]
            model.save_pretrained(out_dir)
            tokenizer.save_pretrained(out_dir / "tokenizer")
            meta = {
                "category": category,
                "aspects": aspects,
                "aspect_map": aspect_map,
                "best_val_f1_macro": best_f1,
            }
            (out_dir / "meta.json").write_text(
                json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"  -> saved best to {out_dir}")

    metrics_dir = resolve_path(cfg["metrics_dir"])
    metrics_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = metrics_dir / f"{safe_subdir(category)}_metrics.json"
    payload = {
        "category": category,
        "n_train": len(train_ds),
        "n_val": len(val_ds),
        "best_val_f1_macro": best_f1,
        "history": history,
    }
    metrics_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[train] done {category}. metrics -> {metrics_path}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="类目 BERT 多属性微调")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--category", type=str, default=None, help="品类名或 all（默认 all）")
    parser.add_argument("--max_train_samples", type=str, default=None, help="每类目随机条数；null=全量")
    parser.add_argument("--max_val_samples", type=str, default=None)
    args = parser.parse_args()

    cfg = load_config(args.config)
    set_seed(int(cfg["random_seed"]))

    category = args.category or cfg.get("category") or "all"
    max_train = parse_maybe_int(
        args.max_train_samples if args.max_train_samples is not None else cfg.get("max_train_samples")
    )
    max_val = parse_maybe_int(
        args.max_val_samples if args.max_val_samples is not None else cfg.get("max_val_samples")
    )

    if category == "all":
        cats = list_trainable_categories(cfg)
        print(f"[train] 模式=多类目(all)，共 {len(cats)} 个: {cats}")
        print(f"[train] 每类目 max_train_samples={max_train}（None=全量；类目内随机抽，不是文件前N行）")
        if max_train is not None and max_train < 100:
            print(
                f"[warn] max_train_samples={max_train} 过小，指标通常会很低；"
                f"冒烟建议>=200，看效果请全量或单类目全量"
            )
        summary = {}
        for i, cat in enumerate(cats, 1):
            print(f"\n===== [{i}/{len(cats)}] 开始训练类目: {cat} =====")
            summary[cat] = train_one_category(cfg, cat, max_train, max_val)
        summary_path = resolve_path(cfg["metrics_dir"]) / "all_categories_summary.json"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        # 去掉过大 history，只留摘要
        slim = {
            k: {
                "n_train": v.get("n_train"),
                "n_val": v.get("n_val"),
                "best_val_f1_macro": v.get("best_val_f1_macro"),
            }
            for k, v in summary.items()
            if v
        }
        summary_path.write_text(json.dumps(slim, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[train] 全部类目完成 -> {summary_path}")
    else:
        print(f"[train] 模式=单类目，category={category}")
        print(f"[train] max_train_samples={max_train}（None=该品类全量）")
        train_one_category(cfg, category, max_train, max_val)


if __name__ == "__main__":
    main()
