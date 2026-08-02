"""
案例:
    模型蒸馏：用总 BERT（教师）软标签，训练轻量学生模型。

损失口诀:
    L = α * CE(学生, 硬标签) + (1-α) * T² * KL(教师软标签 || 学生软标签)

大白话:
    老师把「软答案」教给小学生；学生参数更少，推理更快。
依赖: 先训练 models/bert/common（教师）。

用法:
    python train.py
    python train.py --max-samples 2000 --epochs 2
"""

# 导包
import argparse
import os

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    BertConfig,
    BertForSequenceClassification,
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


def build_student(teacher) -> BertForSequenceClassification:
    """更小 BERT：4 层、隐层 312，词表与教师一致。"""
    tcfg = teacher.config
    # hidden_size 必须能被 num_attention_heads 整除
    hidden_size = 312
    num_heads = 12
    assert hidden_size % num_heads == 0
    cfg = BertConfig(
        vocab_size=tcfg.vocab_size,
        hidden_size=hidden_size,
        num_hidden_layers=4,
        num_attention_heads=num_heads,
        intermediate_size=1200,
        max_position_embeddings=getattr(tcfg, "max_position_embeddings", 512),
        type_vocab_size=getattr(tcfg, "type_vocab_size", 2),
        num_labels=2,
    )
    return BertForSequenceClassification(cfg)


def distill_loss(student_logits, teacher_logits, labels, temperature: float, alpha: float):
    hard = F.cross_entropy(student_logits, labels)
    t = temperature
    soft_s = F.log_softmax(student_logits / t, dim=-1)
    # KL(teacher || student)
    soft = F.kl_div(
        soft_s,
        F.softmax(teacher_logits / t, dim=-1),
        reduction="batchmean",
    ) * (t * t)
    return alpha * hard + (1.0 - alpha) * soft


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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--teacher", default=None, help="教师权重目录，默认 bert_all")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=5e-5)
    parser.add_argument("--max-len", type=int, default=128)
    parser.add_argument("--temperature", type=float, default=4.0)
    parser.add_argument("--alpha", type=float, default=0.3, help="硬标签 CE 权重")
    parser.add_argument("--max-samples", type=int, default=None)
    args = parser.parse_args()

    # 保存路径写在函数里
    teacher_dir = "./models/bert/common/model/bert_all"
    ckpt_dir = "./models/bert/distill/model/bert_student"
    result = "./models/bert/distill/results/metrics.json"

    teacher_path = args.teacher if args.teacher else teacher_dir
    if not os.path.exists(os.path.join(teacher_path, "config.json")):
        # 退回未微调的预训练，仍可做蒸馏实验
        fallback = resolve_bert_model()
        print(f'未找到微调教师 {teacher_path}，改用: {fallback}')
        print(f'建议先跑: python models/bert/common/scripts/train.py')
        teacher_path = fallback

    # 1. 设备
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print('-' * 50)
    print(f'BERT 知识蒸馏')
    print('-' * 50)
    print(f'device: {device}')
    print(f'teacher: {teacher_path}')

    # 2. 加载数据
    x_train, y_train, _ = load_xy("train")
    x_val, y_val, _ = load_xy("val")
    if args.max_samples:
        x_train, y_train = x_train[: args.max_samples], y_train[: args.max_samples]
        n_val = max(args.max_samples // 5, 200)
        x_val, y_val = x_val[:n_val], y_val[:n_val]

    # 3. 教师冻结 + 学生新建
    my_tokenizer = AutoTokenizer.from_pretrained(
        teacher_path, local_files_only=True
    )
    teacher = AutoModelForSequenceClassification.from_pretrained(
        teacher_path, num_labels=2, local_files_only=True
    ).to(device)
    teacher.eval()
    for p in teacher.parameters():
        p.requires_grad = False

    student = build_student(teacher).to(device)
    print(f'学生参数量: {sum(p.numel() for p in student.parameters()) / 1e6:.2f} M')
    print(f'教师参数量: {sum(p.numel() for p in teacher.parameters()) / 1e6:.2f} M')

    # 4. DataLoader
    train_loader = DataLoader(
        ReviewDataset(x_train, y_train, my_tokenizer, args.max_len),
        batch_size=args.batch_size,
        shuffle=True,
    )
    val_loader = DataLoader(
        ReviewDataset(x_val, y_val, my_tokenizer, args.max_len),
        batch_size=args.batch_size,
    )

    # 5. 优化器
    optimizer = torch.optim.AdamW(student.parameters(), lr=args.lr)
    total_steps = max(len(train_loader) * args.epochs, 1)
    sched = get_linear_schedule_with_warmup(
        optimizer, num_warmup_steps=int(0.1 * total_steps), num_training_steps=total_steps
    )

    # 6. 蒸馏训练
    best_f1 = -1.0
    for epoch in range(1, args.epochs + 1):
        student.train()
        losses = []
        for batch in train_loader:
            labels = batch["labels"].to(device)
            inputs = {k: v.to(device) for k, v in batch.items() if k != "labels"}
            with torch.no_grad():
                t_logits = teacher(**inputs).logits
            s_logits = student(**inputs).logits
            # CrossEntropyLoss = softmax() + 损失；蒸馏再加软标签 KL
            loss = distill_loss(
                s_logits, t_logits, labels, args.temperature, args.alpha
            )
            loss.backward()
            optimizer.step()
            sched.step()
            optimizer.zero_grad()
            losses.append(loss.item())

        golds, preds = predict(student, val_loader, device)
        metrics = compute_metrics(golds, preds)
        print(
            f'epoch={epoch} loss={np.mean(losses):.4f} '
            f'acc={metrics["accuracy"]:.4f} f1={metrics["f1"]:.4f}'
        )
        if metrics["f1"] > best_f1:
            best_f1 = metrics["f1"]
            os.makedirs(ckpt_dir, exist_ok=True)
            student.save_pretrained(ckpt_dir)
            my_tokenizer.save_pretrained(ckpt_dir)
            save_metrics(
                metrics,
                result,
                {
                    "model": "bert_distill_student",
                    "teacher": teacher_path,
                    "temperature": args.temperature,
                    "alpha": args.alpha,
                    "epoch": epoch,
                    "train_size": len(x_train),
                },
            )

    print(f'最佳 f1={best_f1:.4f} 已保存: {ckpt_dir}')


if __name__ == "__main__":
    # 1. 蒸馏训练入口
    main()
