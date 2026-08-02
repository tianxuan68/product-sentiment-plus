# -*- coding: utf-8 -*-
"""
train.py —— 属性级情感分类训练主程序

任务：
    输入「商品类别 + 评论文本」，输出 8 种属性（质量/做工/价格/物流/服务/包装/描述/外观）
    各自的情感：好(正面) / 坏(负面) / 未提及。
    建模为 16 维多标签分类（8 属性 × 2 极性），BCEWithLogitsLoss 训练。

运行方式：
    python scripts/train.py                # 使用 Config 默认配置
    python scripts/train.py --epochs 20    # 覆盖训练轮数
    python scripts/train.py --device cpu   # 强制 CPU

流程：
    1. 自动选择 GPU / CPU
    2. 加载已拆分的 训练/验证/测试 数据（若未拆分先提示运行 data_utils.py）
    3. 构建多标签数据集与 DataLoader
    4. 构建 BERT 属性级情感模型
    5. 训练若干轮：每轮打印训练/验证指标，并保存验证集最优模型
    6. 在验证集上为每个属性调优「好/坏判定阈值」
    7. 用调优后的阈值在测试集上评估，输出各项指标
    8. 保存最佳/最终模型、训练日志、指标 JSON
"""

import os
import sys
import json
import csv
import time
import random
import argparse
import logging

# 把本脚本所在目录加入 sys.path，保证直接运行时也能互相 import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from tqdm import tqdm
from transformers import AutoTokenizer, get_linear_schedule_with_warmup
from sklearn.metrics import (
    f1_score, precision_score, recall_score, accuracy_score, hamming_loss,
)

from config import Config, get_device, PROJECT_ROOT, LABEL_NAMES, label_index
from data_utils import load_processed_data
from dataset import AspectDataset, collate_batch
from model import BertAspectModel

# 降低 transformers 日志噪音（本地权重「MLM 头权重未匹配」告警属正常现象）
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
# 2. 日志：同时输出到控制台与 results/train_run.log
# ---------------------------------------------------------------------------
def setup_logger(log_path: str) -> logging.Logger:
    """
    创建同时写控制台和文件的 logger。

    参数：
        log_path: 日志文件路径（results/train_run.log）。

    返回：
        logger 对象。
    """
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    logger = logging.getLogger("bert_aspect_train")
    logger.setLevel(logging.INFO)
    # 清空已有 handler，避免重复打印
    logger.handlers.clear()

    fmt = logging.Formatter("%(asctime)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    # 控制台输出
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    logger.addHandler(console)

    # 文件输出（UTF-8）
    file_h = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    file_h.setFormatter(fmt)
    logger.addHandler(file_h)

    return logger


# ---------------------------------------------------------------------------
# 3. 预测解码：logits/probs -> 每个属性的极性（好/坏/未提及）
# ---------------------------------------------------------------------------
def predict_probs(model: nn.Module, dataloader, device) -> np.ndarray:
    """
    对 DataLoader 内全部样本做一次前向，返回 sigmoid 概率矩阵。

    参数：
        model:     模型。
        dataloader: 评估数据。
        device:    计算设备。

    返回：
        shape = (N, 16) 的概率矩阵。
    """
    model.eval()
    all_probs = []
    with torch.no_grad():
        for batch in dataloader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            token_type_ids = batch["token_type_ids"].to(device)
            logits = model(input_ids, attention_mask, token_type_ids)
            probs = torch.sigmoid(logits).cpu().numpy()
            all_probs.append(probs)
    return np.concatenate(all_probs, axis=0)


def decode_polarities(probs: np.ndarray, thresholds: dict, aspects: list) -> np.ndarray:
    """
    把概率矩阵解码为每个属性的极性矩阵。

    规则（每个属性独立判定）：
        p_pos = probs[:, a]       （该属性「好」的概率）
        p_neg = probs[:, 8+a]     （该属性「坏」的概率）
        - 若 p_pos >= 阈值[a].pos 且 p_pos >= p_neg  ->  好(1)
        - 若 p_neg >= 阈值[a].neg 且 p_neg >  p_pos  ->  坏(0)
        - 否则                                        ->  未提及(-1)

    参数：
        probs:     shape = (N, 16) 概率矩阵。
        thresholds: {属性名: {"pos": 阈值, "neg": 阈值}}。
        aspects:   8 个属性名列表。

    返回：
        shape = (N, 8) 的整数矩阵，取值 1/0/-1。
    """
    n = len(aspects)
    polarities = np.full((probs.shape[0], n), -1, dtype=int)
    for a_idx, aspect in enumerate(aspects):
        p_pos = probs[:, a_idx]
        p_neg = probs[:, n + a_idx]
        t_pos = thresholds[aspect]["pos"]
        t_neg = thresholds[aspect]["neg"]
        # 「好」优先判定；均未过阈值则为未提及
        is_pos = (p_pos >= t_pos) & (p_pos >= p_neg)
        is_neg = (p_neg >= t_neg) & (p_neg > p_pos)
        polarities[is_pos, a_idx] = 1
        polarities[is_neg, a_idx] = 0
    return polarities


def decode_labels(probs: np.ndarray, thresholds: dict, aspects: list) -> np.ndarray:
    """
    把概率矩阵解码为 16 维 0/1 标签矩阵（用于标准多标签 P/R/F1 评估）。

    参数：
        同 decode_polarities。

    返回：
        shape = (N, 16) 的 0/1 矩阵。
    """
    polarities = decode_polarities(probs, thresholds, aspects)
    n = len(aspects)
    labels = np.zeros((probs.shape[0], 2 * n), dtype=int)
    for a_idx in range(n):
        labels[:, a_idx] = (polarities[:, a_idx] == 1).astype(int)
        labels[:, n + a_idx] = (polarities[:, a_idx] == 0).astype(int)
    return labels


def true_polarity_matrix(true_label_vec: list, aspects: list) -> np.ndarray:
    """
    把 16 维 0/1 标签向量转成真实极性矩阵（好=1 / 坏=0 / 未提及=-1）。

    参数：
        true_label_vec: 列表的列表，每项 16 维 0/1。
        aspects:        8 个属性名列表。

    返回：
        shape = (N, 8) 的整数矩阵。
    """
    arr = np.array(true_label_vec, dtype=int)
    n = len(aspects)
    pos_part = arr[:, :n]
    neg_part = arr[:, n:]
    polarities = np.full_like(pos_part, -1)
    polarities[pos_part == 1] = 1
    polarities[neg_part == 1] = 0
    return polarities


# ---------------------------------------------------------------------------
# 4. 指标计算
# ---------------------------------------------------------------------------
def compute_metrics(
    probs: np.ndarray, true_label_vec: list, thresholds: dict, aspects: list
) -> dict:
    """
    综合评估：返回准确率、提及准确率、16 标签 P/R/F1 等指标。

    指标说明：
        - aspect_acc     整体属性准确率：所有「评论×8属性」单元中预测正确的比例（含未提及）
        - mentioned_acc  提及属性准确率：仅真实被提及的属性中预测正确的比例
        - macro_f1_3     每个属性按 好/坏/未提及 三类算宏平均 F1，再对 8 个属性平均
        - micro_pre/rec/f1 / macro_pre/rec/f1：16 维多标签的标准 P/R/F1

    参数：
        probs:        shape = (N, 16) 概率矩阵。
        true_label_vec: 列表的列表，16 维 0/1 真实标签。
        thresholds:   {属性名: {"pos": t, "neg": t}}。
        aspects:      8 个属性名列表。

    返回：
        指标字典。
    """
    n = len(aspects)
    true_pol = true_polarity_matrix(true_label_vec, aspects)          # (N, 8)
    pred_pol = decode_polarities(probs, thresholds, aspects)           # (N, 8)
    pred_labels = decode_labels(probs, thresholds, aspects)            # (N, 16)
    true_labels = np.array(true_label_vec, dtype=int)                  # (N, 16)

    # 整体属性准确率（含未提及）
    aspect_acc = float((pred_pol == true_pol).mean())

    # 提及属性准确率（仅真实提及的属性）
    mentioned_mask = true_pol != -1
    if mentioned_mask.any():
        mentioned_acc = float((pred_pol[mentioned_mask] == true_pol[mentioned_mask]).mean())
    else:
        mentioned_acc = 0.0

    # 每个属性 好/坏/未提及 三类宏平均 F1（映射 -1/0/1 -> 0/1/2）
    class_f1s = []
    for a_idx in range(n):
        true_cls = true_pol[:, a_idx] + 1
        pred_cls = pred_pol[:, a_idx] + 1
        f = f1_score(true_cls, pred_cls, average="macro",
                     labels=[0, 1, 2], zero_division=0)
        class_f1s.append(f)
    macro_f1_3 = float(np.mean(class_f1s))

    # 16 维多标签标准指标
    micro_pre = float(precision_score(true_labels, pred_labels, average="micro", zero_division=0))
    micro_rec = float(recall_score(true_labels, pred_labels, average="micro", zero_division=0))
    micro_f1 = float(f1_score(true_labels, pred_labels, average="micro", zero_division=0))
    macro_pre = float(precision_score(true_labels, pred_labels, average="macro", zero_division=0))
    macro_rec = float(recall_score(true_labels, pred_labels, average="macro", zero_division=0))
    macro_f1 = float(f1_score(true_labels, pred_labels, average="macro", zero_division=0))

    return {
        "aspect_acc": aspect_acc,
        "mentioned_acc": mentioned_acc,
        "macro_f1_3": macro_f1_3,
        "micro_pre": micro_pre,
        "micro_rec": micro_rec,
        "micro_f1": micro_f1,
        "macro_pre": macro_pre,
        "macro_rec": macro_rec,
        "macro_f1": macro_f1,
        "hamming_loss": float(hamming_loss(true_labels, pred_labels)),
    }


# ---------------------------------------------------------------------------
# 5. 阈值调优：在验证集上为每个属性搜索「好/坏」判定阈值
# ---------------------------------------------------------------------------
def tune_thresholds(
    val_probs: np.ndarray, true_label_vec: list, aspects: list, grid: list
) -> dict:
    """
    为每个属性独立搜索 (pos 阈值, neg 阈值)，使该属性 好/坏/未提及 三类宏平均 F1 最大。

    参数：
        val_probs:     shape = (N, 16) 验证集概率。
        true_label_vec: 验证集 16 维 0/1 真实标签。
        aspects:       8 个属性名列表。
        grid:          候选阈值列表，如 [0.3, 0.4, ..., 0.8]。

    返回：
        {属性名: {"pos": 阈值, "neg": 阈值}, ...}
    """
    n = len(aspects)
    true_pol = true_polarity_matrix(true_label_vec, aspects)  # (N, 8)
    thresholds = {}

    for a_idx, aspect in enumerate(aspects):
        true_cls = true_pol[:, a_idx] + 1  # -1/0/1 -> 0/1/2
        p_pos = val_probs[:, a_idx]
        p_neg = val_probs[:, n + a_idx]

        best_score = -1.0
        best_pair = (Config["default_threshold"], Config["default_threshold"])
        for t_pos in grid:
            for t_neg in grid:
                # 用当前 (t_pos, t_neg) 解码该属性极性
                pred_cls = np.full(len(true_cls), 0, dtype=int)
                is_pos = (p_pos >= t_pos) & (p_pos >= p_neg)
                is_neg = (p_neg >= t_neg) & (p_neg > p_pos)
                pred_cls[is_pos] = 2
                pred_cls[is_neg] = 1
                score = f1_score(true_cls, pred_cls, average="macro",
                                 labels=[0, 1, 2], zero_division=0)
                if score > best_score:
                    best_score = score
                    best_pair = (t_pos, t_neg)

        thresholds[aspect] = {"pos": best_pair[0], "neg": best_pair[1]}
    return thresholds


# ---------------------------------------------------------------------------
# 6. 模型保存 / 加载辅助
# ---------------------------------------------------------------------------
def save_checkpoint(model, epoch, thresholds, aspects, categories, label_names,
                    save_path: str, best_metrics: dict = None) -> None:
    """
    保存模型检查点（完整模型权重 + 标签信息 + 阈值），方便后续直接加载推理。

    设计说明：
        必须保存完整的模型状态字典（含微调后的 BERT 骨干 + 分类头）。
        分类头是在「微调后的 BERT」特征上训练的，若只保存分类头，
        加载到未微调的 BERT 上特征不匹配，推理会失效。

    参数：
        model:        待保存的模型。
        epoch:        当前轮次。
        thresholds:   每个属性的判定阈值。
        aspects:      8 个属性名。
        categories:   15 个类别名。
        label_names:  16 个标签名。
        save_path:    保存路径。
        best_metrics: 触发保存时的验证指标（便于追溯）。
    """
    torch.save({
        "model_state_dict": model.state_dict(),
        "epoch": epoch,
        "aspects": aspects,
        "categories": categories,
        "label_names": label_names,
        "num_labels": len(label_names),
        "thresholds": thresholds,
        "best_metrics": best_metrics or {},
        "bert_model_dir": Config["model_name_or_path"],
        "max_len": Config["max_len"],
    }, save_path)
    print(f"[保存模型] 已保存到：{save_path}")


# ---------------------------------------------------------------------------
# 7. 主训练流程
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="BERT 属性级情感分类——训练")
    parser.add_argument("--epochs", type=int, default=None, help="训练轮数（覆盖配置）")
    parser.add_argument("--batch_size", type=int, default=None, help="批大小（覆盖配置）")
    parser.add_argument("--lr", type=float, default=None, help="学习率（覆盖配置）")
    parser.add_argument("--device", type=str, default=None, help="设备：cuda / cpu（默认自动选择）")
    parser.add_argument("--subset", type=int, default=None,
                        help="仅用前 N 条训练样本快速冒烟测试（正式训练不传）")
    args = parser.parse_args()

    if args.epochs is not None:
        Config["epochs"] = args.epochs
    if args.batch_size is not None:
        Config["batch_size"] = args.batch_size
    if args.lr is not None:
        Config["lr"] = args.lr

    set_seed(Config["seed"])

    # 让 PyTorch 充分利用本机全部 CPU 核（Windows 默认可能只启用一半线程，影响训练速度）
    torch.set_num_threads(os.cpu_count() or 4)

    device = torch.device(get_device(args.device))
    logger = setup_logger(Config["train_run_log"])

    logger.info("=" * 70)
    logger.info("BERT 属性级情感分类——开始训练")
    logger.info("=" * 70)
    logger.info(f"[设备] 使用 {device} 训练"
                + ("（GPU 加速）" if device.type == "cuda" else "（当前无 GPU，使用 CPU）"))
    logger.info(f"[属性] {Config['aspects']}")
    logger.info(f"[标签] 共 {len(LABEL_NAMES)} 个：{LABEL_NAMES}")
    logger.info(f"[超参] epochs={Config['epochs']} batch_size={Config['batch_size']} "
                f"lr={Config['lr']} max_len={Config['max_len']} "
                f"pos_weight_clamp={Config['pos_weight_clamp']}")

    # ---- 创建保存目录 ----
    os.makedirs(Config["save_dir"], exist_ok=True)
    os.makedirs(Config["result_dir"], exist_ok=True)

    # ---- 加载数据 ----
    for split in ["train", "val", "test"]:
        f = Config[f"{split}_file"]
        if not os.path.exists(f):
            raise FileNotFoundError(
                f"[数据文件缺失] 找不到 {split} 集文件：{f}\n"
                f"请先运行 python scripts/data_utils.py 生成训练/验证/测试拆分文件。"
            )

    train_cat, train_text, train_label, _ = load_processed_data(Config["train_file"], Config["aspects"])
    val_cat, val_text, val_label, _ = load_processed_data(Config["val_file"], Config["aspects"])
    test_cat, test_text, test_label, test_attr = load_processed_data(Config["test_file"], Config["aspects"])

    # 冒烟测试：仅用前 N 条样本快速验证流程
    if args.subset:
        train_text, train_label = train_text[:args.subset], train_label[:args.subset]
        train_cat = train_cat[:args.subset]
        val_text, val_label = val_text[:args.subset], val_label[:args.subset]
        val_cat = val_cat[:args.subset]
        logger.info(f"[冒烟测试] 已限制样本数（前 {args.subset} 条）")

    logger.info(f"[数据] 训练集 {len(train_text)} 条 | 验证集 {len(val_text)} 条 | 测试集 {len(test_text)} 条")

    # ---- 加载分词器 ----
    tokenizer = AutoTokenizer.from_pretrained(Config["model_name_or_path"], local_files_only=True)

    # ---- 构建数据集与 DataLoader ----
    num_labels = 2 * len(Config["aspects"])
    Config["num_labels"] = num_labels

    train_dataset = AspectDataset(train_cat, train_text, train_label, tokenizer,
                                  Config["max_len"], num_labels)
    val_dataset = AspectDataset(val_cat, val_text, val_label, tokenizer,
                                Config["max_len"], num_labels)
    test_dataset = AspectDataset(test_cat, test_text, test_label, tokenizer,
                                 Config["max_len"], num_labels)

    train_loader = DataLoader(train_dataset, batch_size=Config["batch_size"], shuffle=True,
                              num_workers=Config["num_workers"], collate_fn=collate_batch)
    val_loader = DataLoader(val_dataset, batch_size=Config["batch_size"], shuffle=False,
                            num_workers=Config["num_workers"], collate_fn=collate_batch)
    test_loader = DataLoader(test_dataset, batch_size=Config["batch_size"], shuffle=False,
                             num_workers=Config["num_workers"], collate_fn=collate_batch)

    # ---- 构建模型 ----
    model = BertAspectModel(Config["model_name_or_path"], num_labels, Config["dropout"])
    model.to(device)
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    logger.info(f"[模型] 参数量：{total_params / 1e6:.1f}M（可训练 {trainable_params / 1e6:.1f}M）")

    # ---- 优化器 / 调度器 ----
    optimizer = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad],
        lr=Config["lr"], weight_decay=Config["weight_decay"],
    )
    total_steps = len(train_loader) * Config["epochs"]
    warmup_steps = int(total_steps * Config["warmup_ratio"])
    scheduler = get_linear_schedule_with_warmup(
        optimizer, num_warmup_steps=warmup_steps, num_training_steps=total_steps,
    )

    # ---- 损失函数：带 pos_weight 的 BCE（缓解 16 个标签的正样本稀疏问题） ----
    label_arr = np.array(train_label, dtype=int)
    pos_counts = label_arr.sum(axis=0).astype(np.float64)          # (16,)
    neg_counts = len(train_label) - pos_counts
    pw_clamp = Config["pos_weight_clamp"]
    pos_weight = (neg_counts / np.clip(pos_counts, 1, None)).clip(1.0, pw_clamp)
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(pos_weight, dtype=torch.float).to(device))
    logger.info(f"[损失函数] BCE + pos_weight（16 个标签的 pos_weight 见下）")
    for i, name in enumerate(LABEL_NAMES):
        logger.info(f"    {name:6s}: 正样本 {int(pos_counts[i]):5d} 条, pos_weight={pos_weight[i]:.2f}")

    # ---- 训练过程记录 ----
    log_rows = []
    best_score = -1.0
    best_epoch = -1
    no_improve = 0

    logger.info(f"\n[开始训练] 共 {Config['epochs']} 轮，批大小 {Config['batch_size']}，学习率 {Config['lr']}")
    for epoch in range(1, Config["epochs"] + 1):
        model.train()
        total_train_loss = 0.0
        t0 = time.time()

        progress = tqdm(train_loader, desc=f"Epoch {epoch}/{Config['epochs']}", leave=False)
        for step, batch in enumerate(progress):
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            token_type_ids = batch["token_type_ids"].to(device)
            labels = batch["labels"].to(device)

            optimizer.zero_grad()
            logits = model(input_ids, attention_mask, token_type_ids)
            loss = loss_fn(logits, labels)
            loss.backward()
            optimizer.step()
            scheduler.step()

            total_train_loss += loss.item()
            progress.set_postfix({"loss": f"{loss.item():.4f}"})

        avg_train_loss = total_train_loss / len(train_loader)
        epoch_time = time.time() - t0
        lr_now = scheduler.get_last_lr()[0]

        # 验证集评估（用默认阈值粗评，用于选轮次）
        val_probs = predict_probs(model, val_loader, device)
        default_thresholds = {
            a: {"pos": Config["default_threshold"], "neg": Config["default_threshold"]}
            for a in Config["aspects"]
        }
        val_metrics = compute_metrics(val_probs, val_label, default_thresholds, Config["aspects"])

        log_rows.append({
            "epoch": epoch,
            "train_loss": round(avg_train_loss, 4),
            "val_aspect_acc": round(val_metrics["aspect_acc"], 4),
            "val_mentioned_acc": round(val_metrics["mentioned_acc"], 4),
            "val_macro_f1_3": round(val_metrics["macro_f1_3"], 4),
            "val_micro_f1": round(val_metrics["micro_f1"], 4),
            "lr": round(lr_now, 8),
        })
        logger.info(
            f"[Epoch {epoch}] 训练损失 {avg_train_loss:.4f} | 耗时 {epoch_time:.0f}s | lr {lr_now:.2e} | "
            f"验证 整体ACC {val_metrics['aspect_acc']:.4f} / 提及ACC {val_metrics['mentioned_acc']:.4f} / "
            f"三类宏F1 {val_metrics['macro_f1_3']:.4f}"
        )

        # 用「三类宏平均 F1」作为选优指标（兼顾提及检测与未提及）
        if val_metrics["macro_f1_3"] > best_score:
            best_score = val_metrics["macro_f1_3"]
            best_epoch = epoch
            no_improve = 0
            save_checkpoint(model, epoch, default_thresholds, Config["aspects"],
                            Config["categories"], LABEL_NAMES, Config["best_model_path"],
                            best_metrics=val_metrics)
            logger.info(f"  -> 新最优模型（验证三类宏F1 = {best_score:.4f}）")
        else:
            no_improve += 1
            logger.info(f"  -> 验证指标未提升（已连续 {no_improve} 轮）")

        if no_improve >= Config["early_stop_patience"]:
            logger.info(f"[早停] 连续 {no_improve} 轮未提升，提前结束训练")
            break

    # ---- 训练结束：加载最优模型，在验证集上调优每个属性的阈值 ----
    logger.info(f"\n[阈值调优] 加载验证集最优模型（第 {best_epoch} 轮），在验证集上为每个属性搜索最优判定阈值 ...")
    checkpoint = torch.load(Config["best_model_path"], map_location=device)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device)

    val_probs = predict_probs(model, val_loader, device)
    thresholds = tune_thresholds(val_probs, val_label, Config["aspects"], Config["threshold_grid"])
    for a in Config["aspects"]:
        logger.info(f"    属性 {a}: 好阈值={thresholds[a]['pos']:.2f}，坏阈值={thresholds[a]['neg']:.2f}")

    # ---- 用调优后的阈值重评验证集 ----
    val_metrics_tuned = compute_metrics(val_probs, val_label, thresholds, Config["aspects"])
    logger.info(f"[验证集·调优阈值] 整体ACC {val_metrics_tuned['aspect_acc']:.4f} | "
                f"提及ACC {val_metrics_tuned['mentioned_acc']:.4f} | 三类宏F1 {val_metrics_tuned['macro_f1_3']:.4f} | "
                f"宏F1(16标签) {val_metrics_tuned['macro_f1']:.4f}")

    # ---- 重新保存最佳模型（含调优后的阈值） ----
    save_checkpoint(model, best_epoch, thresholds, Config["aspects"],
                    Config["categories"], LABEL_NAMES, Config["best_model_path"],
                    best_metrics=val_metrics_tuned)

    # ---- 测试集评估 ----
    logger.info("\n[测试评估] 使用验证集最优模型 + 调优阈值 ...")
    test_probs = predict_probs(model, test_loader, device)
    test_metrics = compute_metrics(test_probs, test_label, thresholds, Config["aspects"])
    logger.info(
        f"[测试集指标]\n"
        f"    整体属性准确率 aspect_acc        : {test_metrics['aspect_acc']:.4f}\n"
        f"    提及属性准确率 mentioned_acc     : {test_metrics['mentioned_acc']:.4f}\n"
        f"    好/坏/未提及 三类宏平均F1        : {test_metrics['macro_f1_3']:.4f}\n"
        f"    16标签 micro 精确率/召回率/F1    : {test_metrics['micro_pre']:.4f} / "
        f"{test_metrics['micro_rec']:.4f} / {test_metrics['micro_f1']:.4f}\n"
        f"    16标签 macro 精确率/召回率/F1    : {test_metrics['macro_pre']:.4f} / "
        f"{test_metrics['macro_rec']:.4f} / {test_metrics['macro_f1']:.4f}\n"
        f"    Hamming Loss                    : {test_metrics['hamming_loss']:.4f}"
    )

    # ---- 写入训练日志 CSV ----
    with open(Config["log_file"], "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(log_rows[0].keys()))
        writer.writeheader()
        writer.writerows(log_rows)
    logger.info(f"[日志] 训练过程已写入：{Config['log_file']}")

    # ---- 写入指标 JSON ----
    test_metrics_save = {
        "best_epoch": best_epoch,
        "best_val_macro_f1_3": best_score,
        "val_tuned": val_metrics_tuned,
        "test": test_metrics,
        "thresholds": thresholds,
    }
    with open(Config["metrics_file"], "w", encoding="utf-8") as f:
        json.dump(test_metrics_save, f, ensure_ascii=False, indent=2)
    logger.info(f"[指标] 测试集指标已写入：{Config['metrics_file']}")

    # ---- 备份标签列表 ----
    with open(Config["labels_file"], "w", encoding="utf-8") as f:
        f.write("\n".join(LABEL_NAMES))
    logger.info(f"[标签] 标签列表已写入：{Config['labels_file']}")

    # ---- 展示测试集预测样例 ----
    logger.info("\n[预测样例]")
    show_examples(model, tokenizer, test_cat, test_text, test_attr,
                  thresholds, device)

    logger.info(f"\n[训练完成] 最佳验证三类宏F1 = {best_score:.4f}（第 {best_epoch} 轮），"
                f"测试整体属性准确率 = {test_metrics['aspect_acc']:.4f}")


# ---------------------------------------------------------------------------
# 8. 样例展示辅助
# ---------------------------------------------------------------------------
def show_examples(model, tokenizer, categories, texts, attrs_lists,
                  thresholds, device, n=5, seed=0):
    """
    打印若干条测试样本的真实属性标注与模型预测，方便直观检查效果。
    """
    model.eval()
    rng = random.Random(seed)
    idxs = rng.sample(range(len(texts)), min(n, len(texts)))

    def fmt_attrs(attrs):
        """把 [(属性, 极性), ...] 转成 '质量:好' 的可读形式。"""
        return "；".join(f"{a}:{'好' if p == 1 else '坏'}" for a, p in attrs)

    for i in idxs:
        category, text, attrs = categories[i], texts[i], attrs_lists[i]
        encoding = tokenizer(text=category, text_pair=text,
                             max_length=Config["max_len"], truncation=True,
                             padding="max_length", return_tensors="pt")
        with torch.no_grad():
            logits = model(encoding["input_ids"].to(device),
                           encoding["attention_mask"].to(device),
                           encoding.get("token_type_ids", torch.zeros_like(encoding["input_ids"])).to(device))
            probs = torch.sigmoid(logits).squeeze(0).cpu().numpy()
        pred_pol = decode_polarities(probs[None, :], thresholds, Config["aspects"])[0]

        parts = []
        for a_idx, a in enumerate(Config["aspects"]):
            p = int(pred_pol[a_idx])
            if p == 1:
                parts.append(f"{a}好")
            elif p == 0:
                parts.append(f"{a}坏")
        pred_text = "，".join(parts) if parts else "（未提及任何属性）"

        print(f"\n  类别：{category}")
        print(f"  评论：{text[:60]}{'...' if len(text) > 60 else ''}")
        print(f"  真实：{fmt_attrs(attrs)}")
        print(f"  预测：{pred_text}")


# ---------------------------------------------------------------------------
# 9. 程序入口
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    main()
