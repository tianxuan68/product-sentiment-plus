"""
案例:
    总 BERT：全品类情感二分类（bert-base-chinese）。

实现步骤:
    1. 加载本地预训练（禁止去 HF 慢下载）
    2. DataLoader（动态 padding）
    3. 训练：前向→损失→清零→反向→更新
    4. 验证集选最优（可阈值搜索抬精确率）
    5. 保存到 models/bert/common/model/bert_all

提速开关:
    --fp16 / --batch-size 48 / --freeze-epochs 1 / --threshold-tune

用法（在 product-sentiment-ai 目录下）:
    python -m models.bert.common.scripts.train --epochs 2 --batch-size 48
"""

# 导包
import argparse
import os

import numpy as np
import torch                                                            # 深度学习框架
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    get_linear_schedule_with_warmup,
)

from models.common.dataset.load_reviews import load_xy
from models.common.metrics.evaluate import compute_metrics, save_metrics
from models.common.pretrained_path import resolve_bert_model


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

    # 保存路径写在函数里
    ckpt_dir = "./models/bert/common/model/bert_all"
    result = "./models/bert/common/results/metrics.json"

    # CUDA 默认开 FP16；--no-fp16 关闭；--fp16 强制开
    if args.fp16 is None:
        use_amp = torch.cuda.is_available()
    else:
        use_amp = bool(args.fp16) and torch.cuda.is_available()

    # 1. 设备
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print('-' * 50)
    print(f'总 BERT 训练（优化版）')
    print('-' * 50)
    print(f'device: {device} | fp16: {use_amp}')
    print(
        f'batch={args.batch_size} lr={args.lr} metric={args.metric} '
        f'threshold_tune={args.threshold_tune} freeze_epochs={args.freeze_epochs}'
    )

    # 2. 加载数据
    x_train, y_train, _ = load_xy("train")
    x_val, y_val, _ = load_xy("val")
    if args.max_samples:
        x_train, y_train = x_train[: args.max_samples], y_train[: args.max_samples]
        n_val = max(args.max_samples // 5, 200)
        x_val, y_val = x_val[:n_val], y_val[:n_val]
    print(f'train={len(x_train)} val={len(x_val)}')

    # 3. 本地预训练（禁止去 HF）
    model_name = resolve_bert_model(args.model_name)
    print(f'model: {model_name}')
    my_tokenizer = AutoTokenizer.from_pretrained(model_name, local_files_only=True)
    my_model = AutoModelForSequenceClassification.from_pretrained(
        model_name, num_labels=2, local_files_only=True
    ).to(device)

    # 4. DataLoader：数据 -> Dataset -> Loader；动态 padding
    collate_fn1 = make_collate(my_tokenizer, args.max_len)
    train_loader = DataLoader(
        ReviewDataset(x_train, y_train, my_tokenizer, args.max_len),
        batch_size=args.batch_size,
        shuffle=True,                   # 参1: 训练集打乱
        collate_fn=collate_fn1,
        pin_memory=torch.cuda.is_available(),
    )
    val_loader = DataLoader(
        ReviewDataset(x_val, y_val, my_tokenizer, args.max_len),
        batch_size=args.batch_size,
        shuffle=False,                  # 参2: 验证集不打乱
        collate_fn=collate_fn1,
        pin_memory=torch.cuda.is_available(),
    )

    # 5. 类别权重：差评少，给更高权重
    n0 = max(y_train.count(0), 1)
    n1 = max(y_train.count(1), 1)
    w0, w1 = (n0 + n1) / (2.0 * n0), (n0 + n1) / (2.0 * n1)
    class_weight = torch.tensor([w0, w1], dtype=torch.float, device=device)
    print(f'class_weight: 差评={w0:.3f} 好评={w1:.3f}')

    # 6. 优化器：W新 = W旧 - 学习率 * 梯度（AdamW 带动量/衰减）
    optimizer = torch.optim.AdamW(
        my_model.parameters(), lr=args.lr, weight_decay=args.weight_decay
    )
    total_steps = max(len(train_loader) * args.epochs, 1)
    sched = get_linear_schedule_with_warmup(
        optimizer, num_warmup_steps=int(0.1 * total_steps), num_training_steps=total_steps
    )
    amp_device = "cuda" if device.type == "cuda" else "cpu"
    scaler = torch.amp.GradScaler(amp_device, enabled=use_amp)

    best_score = -1.0
    bad_epochs = 0
    best_thr = 0.5

    # 7. 训练循环
    for epoch in range(1, args.epochs + 1):
        if args.freeze_epochs > 0:
            frozen = epoch <= args.freeze_epochs
            set_requires_grad(my_model, requires_grad=not frozen)
            print(f'epoch={epoch} encoder_frozen={frozen}')

        my_model.train()
        losses = []
        for batch in train_loader:
            labels = batch["labels"].to(device, non_blocking=True)
            inputs = {
                k: v.to(device, non_blocking=True)
                for k, v in batch.items()
                if k != "labels"
            }
            optimizer.zero_grad(set_to_none=True)
            with torch.amp.autocast(amp_device, enabled=use_amp):
                out = my_model(**inputs)
                # CrossEntropyLoss = softmax() + 损失计算 → 输出层勿再 Softmax
                loss = F.cross_entropy(out.logits, labels, weight=class_weight)
            scaler.scale(loss).backward()
            if args.grad_clip > 0:
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(my_model.parameters(), args.grad_clip)
            scaler.step(optimizer)
            scaler.update()
            sched.step()
            losses.append(float(loss.item()))

        logits, golds = predict_logits(my_model, val_loader, device, use_amp)
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
            f'epoch={epoch} loss={np.mean(losses):.4f} thr={thr:.2f} '
            f'acc={metrics["accuracy"]:.4f} prec={metrics["precision"]:.4f} '
            f'rec={metrics["recall"]:.4f} f1={metrics["f1"]:.4f}'
        )

        if score > best_score:
            best_score = score
            best_thr = thr
            bad_epochs = 0
            os.makedirs(ckpt_dir, exist_ok=True)
            my_model.save_pretrained(ckpt_dir)
            my_tokenizer.save_pretrained(ckpt_dir)
            with open(ckpt_dir + "/threshold.txt", "w", encoding="utf-8") as f:
                f.write(str(best_thr))
            save_metrics(
                metrics,
                result,
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
            print(f'  ✓ 更新最优 {args.metric}={best_score:.4f}')
        else:
            bad_epochs += 1
            print(f'  未提升 ({bad_epochs}/{args.patience})')
            if bad_epochs >= args.patience:
                print(f'早停')
                break

    print(f'最佳 {args.metric}={best_score:.4f} thr={best_thr:.2f} 已保存: {ckpt_dir}')


if __name__ == "__main__":
    # 1. 训练总 BERT
    main()
