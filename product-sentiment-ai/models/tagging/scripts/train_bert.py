"""
案例:
    BERT 多标签多分类打标（一条评论可同时命中多个方面标签）。

大白话:
    不再只分好评差评；29 个标签各自独立开/关（sigmoid）。
    靠语义向量扛「质量很好」这类规则 OOV。

用法（在 product-sentiment-ai 目录下）:
    python -m models.tagging.scripts.train_bert --epochs 2 --batch-size 32
    python -m models.tagging.scripts.train_bert --max-samples 8000 --epochs 1
"""

# 导包
import argparse
import json
import os

import numpy as np
import torch
from sklearn.preprocessing import MultiLabelBinarizer
from torch.utils.data import DataLoader, Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
)

from models.common.dataset.load_multilabel_tags import (
    all_tag_names,
    load_multilabel,
    tag_meta_map,
)
from models.common.metrics.evaluate import save_metrics
from models.common.metrics.evaluate_multilabel import compute_multilabel_metrics
from models.common.pretrained_path import resolve_bert_model


class MultiLabelDataset(Dataset):
    def __init__(self, texts, y, tokenizer, max_len=128):
        self.texts = texts
        self.y = y.astype(np.float32)
        self.tokenizer = tokenizer
        self.max_len = max_len

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        return self.texts[idx], self.y[idx]


def make_collate(tokenizer, max_len):
    def collate(batch):
        texts, labels = zip(*batch)
        enc = tokenizer(
            list(texts),
            truncation=True,
            padding=True,
            max_length=max_len,
            return_tensors="pt",
        )
        enc["labels"] = torch.tensor(np.stack(labels), dtype=torch.float32)
        return enc

    return collate


@torch.no_grad()
def predict_probs(model, loader, device, use_amp):
    model.eval()
    probs_all, golds = [], []
    amp_device = "cuda" if device.type == "cuda" else "cpu"
    for batch in loader:
        labels = batch.pop("labels")
        batch = {k: v.to(device, non_blocking=True) for k, v in batch.items()}
        with torch.amp.autocast(amp_device, enabled=use_amp):
            logits = model(**batch).logits
        probs_all.append(torch.sigmoid(logits.float()).cpu())
        golds.append(labels)
    return torch.cat(probs_all, dim=0).numpy(), torch.cat(golds, dim=0).numpy()


def tune_threshold(probs, y_true):
    best = {"threshold": 0.5, "f1": -1.0}
    for thr in np.arange(0.20, 0.70, 0.02):
        pred = (probs >= thr).astype(int)
        m = compute_multilabel_metrics(y_true, pred)
        if m["f1_micro"] > best["f1"]:
            best = {"threshold": float(thr), "f1": float(m["f1_micro"]), "metrics": m}
    return best


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-name", default=None)
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--max-len", type=int, default=128)
    parser.add_argument("--max-samples", type=int, default=None)
    parser.add_argument("--threshold", type=float, default=None, help="不传则验证集自动搜")
    parser.add_argument("--no-augment", action="store_true")
    parser.add_argument("--fp16", action="store_true", default=True)
    parser.add_argument("--no-fp16", action="store_true")
    args = parser.parse_args()
    use_amp = args.fp16 and (not args.no_fp16) and torch.cuda.is_available()

    ckpt_dir = "./models/tagging/model/bert_multilabel"
    result = "./models/tagging/results/metrics_bert.json"

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print('-' * 50)
    print(f'BERT 多标签多分类打标')
    print('-' * 50)
    print(f'device={device} fp16={use_amp}')

    # 1. 数据 → multi-hot
    x_train, y_train_lists, _ = load_multilabel(
        "train", max_samples=args.max_samples, augment=not args.no_augment
    )
    val_max = max(args.max_samples // 5, 300) if args.max_samples else None
    x_val, y_val_lists, _ = load_multilabel("val", max_samples=val_max, augment=False)

    classes = all_tag_names()
    mlb = MultiLabelBinarizer(classes=classes)
    y_train = mlb.fit_transform(y_train_lists)
    y_val = mlb.transform(y_val_lists)
    n_labels = len(classes)
    print(f'标签数={n_labels} train={len(x_train)} val={len(x_val)}')

    # 2. 本地 BERT + multi_label_classification
    model_name = resolve_bert_model(args.model_name)
    tokenizer = AutoTokenizer.from_pretrained(model_name, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name,
        num_labels=n_labels,
        problem_type="multi_label_classification",
        local_files_only=True,
        ignore_mismatched_sizes=True,
    ).to(device)

    # 类别不平衡：稀有标签加权，但封顶防炸
    pos = y_train.sum(axis=0)
    neg = y_train.shape[0] - pos
    pw = np.where(pos > 0, neg / np.maximum(pos, 1), 1.0)
    pw = np.clip(pw, 1.0, 15.0)
    pos_weight = torch.tensor(pw, dtype=torch.float32, device=device)
    bce = torch.nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    train_loader = DataLoader(
        MultiLabelDataset(x_train, y_train, tokenizer, args.max_len),
        batch_size=args.batch_size,
        shuffle=True,
        collate_fn=make_collate(tokenizer, args.max_len),
    )
    val_loader = DataLoader(
        MultiLabelDataset(x_val, y_val, tokenizer, args.max_len),
        batch_size=args.batch_size,
        shuffle=False,
        collate_fn=make_collate(tokenizer, args.max_len),
    )

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    total_steps = max(len(train_loader) * args.epochs, 1)
    sched = get_linear_schedule_with_warmup(
        optimizer, num_warmup_steps=int(0.1 * total_steps), num_training_steps=total_steps
    )
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
    amp_device = "cuda" if device.type == "cuda" else "cpu"

    best_f1 = -1.0
    best_thr = 0.35
    for epoch in range(1, args.epochs + 1):
        model.train()
        losses = []
        for batch in train_loader:
            labels = batch.pop("labels").to(device)
            batch = {k: v.to(device, non_blocking=True) for k, v in batch.items()}
            optimizer.zero_grad(set_to_none=True)
            with torch.amp.autocast(amp_device, enabled=use_amp):
                logits = model(**batch).logits
                loss = bce(logits, labels)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
            sched.step()
            losses.append(float(loss.item()))

        probs, gold = predict_probs(model, val_loader, device, use_amp)
        if args.threshold is None:
            tuned = tune_threshold(probs, gold)
            thr = tuned["threshold"]
            metrics = tuned["metrics"]
        else:
            thr = args.threshold
            pred = (probs >= thr).astype(int)
            metrics = compute_multilabel_metrics(gold, pred, label_names=list(classes))

        print(
            f'epoch={epoch} loss={np.mean(losses):.4f} '
            f'thr={thr:.2f} f1_micro={metrics["f1_micro"]:.4f} '
            f'f1_macro={metrics["f1_macro"]:.4f}'
        )

        if metrics["f1_micro"] > best_f1:
            best_f1 = metrics["f1_micro"]
            best_thr = thr
            os.makedirs(ckpt_dir, exist_ok=True)
            model.save_pretrained(ckpt_dir)
            tokenizer.save_pretrained(ckpt_dir)
            with open(os.path.join(ckpt_dir, "label_names.json"), "w", encoding="utf-8") as f:
                json.dump(list(classes), f, ensure_ascii=False, indent=2)
            with open(os.path.join(ckpt_dir, "tag_meta.json"), "w", encoding="utf-8") as f:
                json.dump(tag_meta_map(), f, ensure_ascii=False, indent=2)
            with open(os.path.join(ckpt_dir, "threshold.txt"), "w", encoding="utf-8") as f:
                f.write(str(best_thr))
            save_metrics(
                metrics,
                result,
                {
                    "model": "tagging_bert_multilabel",
                    "train_size": len(x_train),
                    "threshold": best_thr,
                    "n_labels": n_labels,
                    "epoch": epoch,
                },
            )
            cfg = os.path.join(ckpt_dir, "config.json")
            print(f'已落盘权重: {cfg} exists={os.path.exists(cfg)}')

    if not os.path.exists(os.path.join(ckpt_dir, "config.json")):
        raise RuntimeError(f"训练结束但未找到权重目录: {ckpt_dir}")
    print(f'最佳 f1_micro={best_f1:.4f} thr={best_thr:.2f} 已保存: {ckpt_dir}')


if __name__ == "__main__":
    main()
