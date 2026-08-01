# -*- coding: utf-8 -*-
"""
predict.py —— BERT 多标签分类推理主程序

功能：
    加载训练好的模型检查点，对一条或多条评论文本预测多标签情感。

运行方式：
    python scripts/predict.py --text "客服推荐的尺码合适，发货也很快"
    python scripts/predict.py --text "衣服质量很差，做工也粗糙"
    python scripts/predict.py --checkpoint checkpoints/best_model.pt --text "..."

    # 批量预测文件（每行一条文本）
    python scripts/predict.py --input_file path/to/texts.txt --output_file path/to/result.csv

输出示例：
    输入文本：客服推荐的尺码合适，发货也很快
    预测标签：尺码合适，发货快
"""

import os
import sys
import csv
import argparse

# 把本脚本所在目录加入 sys.path，保证直接运行时也能互相 import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import torch
from transformers import AutoTokenizer

from config import Config, get_device, PROJECT_ROOT
from model import BertMultiLabelModel

# 降低 transformers 日志噪音：加载本地权重时关于「MLM 头权重未匹配」的告警属正常现象
from transformers import logging as tf_logging
tf_logging.set_verbosity_error()


# ---------------------------------------------------------------------------
# 1. 加载模型与分词器
# ---------------------------------------------------------------------------
def load_model(checkpoint_path: str, device) -> tuple:
    """
    从检查点文件恢复模型、分词器与标签信息。

    参数：
        checkpoint_path: 训练时保存的 .pt 检查点。
        device:          计算设备。

    返回：
        (model, tokenizer, tags)
        model:     已加载权重的多标签模型。
        tokenizer: BERT 分词器。
        tags:      标签名列表（与模型输出维度一一对应）。
    """
    # 检查点文件不存在时给出友好提示
    if not os.path.exists(checkpoint_path):
        raise FileNotFoundError(
            f"[模型文件缺失] 找不到检查点：{checkpoint_path}\n"
            f"请先运行 python scripts/train.py 训练模型并保存权重。"
        )

    # 加载检查点（训练时保存了完整模型权重 + 标签信息）
    checkpoint = torch.load(checkpoint_path, map_location=device)
    tags = checkpoint["tags"]
    num_labels = checkpoint["num_labels"]

    # 用训练时相同的预训练模型目录重建模型结构，再套用训练好的完整权重
    bert_model_dir = checkpoint.get("bert_model_dir", Config["model_name_or_path"])
    model = BertMultiLabelModel(bert_model_dir, num_labels, Config["dropout"])
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device)
    model.eval()

    # 加载分词器
    tokenizer = AutoTokenizer.from_pretrained(bert_model_dir, local_files_only=True)
    return model, tokenizer, tags


# ---------------------------------------------------------------------------
# 2. 单条文本预测
# ---------------------------------------------------------------------------
def predict_one(text: str, model, tokenizer, tags, device, threshold: float) -> list:
    """
    对单条评论文本预测多标签。

    参数：
        text:      评论文本。
        model:     多标签模型。
        tokenizer: 分词器。
        tags:      标签名列表。
        device:    设备。
        threshold: 判定阈值。

    返回：
        命中标签名列表，例如 ["尺码合适", "发货快"]。
    """
    # 文本 token 化
    encoding = tokenizer(
        text,
        max_length=Config["max_len"],
        truncation=True,
        padding="max_length",
        return_tensors="pt",
    )
    input_ids = encoding["input_ids"].to(device)
    attention_mask = encoding["attention_mask"].to(device)
    token_type_ids = encoding.get("token_type_ids", torch.zeros_like(input_ids)).to(device)

    # 前向推理，logits -> sigmoid 概率
    with torch.no_grad():
        logits = model(input_ids, attention_mask, token_type_ids)
        probs = torch.sigmoid(logits).squeeze(0).cpu().numpy()

    # 概率大于阈值的标签即为预测结果
    pred_tags = [tags[i] for i, p in enumerate(probs) if p >= threshold]

    # 附带每个标签的概率，便于调试与调阈值
    prob_detail = {tags[i]: round(float(p), 4) for i, p in enumerate(probs) if p >= 0.1}
    return pred_tags, prob_detail


# ---------------------------------------------------------------------------
# 3. 主流程
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="BERT 商品评论情感多标签分类——推理")
    parser.add_argument("--text", type=str, default=None, help="待预测的评论文本")
    parser.add_argument("--input_file", type=str, default=None, help="批量预测：每行一条文本的文件")
    parser.add_argument("--output_file", type=str, default=None, help="批量预测结果输出 CSV 路径")
    parser.add_argument("--checkpoint", type=str, default=None,
                        help="模型检查点路径（默认使用最佳模型）")
    parser.add_argument("--device", type=str, default=None, help="设备：cuda / cpu（默认自动选择）")
    parser.add_argument("--threshold", type=float, default=None,
                        help="标签命中概率阈值（默认用 config.py 中的 threshold）")
    args = parser.parse_args()

    # 必须提供文本或批量文件之一
    if not args.text and not args.input_file:
        print("用法示例：")
        print('  python scripts/predict.py --text "客服推荐的尺码合适，发货也很快"')
        print('  python scripts/predict.py --input_file data/synthetic/sample_texts.txt --output_file data/synthetic/predict_result.csv')
        sys.exit(1)

    # 自动选择设备
    device = torch.device(get_device(args.device))
    print(f"[设备] 使用 {device} 推理")

    # 判定阈值：命令行 > 配置文件
    threshold = args.threshold if args.threshold is not None else Config["threshold"]
    print(f"[阈值] 标签判定阈值 = {threshold}")

    # 加载模型（默认最佳模型，可指定其他检查点）
    checkpoint_path = args.checkpoint or Config["best_model_path"]
    model, tokenizer, tags = load_model(checkpoint_path, device)
    print(f"[模型] 加载检查点：{checkpoint_path}，共 {len(tags)} 个标签")

    # ---- 情况一：单条文本预测 ----
    if args.text:
        text = args.text.strip()
        pred_tags, prob_detail = predict_one(text, model, tokenizer, tags, device, threshold)
        print("\n输入文本：", text)
        # 输出格式与需求示例一致：标签用中文顿号/逗号连接
        print("预测标签：", "，".join(pred_tags) if pred_tags else "（未命中任何标签）")
        print("标签概率：", prob_detail)
        return

    # ---- 情况二：批量文件预测 ----
    if not os.path.exists(args.input_file):
        raise FileNotFoundError(
            f"[文件缺失] 找不到输入文件：{args.input_file}\n"
            f"请确认文件存在，且每行是一条评论文本。"
        )

    # 读取每行文本（跳过空行）
    with open(args.input_file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    # 逐条预测
    results = []
    for i, line in enumerate(lines):
        pred_tags, _ = predict_one(line, model, tokenizer, tags, device, threshold)
        results.append({"review_id": i + 1, "text": line, "tags": "，".join(pred_tags)})

    # 输出结果
    output_file = args.output_file or os.path.join(Config["result_dir"], "predict_results.csv")
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["review_id", "text", "tags"])
        writer.writeheader()
        writer.writerows(results)

    print(f"[完成] 共预测 {len(lines)} 条文本，结果已写入：{output_file}")

    # 终端预览前几条
    print("\n预览前 5 条：")
    for row in results[:5]:
        print(f"  文本：{row['text']}")
        print(f"  预测：{row['tags']}")


if __name__ == "__main__":
    main()
