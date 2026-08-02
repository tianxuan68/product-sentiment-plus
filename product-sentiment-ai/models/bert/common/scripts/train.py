"""
总 BERT：全品类情感二分类（bert-base-chinese）

提速 / 提效果常用开关：
  --fp16                 半精度（CUDA 默认开）
  --batch-size 48/64     显存够就加大
  --threshold-tune       验证集搜阈值，抬精确率
  --metric precision     按精确率存最优（默认 f1）
  --freeze-epochs 1      先冻 BERT 只训分类头，再解冻
  --max-samples N        冒烟调试

用法：
  python train.py --epochs 2 --batch-size 48
  python train.py --epochs 3 --batch-size 48 --threshold-tune --metric precision
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
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

CKPT_DIR = Path(__file__).resolve().parents[1] / "checkpoints" / "bert_all"
RESULT = Path(__file__).resolve().parents[1] / "results" / "metrics.json"


class ReviewDataset(Dataset):
    """只存原文，padding 放到 collate，避免每条都 pad 到 max_len（更省更快）。"""

    def __init__(self, texts, labels, tokenizer, max_len=128):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_len = max_len

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        return self.texts[idx], int(self.labels[idx])


def make_collate(tokenizer, max_len: int):
    def collate(batch):
        texts, labels = zip(*batch)
        enc = tokenizer(
            list(texts),
            truncation=True,
            padding=True,  # 动态 pad 到本 batch 最长
            max_length=max_len,
            return_tensors="pt",
        )
        enc["labels"] = torch.tensor(labels, dtype=torch.long)
        return enc

    return collate


@torch.no_grad()
def predict_logits(model, loader, device, use_amp: bool):
    model.eval()
    logits_all, golds = [], []
    amp_device = "cuda" if device.type == "cuda" else "cpu"
    for batch in loader:
        labels = batch.pop("labels")
        batch = {k: v.to(device, non_blocking=True) for k, v in batch.items()}
        with torch.amp.autocast(amp_device, enabled=use_amp):
            logits = model(**batch).logits
        logits_all.append(logits.float().cpu())
        golds.extend(labels.tolist())
    return torch.cat(logits_all, dim=0), golds


def tune_threshold(logits: torch.Tensor, golds: list[int], metric: str = "f1"):
    """在验证集上搜正类阈值，常用来抬 precision。"""
    probs = F.softmax(logits, dim=-1)[:, 1].numpy()
    y = np.asarray(golds)
    best = {"threshold": 0.5, "score": -1.0, "metrics": None}
    for thr in np.arange(0.30, 0.90, 0.02):
        pred = (probs >= thr).astype(int)
        m = compute_metrics(y, pred)
        score = m.get(metric, m["f1"])
        if score > best["score"]:
            best = {"threshold": float(thr), "score": float(score), "metrics": m}
    return best


def set_requires_grad(model, requires_grad: bool) -> None:
    for name, p in model.named_parameters():
        if name.startswith("classifier"):
            p.requires_grad = True
        else:
            p.requires_grad = requires_grad


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model-name",
        default=None,
        help="本地模型目录；默认自动解析 pretrained / bert_all",
    )
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--batch-size", type=int, default=48)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--weight-decay", type=float, default=0.01)
    parser.add_argument("--max-len", type=int, default=128)
    parser.add_argument("--max-samples", type=int, default=None)
    amp_group = parser.add_mutually_exclusive_group()
    amp_group.add_argument(
        "--fp16",
        dest="fp16",
        action="store_true",
        help="强制开启 FP16（CUDA 默认已开）",
    )
    amp_group.add_argument(
        "--no-fp16",
        dest="fp16",
        action="store_false",
        help="关闭 FP16",
    )
    parser.set_defaults(fp16=None)
    parser.add_argument("--threshold-tune", action="store_true")
    parser.add_argument(
        "--metric",
        default="f1",
        choices=["f1", "precision", "accuracy", "recall"],
        help="选最优 checkpoint 的指标",
    )
    parser.add_argument(
        "--freeze-epochs",
        type=int,
        default=0,
        help="前 N 个 epoch 只训分类头（提速+稳）",
    )
    parser.add_argument("--grad-clip", type=float, default=1.0)
    parser.add_argument("--patience", type=int, default=2, help="早停耐心")
    args = parser.parse_args()
    # CUDA 默认开 FP16；--no-fp16 关闭；--fp16 强制开
    if args.fp16 is None:
        use_amp = torch.cuda.is_available()
    else:
        use_amp = bool(args.fp16) and torch.cuda.is_available()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("=" * 50)
    print("总 BERT 训练（优化版）")
    print("=" * 50)
    print("device:", device, "| fp16:", use_amp)
    print(
        f"batch={args.batch_size} lr={args.lr} metric={args.metric} "
        f"threshold_tune={args.threshold_tune} freeze_epochs={args.freeze_epochs}"
    )

    x_train, y_train, _ = load_xy("train")
    x_val, y_val, _ = load_xy("val")
    if args.max_samples:
        x_train, y_train = x_train[: args.max_samples], y_train[: args.max_samples]
        n_val = max(args.max_samples // 5, 200)
        x_val, y_val = x_val[:n_val], y_val[:n_val]
    print(f"train={len(x_train)} val={len(x_val)}")

    model_name = resolve_bert_model(args.model_name)
    print("model:", model_name)
    tokenizer = AutoTokenizer.from_pretrained(model_name, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_name, num_labels=2, local_files_only=True
    ).to(device)

    collate = make_collate(tokenizer, args.max_len)
    train_loader = DataLoader(
        ReviewDataset(x_train, y_train, tokenizer, args.max_len),
        batch_size=args.batch_size,
        shuffle=True,
        collate_fn=collate,
        pin_memory=torch.cuda.is_available(),
    )
    val_loader = DataLoader(
        ReviewDataset(x_val, y_val, tokenizer, args.max_len),
        batch_size=args.batch_size,
        collate_fn=collate,
        pin_memory=torch.cuda.is_available(),
    )

    # 分类不平衡：给差评更高权重，常能稳住精确率/占比少数类
    n0 = max(y_train.count(0), 1)
    n1 = max(y_train.count(1), 1)
    # 权重反比于频次，再归一
    w0, w1 = (n0 + n1) / (2.0 * n0), (n0 + n1) / (2.0 * n1)
    class_weight = torch.tensor([w0, w1], dtype=torch.float, device=device)
    print(f"class_weight: 差评={w0:.3f} 好评={w1:.3f}")

    optim = torch.optim.AdamW(
        model.parameters(), lr=args.lr, weight_decay=args.weight_decay
    )
    total_steps = max(len(train_loader) * args.epochs, 1)
    sched = get_linear_schedule_with_warmup(
        optim, num_warmup_steps=int(0.1 * total_steps), num_training_steps=total_steps
    )
    amp_device = "cuda" if device.type == "cuda" else "cpu"
    scaler = torch.amp.GradScaler(amp_device, enabled=use_amp)

    best_score = -1.0
    bad_epochs = 0
    best_thr = 0.5

    for epoch in range(1, args.epochs + 1):
        if args.freeze_epochs > 0:
            frozen = epoch <= args.freeze_epochs
            set_requires_grad(model, requires_grad=not frozen)
            print(f"epoch={epoch} encoder_frozen={frozen}")

        model.train()
        losses = []
        for batch in train_loader:
            labels = batch["labels"].to(device, non_blocking=True)
            inputs = {
                k: v.to(device, non_blocking=True)
                for k, v in batch.items()
                if k != "labels"
            }
            optim.zero_grad(set_to_none=True)
            with torch.amp.autocast(amp_device, enabled=use_amp):
                out = model(**inputs)
                loss = F.cross_entropy(out.logits, labels, weight=class_weight)
            scaler.scale(loss).backward()
            if args.grad_clip > 0:
                scaler.unscale_(optim)
                torch.nn.utils.clip_grad_norm_(model.parameters(), args.grad_clip)
            scaler.step(optim)
            scaler.update()
            sched.step()
            losses.append(float(loss.item()))

        logits, golds = predict_logits(model, val_loader, device, use_amp)
        if args.threshold_tune:
            tuned = tune_threshold(logits, golds, metric=args.metric)
            thr = tuned["threshold"]
            metrics = tuned["metrics"]
        else:
            thr = 0.5
            pred = logits.argmax(-1).tolist()
            metrics = compute_metrics(golds, pred)

        score = metrics[args.metric]
        print(
            f"epoch={epoch} loss={np.mean(losses):.4f} thr={thr:.2f} "
            f"acc={metrics['accuracy']:.4f} prec={metrics['precision']:.4f} "
            f"rec={metrics['recall']:.4f} f1={metrics['f1']:.4f}"
        )

        if score > best_score:
            best_score = score
            best_thr = thr
            bad_epochs = 0
            CKPT_DIR.mkdir(parents=True, exist_ok=True)
            model.save_pretrained(CKPT_DIR)
            tokenizer.save_pretrained(CKPT_DIR)
            (CKPT_DIR / "threshold.txt").write_text(str(best_thr), encoding="utf-8")
            save_metrics(
                metrics,
                RESULT,
                {
                    "model": "bert_all",
                    "base": model_name,
                    "epoch": epoch,
                    "train_size": len(x_train),
                    "threshold": best_thr,
                    "select_metric": args.metric,
                    "fp16": use_amp,
                },
            )
            print(f"  ✓ 更新最优 {args.metric}={best_score:.4f}")
        else:
            bad_epochs += 1
            print(f"  未提升 ({bad_epochs}/{args.patience})")
            if bad_epochs >= args.patience:
                print("早停")
                break

    print(f"最佳 {args.metric}={best_score:.4f} thr={best_thr:.2f} 已保存: {CKPT_DIR}")


if __name__ == "__main__":
    main()
