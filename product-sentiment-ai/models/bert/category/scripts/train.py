"""
案例:
    类目 BERT：在评论数最多的品类上微调（相对总 BERT 的分品类加强）。

大白话:
    总模型看全部；这里挑样本多的品类再加一把劲。
"""

# 导包
import argparse
import os

import numpy as np
import torch
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


def default_model_name():
    # 有总 BERT 就接着微调；没有就用预训练
    bert_all = "./models/bert/common/model/bert_all"
    has_cfg = os.path.exists(bert_all + "/config.json")
    has_w = os.path.exists(bert_all + "/model.safetensors") or os.path.exists(
        bert_all + "/pytorch_model.bin"
    )
    if has_cfg and has_w:
        return os.path.abspath(bert_all)
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

    # 保存路径写在函数里
    ckpt_dir = "./models/bert/category/model/bert_category"
    result = "./models/bert/category/results/metrics.json"

    # 1. 设备
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print('-' * 50)
    print(f'类目 BERT 训练')
    print('-' * 50)
    print(f'device: {device}')

    # 2. 按品类筛数据
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
    print(f'品类: {cate} | train={len(x_train)} val={len(x_val)}')
    if len(x_train) < 50 or len(x_val) < 20:
        raise RuntimeError("该类目样本过少，请换 --category 或增大数据")

    # 3. 加载本地预训练 / 总 BERT
    model_name = resolve_bert_model(args.model_name or default_model_name())
    print(f'model: {model_name}')
    my_tokenizer = AutoTokenizer.from_pretrained(model_name, local_files_only=True)
    my_model = AutoModelForSequenceClassification.from_pretrained(
        model_name, num_labels=2, local_files_only=True
    ).to(device)

    # 4. DataLoader（数据 -> Dataset -> Loader）
    train_loader = DataLoader(
        ReviewDataset(x_train, y_train, my_tokenizer, args.max_len),
        batch_size=args.batch_size,
        shuffle=True,                   # 参1: 训练集打乱
    )
    val_loader = DataLoader(
        ReviewDataset(x_val, y_val, my_tokenizer, args.max_len),
        batch_size=args.batch_size,
        shuffle=False,                  # 参2: 验证集不打乱
    )

    # 5. 优化器 + 调度
    optimizer = torch.optim.AdamW(my_model.parameters(), lr=args.lr)
    total_steps = max(len(train_loader) * args.epochs, 1)
    sched = get_linear_schedule_with_warmup(
        optimizer, num_warmup_steps=int(0.1 * total_steps), num_training_steps=total_steps
    )

    # 6. 训练循环：前向→损失→反向→更新
    best_f1 = -1.0
    for epoch in range(1, args.epochs + 1):
        my_model.train()
        losses = []
        for batch in train_loader:
            batch = {k: v.to(device) for k, v in batch.items()}
            out = my_model(**batch)
            out.loss.backward()
            optimizer.step()
            sched.step()
            optimizer.zero_grad()
            losses.append(out.loss.item())
        golds, preds = predict(my_model, val_loader, device)
        metrics = compute_metrics(golds, preds)
        print(
            f'epoch={epoch} loss={np.mean(losses):.4f} '
            f'acc={metrics["accuracy"]:.4f} f1={metrics["f1"]:.4f}'
        )
        if metrics["f1"] > best_f1:
            best_f1 = metrics["f1"]
            os.makedirs(ckpt_dir, exist_ok=True)
            my_model.save_pretrained(ckpt_dir)
            my_tokenizer.save_pretrained(ckpt_dir)
            save_metrics(
                metrics,
                result,
                {
                    "model": "bert_category",
                    "categories": cate,
                    "epoch": epoch,
                    "train_size": len(x_train),
                },
            )

    print(f'最佳 f1={best_f1:.4f} 已保存: {ckpt_dir}')


if __name__ == "__main__":
    # 1. 训练类目 BERT
    main()
