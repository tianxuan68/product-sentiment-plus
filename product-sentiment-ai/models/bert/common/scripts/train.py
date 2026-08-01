# -*- coding: utf-8 -*-
"""
train.py —— BERT 多标签分类训练主程序

运行方式：
    python scripts/train.py            # 使用 Config 默认配置
    python scripts/train.py --epochs 5 # 覆盖训练轮数

流程：
    1. 自动选择 GPU / CPU
    2. 加载标签词表与训练/验证/测试数据
    3. 构建多标签数据集与 DataLoader
    4. 构建 BERT 多标签模型
    5. 训练若干轮，每轮在验证集上评估
    6. 保存验证集最优模型与最终模型到 checkpoints/
    7. 在测试集上评估并输出指标到 results/
"""

import os
import sys
import json
import csv
import random
import argparse

# 把本脚本所在目录加入 sys.path，保证直接运行时也能互相 import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from tqdm import tqdm
from transformers import AutoTokenizer, get_linear_schedule_with_warmup
from sklearn.metrics import (
    f1_score,
    precision_score,
    recall_score,
    accuracy_score,
    hamming_loss,
)

from config import Config, get_device, PROJECT_ROOT
from data_utils import load_tag_vocab, load_labeled_data
from dataset import MultiLabelDataset, build_label_index, collate_batch
from model import BertMultiLabelModel

# 降低 transformers 日志噪音：本模型加载时会报告「MLM 预训练头权重未匹配」，
# 这是用 AutoModel 加载 BertForMaskedLM 权重时的正常现象（仅用编码器部分），无需告警。
from transformers import logging as tf_logging
tf_logging.set_verbosity_error()


# ---------------------------------------------------------------------------
# 1. 固定随机种子，保证结果可复现
# ---------------------------------------------------------------------------
def set_seed(seed: int) -> None:
    """固定 Python / NumPy / PyTorch 的随机种子。"""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


# ---------------------------------------------------------------------------
# 2. 评估函数：计算多标签分类的各项指标
# ---------------------------------------------------------------------------
def evaluate(model: nn.Module, dataloader, device, loss_fn, threshold: float = 0.5) -> dict:
    """
    在给定 DataLoader 上评估模型。

    参数：
        model:      待评估模型。
        dataloader: 评估数据。
        device:     计算设备。
        loss_fn:    损失函数（与训练时一致，便于对比损失值）。
        threshold:  判定阈值，logits > threshold 视为命中。

    返回：
        指标字典：{loss, exact_acc, macro_f1, micro_f1, hamming_loss, ...}
    """
    model.eval()
    total_loss = 0.0
    all_logits = []
    all_labels = []

    with torch.no_grad():
        for batch in dataloader:
            # 数据搬到设备上
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            token_type_ids = batch["token_type_ids"].to(device)
            labels = batch["labels"].to(device)

            logits = model(input_ids, attention_mask, token_type_ids)
            loss = loss_fn(logits, labels)
            total_loss += loss.item() * input_ids.size(0)

            all_logits.append(logits.cpu().numpy())
            all_labels.append(labels.cpu().numpy())

    # 汇总成二维数组
    logits_all = np.concatenate(all_logits, axis=0)
    labels_all = np.concatenate(all_labels, axis=0)

    # logits -> 0/1 预测
    preds_all = (torch.sigmoid(torch.tensor(logits_all)).numpy() >= threshold).astype(int)

    # 各项指标
    metrics = {
        "loss": total_loss / len(dataloader.dataset),
        # 精确完全一致（exact match）准确率
        "exact_acc": accuracy_score(labels_all, preds_all),
        # 宏平均 F1：每个标签算一次再平均
        "macro_f1": f1_score(labels_all, preds_all, average="macro", zero_division=0),
        # 微平均 F1：所有样本所有标签一起算
        "micro_f1": f1_score(labels_all, preds_all, average="micro", zero_division=0),
        # 汉明距离损失（越小越好）
        "hamming_loss": hamming_loss(labels_all, preds_all),
        "precision_macro": precision_score(labels_all, preds_all, average="macro", zero_division=0),
        "recall_macro": recall_score(labels_all, preds_all, average="macro", zero_division=0),
    }
    return metrics


# ---------------------------------------------------------------------------
# 3. 模型保存 / 加载辅助
# ---------------------------------------------------------------------------
def save_checkpoint(model, epoch, tags, tag_to_idx, threshold, save_path: str) -> None:
    """
    保存模型检查点（完整模型权重 + 标签信息），方便后续直接加载推理。

    设计说明：
        必须保存完整的模型状态字典（含微调后的 BERT 骨干 + 分类头）。
        分类头是在「微调后的 BERT」特征上训练的，若只保存分类头，
        加载到未微调的 BERT 上特征不匹配，推理会失效。
        因此检查点约为模型大小（~400MB），但不包含优化器状态。

    参数：
        model:      待保存的模型。
        epoch:      当前轮次。
        tags:       标签名列表。
        tag_to_idx: 标签名 -> 下标映射。
        threshold:  判定阈值。
        save_path:  保存路径。
    """
    torch.save({
        "model_state_dict": model.state_dict(),
        "epoch": epoch,
        "tags": tags,
        "tag_to_idx": tag_to_idx,
        "threshold": threshold,
        "num_labels": len(tags),
        "bert_model_dir": Config["model_name_or_path"],
    }, save_path)
    print(f"[保存模型] 已保存到：{save_path}")


# ---------------------------------------------------------------------------
# 4. 主训练流程
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="BERT 商品评论情感多标签分类——训练")
    # 允许通过命令行覆盖 Config 中的部分关键参数
    parser.add_argument("--epochs", type=int, default=None, help="训练轮数（覆盖配置）")
    parser.add_argument("--batch_size", type=int, default=None, help="批大小（覆盖配置）")
    parser.add_argument("--lr", type=float, default=None, help="学习率（覆盖配置）")
    parser.add_argument("--device", type=str, default=None, help="设备：cuda / cpu（默认自动选择）")
    args = parser.parse_args()

    # ---- 用命令行参数覆盖默认配置 ----
    if args.epochs is not None:
        Config["epochs"] = args.epochs
    if args.batch_size is not None:
        Config["batch_size"] = args.batch_size
    if args.lr is not None:
        Config["lr"] = args.lr

    # ---- 固定随机种子 ----
    set_seed(Config["seed"])

    # ---- 自动选择设备：优先 GPU，无 GPU 自动回退 CPU ----
    device = torch.device(get_device(args.device))
    print(f"[设备] 使用 {device} 进行训练"
          + ("（GPU 加速）" if device.type == "cuda" else "（当前无 GPU，使用 CPU）"))

    # ---- 创建保存目录 ----
    save_dir = Config["save_dir"]
    result_dir = Config["result_dir"]
    os.makedirs(save_dir, exist_ok=True)
    os.makedirs(result_dir, exist_ok=True)

    # ---- 加载标签词表并构建索引 ----
    tags = load_tag_vocab(Config["vocab_file"], Config["vocab_file_alt"])
    tag_to_idx, idx_to_tag = build_label_index(tags)
    num_labels = len(tags)
    Config["num_labels"] = num_labels
    print(f"[标签] 共 {num_labels} 个标签：{tags}")

    # ---- 加载训练 / 验证 / 测试数据 ----
    train_samples = load_labeled_data(Config["train_file"])
    val_samples = load_labeled_data(Config["val_file"])
    test_samples = load_labeled_data(Config["test_file"])
    print(f"[数据] 训练集 {len(train_samples)} 条 | 验证集 {len(val_samples)} 条 | 测试集 {len(test_samples)} 条")

    # ---- 加载分词器 ----
    tokenizer = AutoTokenizer.from_pretrained(Config["model_name_or_path"], local_files_only=True)

    # ---- 构建数据集与 DataLoader ----
    train_texts = [s[0] for s in train_samples]
    train_tag_lists = [s[1] for s in train_samples]
    val_texts = [s[0] for s in val_samples]
    val_tag_lists = [s[1] for s in val_samples]
    test_texts = [s[0] for s in test_samples]
    test_tag_lists = [s[1] for s in test_samples]

    train_dataset = MultiLabelDataset(
        train_texts, train_tag_lists, tokenizer, tag_to_idx,
        Config["max_len"], num_labels,
    )
    val_dataset = MultiLabelDataset(
        val_texts, val_tag_lists, tokenizer, tag_to_idx,
        Config["max_len"], num_labels,
    )
    test_dataset = MultiLabelDataset(
        test_texts, test_tag_lists, tokenizer, tag_to_idx,
        Config["max_len"], num_labels,
    )

    train_loader = DataLoader(
        train_dataset, batch_size=Config["batch_size"], shuffle=True,
        num_workers=Config["num_workers"], collate_fn=collate_batch,
    )
    val_loader = DataLoader(
        val_dataset, batch_size=Config["batch_size"], shuffle=False,
        num_workers=Config["num_workers"], collate_fn=collate_batch,
    )
    test_loader = DataLoader(
        test_dataset, batch_size=Config["batch_size"], shuffle=False,
        num_workers=Config["num_workers"], collate_fn=collate_batch,
    )

    # ---- 构建模型并搬到设备 ----
    model = BertMultiLabelModel(Config["model_name_or_path"], num_labels, Config["dropout"])
    model.to(device)

    # ---- 优化器：仅对需要梯度的参数做 AdamW ----
    optimizer = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad],
        lr=Config["lr"],
        weight_decay=Config["weight_decay"],
    )

    # ---- 学习率预热 + 线性衰减 ----
    total_steps = len(train_loader) * Config["epochs"]
    warmup_steps = int(total_steps * Config["warmup_ratio"])
    scheduler = get_linear_schedule_with_warmup(
        optimizer, num_warmup_steps=warmup_steps, num_training_steps=total_steps,
    )

    # ---- 损失函数：多标签二分类交叉熵（带正负样本平衡） ----
    # 每个标签的正样本很少（28 个标签，一条评论通常只命中 1~3 个），
    # 若不处理，负样本梯度会淹没正样本信号，导致模型退化成「什么都不预测」。
    # 因此根据训练集各标签的正负出现次数，计算 pos_weight 放大正样本梯度。
    pos_counts = torch.zeros(num_labels)
    for tag_list in train_tag_lists:
        for tag in tag_list:
            if tag in tag_to_idx:
                pos_counts[tag_to_idx[tag]] += 1
    neg_counts = len(train_tag_lists) - pos_counts
    # pos_weight = 负样本数 / 正样本数；裁剪到 [1, pos_weight_clamp] 防止个别稀疏标签过激
    pw_clamp = Config["pos_weight_clamp"]
    pos_weight = (neg_counts / pos_counts.clamp(min=1)).clamp(1.0, pw_clamp)
    loss_fn = torch.nn.BCEWithLogitsLoss(pos_weight=pos_weight.to(device))
    print(f"[损失函数] 使用带 pos_weight 的 BCE（正负样本比中位数约 {pos_weight.median():.1f}:1）")

    # ---- 训练过程记录 ----
    log_rows = []
    best_macro_f1 = -1.0
    best_epoch = -1

    print(f"\n[开始训练] 共 {Config['epochs']} 轮，批大小 {Config['batch_size']}，学习率 {Config['lr']}")
    for epoch in range(1, Config["epochs"] + 1):
        model.train()
        total_train_loss = 0.0

        # 一个 epoch 的训练循环
        progress = tqdm(train_loader, desc=f"Epoch {epoch}/{Config['epochs']}", leave=False)
        for step, batch in enumerate(progress):
            # 数据搬到设备
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            token_type_ids = batch["token_type_ids"].to(device)
            labels = batch["labels"].to(device)

            # 前向 + 损失 + 反向 + 更新
            optimizer.zero_grad()
            logits = model(input_ids, attention_mask, token_type_ids)
            loss = loss_fn(logits, labels)
            loss.backward()
            optimizer.step()
            scheduler.step()

            total_train_loss += loss.item()
            progress.set_postfix({"loss": f"{loss.item():.4f}"})

        # 当前轮平均训练损失
        avg_train_loss = total_train_loss / len(train_loader)

        # 验证集评估（传入与训练一致的损失函数，保证损失值可比）
        val_metrics = evaluate(model, val_loader, device, loss_fn, Config["threshold"])

        # 记录本轮信息
        log_rows.append({
            "epoch": epoch,
            "train_loss": round(avg_train_loss, 4),
            "val_loss": round(val_metrics["loss"], 4),
            "val_exact_acc": round(val_metrics["exact_acc"], 4),
            "val_macro_f1": round(val_metrics["macro_f1"], 4),
            "val_micro_f1": round(val_metrics["micro_f1"], 4),
        })
        print(
            f"\n[Epoch {epoch}] 训练损失 {avg_train_loss:.4f} | "
            f"验证损失 {val_metrics['loss']:.4f} | "
            f"验证 Macro-F1 {val_metrics['macro_f1']:.4f} | "
            f"验证 Exact-ACC {val_metrics['exact_acc']:.4f}"
        )

        # 保存验证集最优模型（按 Macro-F1）
        if val_metrics["macro_f1"] > best_macro_f1:
            best_macro_f1 = val_metrics["macro_f1"]
            best_epoch = epoch
            save_checkpoint(
                model, epoch, tags, tag_to_idx,
                Config["threshold"], Config["best_model_path"],
            )
            print(f"  -> 新最优模型（验证 Macro-F1 = {best_macro_f1:.4f}）")

    # ---- 训练结束：保存最终模型 ----
    save_checkpoint(
        model, Config["epochs"], tags, tag_to_idx,
        Config["threshold"], Config["final_model_path"],
    )

    # ---- 训练日志写入 CSV ----
    log_path = Config["log_file"]
    with open(log_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(log_rows[0].keys()))
        writer.writeheader()
        writer.writerows(log_rows)
    print(f"[日志] 训练过程已写入：{log_path}")

    # ---- 测试集评估：用验证集最优模型 ----
    print("\n[测试评估] 加载验证集最优模型 ...")
    checkpoint = torch.load(Config["best_model_path"], map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"])
    test_metrics = evaluate(model, test_loader, device, loss_fn, Config["threshold"])
    print(
        f"\n[测试集指标] Loss {test_metrics['loss']:.4f} | "
        f"Exact-ACC {test_metrics['exact_acc']:.4f} | "
        f"Macro-F1 {test_metrics['macro_f1']:.4f} | "
        f"Micro-F1 {test_metrics['micro_f1']:.4f} | "
        f"Hamming-Loss {test_metrics['hamming_loss']:.4f}"
    )

    # ---- 测试指标写入 JSON ----
    test_metrics_save = {
        "best_epoch": best_epoch,
        "best_val_macro_f1": best_macro_f1,
        **{k: round(v, 4) for k, v in test_metrics.items()},
    }
    with open(Config["metrics_file"], "w", encoding="utf-8") as f:
        json.dump(test_metrics_save, f, ensure_ascii=False, indent=2)
    print(f"[指标] 测试集指标已写入：{Config['metrics_file']}")

    # ---- 备份标签列表（推理时需要） ----
    with open(Config["tags_file"], "w", encoding="utf-8") as f:
        f.write("\n".join(tags))
    print(f"[标签] 标签列表已写入：{Config['tags_file']}")

    # ---- 展示几条测试集预测样例 ----
    print("\n[预测样例]")
    show_examples(model, tokenizer, test_samples[:5], tag_to_idx, device)

    print("\n[训练完成] 最佳验证 Macro-F1 = {:.4f}（第 {} 轮）".format(best_macro_f1, best_epoch))


# ---------------------------------------------------------------------------
# 5. 样例展示辅助
# ---------------------------------------------------------------------------
def show_examples(model, tokenizer, samples, tag_to_idx, device, threshold=0.5):
    """
    打印若干条测试样本的真实标签与模型预测，方便直观检查效果。
    """
    model.eval()
    tags = list(tag_to_idx.keys())
    with torch.no_grad():
        for text, gold_tags in samples:
            # 单条文本编码
            enc = tokenizer(
                text, max_length=Config["max_len"],
                truncation=True, padding="max_length", return_tensors="pt",
            )
            input_ids = enc["input_ids"].to(device)
            attention_mask = enc["attention_mask"].to(device)
            token_type_ids = enc.get("token_type_ids", torch.zeros_like(input_ids)).to(device)

            logits = model(input_ids, attention_mask, token_type_ids)
            probs = torch.sigmoid(logits).squeeze(0).cpu().numpy()
            # 命中概率 > 阈值的标签
            pred_tags = [tags[i] for i, p in enumerate(probs) if p >= threshold]

            print(f"  文本：{text}")
            print(f"    真实标签：{gold_tags}")
            print(f"    预测标签：{pred_tags}")
            print()


# ---------------------------------------------------------------------------
# 6. 程序入口
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    main()
