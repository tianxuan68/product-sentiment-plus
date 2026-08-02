"""
类目 BERT：在评论数最多的品类上微调（相对总 BERT 的分品类加强）
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
)

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "models"))

from common.dataset.load_reviews import load_xy  # noqa: E402
from common.metrics.evaluate import compute_metrics, save_metrics  # noqa: E402
from common.pretrained_path import resolve_bert_model  # noqa: E402

CKPT_DIR = Path(__file__).resolve().parents[1] / "checkpoints" / "bert_category"
RESULT = Path(__file__).resolve().parents[1] / "results" / "metrics.json"
_BERT_ALL = Path(__file__).resolve().parents[2] / "common" / "checkpoints" / "bert_all"


class ReviewDataset(Dataset):
    def __init__(self, texts, labels, tokenizer, max_len=128):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_len = max_len

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        enc = self.tokenizer(
            self.texts[idx],
            truncation=True,
            padding="max_length",
            max_length=self.max_len,
            return_tensors="pt",
        )
        item = {k: v.squeeze(0) for k, v in enc.items()}
        item["labels"] = torch.tensor(self.labels[idx], dtype=torch.long)
        return item


@torch.no_grad()
def predict(model, loader, device):
    model.eval()
    preds, golds = [], []
    for batch in loader:
        labels = batch.pop("labels")
        batch = {k: v.to(device) for k, v in batch.items()}
        logits = model(**batch).logits
        preds.extend(logits.argmax(-1).cpu().tolist())
        golds.extend(labels.tolist())
    return golds, preds


def default_model_name() -> str:
    if (_BERT_ALL / "config.json").exists() and (
        (_BERT_ALL / "model.safetensors").exists()
        or (_BERT_ALL / "pytorch_model.bin").exists()
    ):
        return str(_BERT_ALL.resolve())
    return resolve_bert_model()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-name", default=None)
    parser.add_argument("--category", default=None, help="指定品类名；默认取样本最多品类")
    parser.add_argument("--top-n-categories", type=int, default=3)
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--max-len", type=int, default=128)
    parser.add_argument("--max-samples", type=int, default=None)
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("=" * 50)
    print("类目 BERT 训练")
    print("=" * 50)

    _, _, df_train = load_xy("train")
    _, _, df_val = load_xy("val")

    if args.category:
        tops = {args.category}
    else:
        tops = set(df_train["category"].value_counts().head(args.top_n_categories).index)

    tr = df_train[df_train["category"].isin(tops)]
    va = df_val[df_val["category"].isin(tops)]
    x_train = tr["sentence"].fillna("").astype(str).tolist()
    y_train = tr["sentiment"].astype(int).tolist()
    x_val = va["sentence"].fillna("").astype(str).tolist()
    y_val = va["sentiment"].astype(int).tolist()

    if args.max_samples:
        x_train, y_train = x_train[: args.max_samples], y_train[: args.max_samples]
        n_val = max(args.max_samples // 5, 100)
        x_val, y_val = x_val[:n_val], y_val[:n_val]

    cate = ",".join(sorted(tops))
    print(f"品类: {cate} | train={len(x_train)} val={len(x_val)}")
    if len(x_train) < 50 or len(x_val) < 20:
        raise RuntimeError("该类目样本过少，请换 --category 或增大数据")

    model_name = resolve_bert_model(args.model_name or default_model_name())
    print("model:", model_name)
    tokenizer = AutoTokenizer.from_pretrained(model_name, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name, num_labels=2, local_files_only=True
    ).to(device)

    train_loader = DataLoader(
        ReviewDataset(x_train, y_train, tokenizer, args.max_len),
        batch_size=args.batch_size,
        shuffle=True,
    )
    val_loader = DataLoader(
        ReviewDataset(x_val, y_val, tokenizer, args.max_len),
        batch_size=args.batch_size,
    )

    optim = torch.optim.AdamW(model.parameters(), lr=args.lr)
    total_steps = max(len(train_loader) * args.epochs, 1)
    sched = get_linear_schedule_with_warmup(
        optim, num_warmup_steps=int(0.1 * total_steps), num_training_steps=total_steps
    )

    best_f1 = -1.0
    for epoch in range(1, args.epochs + 1):
        model.train()
        losses = []
        for batch in train_loader:
            batch = {k: v.to(device) for k, v in batch.items()}
            out = model(**batch)
            out.loss.backward()
            optim.step()
            sched.step()
            optim.zero_grad()
            losses.append(out.loss.item())
        golds, preds = predict(model, val_loader, device)
        metrics = compute_metrics(golds, preds)
        print(
            f"epoch={epoch} loss={np.mean(losses):.4f} "
            f"acc={metrics['accuracy']:.4f} f1={metrics['f1']:.4f}"
        )
        if metrics["f1"] > best_f1:
            best_f1 = metrics["f1"]
            CKPT_DIR.mkdir(parents=True, exist_ok=True)
            model.save_pretrained(CKPT_DIR)
            tokenizer.save_pretrained(CKPT_DIR)
            save_metrics(
                metrics,
                RESULT,
                {
                    "model": "bert_category",
                    "categories": cate,
                    "epoch": epoch,
                    "train_size": len(x_train),
                },
            )

    print(f"最佳 f1={best_f1:.4f} 已保存: {CKPT_DIR}")


if __name__ == "__main__":
    main()
