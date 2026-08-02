# -*- coding: utf-8 -*-
"""
predict.py —— 属性级情感分类推理模块（可独立调用 / 批量文件）

功能：
    1. predict_aspects(category, text)    独立函数：输入「商品类别 + 评论」，输出 8 个属性的情感。
       既可在脚本里 import 调用，也可被 API 服务（api_server.py）直接复用。
    2. predict_file(input_file, ...)      批量预测：读取文件（CSV/TXT），逐条预测并写出结果文件。
    3. main()                             命令行入口。

命令行运行方式：
    python scripts/predict.py --category 图书音像 --text "是真品 跟在海关买的一样 ..."
    python scripts/predict.py --category 图书音像 --input_file data/data_pre/xx.csv --output_file results/xx_result.csv
    python scripts/predict.py --checkpoint checkpoints/best_model.pt --text "..."
"""

import os
import sys
import csv
import argparse

# 把本脚本所在目录加入 sys.path，保证直接运行时也能互相 import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np
import torch
from transformers import AutoTokenizer

from config import Config, get_device, LABEL_NAMES
from model import BertAspectModel
from train import decode_polarities

# 降低 transformers 日志噪音（本地权重「MLM 头权重未匹配」告警属正常现象）
from transformers import logging as tf_logging
tf_logging.set_verbosity_error()


# ---------------------------------------------------------------------------
# 1. 加载模型与分词器
# ---------------------------------------------------------------------------
def load_model(checkpoint_path: str, device):
    """
    从检查点文件恢复模型、分词器与元信息。

    参数：
        checkpoint_path: 训练时保存的 .pt 检查点。
        device:          计算设备。

    返回：
        (model, tokenizer, meta)
        model:     已加载权重的属性级情感模型。
        tokenizer: BERT 分词器。
        meta:      检查点中的元信息字典（aspects / thresholds / categories / max_len 等）。
    """
    # 充分利用本机全部 CPU 核，提升推理速度
    torch.set_num_threads(os.cpu_count() or 4)

    if not os.path.exists(checkpoint_path):
        raise FileNotFoundError(
            f"[模型文件缺失] 找不到检查点：{checkpoint_path}\n"
            f"请先运行 python scripts/train.py 训练模型并保存权重。"
        )

    checkpoint = torch.load(checkpoint_path, map_location=device)
    num_labels = checkpoint["num_labels"]

    bert_model_dir = checkpoint.get("bert_model_dir", Config["model_name_or_path"])
    model = BertAspectModel(bert_model_dir, num_labels, Config["dropout"])
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device)
    model.eval()

    tokenizer = AutoTokenizer.from_pretrained(bert_model_dir, local_files_only=True)
    return model, tokenizer, checkpoint


# ---------------------------------------------------------------------------
# 2. 核心独立函数：预测单条评论的属性级情感
# ---------------------------------------------------------------------------
def predict_aspects(category: str, text: str, model=None, tokenizer=None,
                    device=None, checkpoint_path: str = None,
                    return_detail: bool = False):
    """
    预测一条商品评论在各属性上的情感（好 / 坏 / 未提及）。

    支持两种调用方式：
        1) 不传 model/tokenizer：自动加载默认检查点（checkpoint_path 或 Config.best_model_path）；
        2) 传 model/tokenizer：复用已加载的模型（供 API 服务避免重复加载）。

    参数：
        category:       商品类别名，如 "图书音像"。
        text:           评论文本。
        model:          可选，已加载的模型（None 则自动加载）。
        tokenizer:      可选，已加载的分词器。
        device:         可选，计算设备。
        checkpoint_path: 可选，模型检查点路径（默认用最佳模型）。
        return_detail:  是否返回详细结果（默认 False）。

    返回（默认 return_detail=False，符合需求「输出为一个列表」）：
        列表，包含 1 个或多个「属性+情感」标签，例如：
            ["物流快", "质量好"]      # 命中的属性标签
            []                       # 未提及任何属性时为空列表

    返回（return_detail=True）：
        dict，含逐属性概率等调试信息：
            {
              "category": "图书音像",
              "text": "…",
              "labels": ["物流快", "质量好"],
              "aspects": [
                  {"aspect": "质量", "polarity": "好", "polarity_code": 1,
                   "prob_pos": 0.95, "prob_neg": 0.02},
                  …
              ]
            }
    """
    # 惰性加载：第一次调用时自动加载模型，后续调用可复用
    if model is None or tokenizer is None:
        device = torch.device(get_device(device))
        ckpt = checkpoint_path or Config["best_model_path"]
        model, tokenizer, meta = load_model(ckpt, device)
    else:
        meta = None

    aspects = (meta or {}).get("aspects", Config["aspects"])
    thresholds = (meta or {}).get("thresholds")
    # 检查点未保存阈值时回退默认阈值
    if not thresholds:
        thresholds = {a: {"pos": Config["default_threshold"], "neg": Config["default_threshold"]}
                      for a in aspects}
    max_len = (meta or {}).get("max_len", Config["max_len"])

    # 编码「类别 + 评论」两个文本段
    encoding = tokenizer(text=category, text_pair=text,
                         max_length=max_len, truncation=True,
                         padding="max_length", return_tensors="pt")
    with torch.no_grad():
        logits = model(encoding["input_ids"].to(device),
                       encoding["attention_mask"].to(device),
                       encoding.get("token_type_ids",
                                    torch.zeros_like(encoding["input_ids"])).to(device))
        probs = torch.sigmoid(logits).squeeze(0).cpu().numpy()  # (16,)

    # 解码极性矩阵（1=好, 0=坏, -1=未提及）
    pred_pol = decode_polarities(probs[None, :], thresholds, aspects)[0]

    n = len(aspects)
    labels = []
    aspect_results = []
    for a_idx, a in enumerate(aspects):
        p_pos = float(probs[a_idx])
        p_neg = float(probs[n + a_idx])
        code = int(pred_pol[a_idx])
        polarity = "好" if code == 1 else ("坏" if code == 0 else "未提及")
        aspect_results.append({
            "aspect": a,
            "polarity": polarity,
            "polarity_code": code,
            "prob_pos": round(p_pos, 4),
            "prob_neg": round(p_neg, 4),
        })
        if code in (1, 0):
            labels.append(f"{a}{polarity}")

    if return_detail:
        return {
            "category": category,
            "text": text,
            "labels": labels,
            "aspects": aspect_results,
        }
    return labels


# ---------------------------------------------------------------------------
# 3. 批量预测：读取文件 -> 预测 -> 写出结果文件
# ---------------------------------------------------------------------------
def predict_file(input_file: str, output_file: str = None, model=None, tokenizer=None,
                 device=None, checkpoint_path: str = None,
                 category: str = "其他", category_col: str = None,
                 text_col: str = None) -> str:
    """
    批量预测一个文件中的评论，并返回处理后的结果文件路径。

    支持两种输入格式：
        - CSV：自动识别「类别」列与「评论文本」列（也可用 category_col / text_col 指定）。
        - TXT：每行一条评论，类别统一用参数 category（默认「其他」）。

    参数：
        input_file:     输入文件路径（CSV / TXT）。
        output_file:    输出结果 CSV 路径（默认写到 results/predict_file_result.csv）。
        model/tokenizer/device/checkpoint_path: 同 predict_aspects。
        category:       TXT 格式时使用的统一类别名。
        category_col:   CSV 中类别列的列名（不传则自动识别）。
        text_col:       CSV 中评论列的列名（不传则自动识别）。

    返回：
        输出 CSV 的绝对路径。每行包含：category, text, aspects_summary,
        以及 8 列「属性:极性」明细与 16 列概率（可选列较多，便于下游使用）。
    """
    device = torch.device(get_device(device))
    if model is None or tokenizer is None:
        ckpt = checkpoint_path or Config["best_model_path"]
        model, tokenizer, meta = load_model(ckpt, device)
    else:
        meta = None

    aspects = (meta or {}).get("aspects", Config["aspects"])
    thresholds = (meta or {}).get("thresholds") or {
        a: {"pos": Config["default_threshold"], "neg": Config["default_threshold"]} for a in aspects
    }

    file_lower = str(input_file).lower()
    if file_lower.endswith(".csv"):
        df = pd.read_csv(input_file, encoding="utf-8-sig")
        # 自动识别类别列与文本列
        if category_col is None:
            cat_candidates = [c for c in df.columns if ("类别" in str(c)) or ("category" in str(c).lower())]
            category_col = cat_candidates[0] if cat_candidates else None
        if text_col is None:
            text_candidates = [c for c in df.columns
                               if ("评论" in str(c)) or ("text" in str(c).lower())
                               or ("content" in str(c).lower()) or ("内容" in str(c))]
            text_col = text_candidates[0] if text_candidates else None
        if text_col is None:
            raise ValueError(
                f"[批量预测] CSV 未找到评论文本列，实际列：{list(df.columns)}。"
                f"请用 --text_col 指定评论列。"
            )
        rows = []
        for _, r in df.iterrows():
            cat = str(r[category_col]).strip() if category_col else category
            rows.append((cat, str(r[text_col]).strip()))
    else:
        # 按 TXT 处理：每行一条评论
        with open(input_file, "r", encoding="utf-8") as f:
            lines = [ln.strip() for ln in f if ln.strip()]
        rows = [(category, ln) for ln in lines]

    # 逐条预测（用 return_detail=True 拿到逐属性明细列）
    results = []
    for i, (cat, txt) in enumerate(rows):
        if not txt:
            continue
        pred = predict_aspects(cat, txt, model=model, tokenizer=tokenizer,
                               device=device, checkpoint_path=checkpoint_path,
                               return_detail=True)
        row = {
            "index": i + 1,
            "category": cat,
            "text": txt,
            "labels": "，".join(pred["labels"]),  # 标签列表，如「物流快，质量好」
        }
        for item in pred["aspects"]:
            row[f"{item['aspect']}:polarity"] = item["polarity"]
        results.append(row)

    out_df = pd.DataFrame(results)
    output_file = output_file or os.path.join(Config["result_dir"], "predict_file_result.csv")
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    out_df.to_csv(output_file, index=False, encoding="utf-8-sig")
    return output_file


# ---------------------------------------------------------------------------
# 4. 命令行入口
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="BERT 属性级情感分类——推理")
    parser.add_argument("--category", type=str, default=None, help="商品类别（如 图书音像）")
    parser.add_argument("--text", type=str, default=None, help="单条评论文本")
    parser.add_argument("--input_file", type=str, default=None, help="批量预测：CSV 或每行一条评论的 TXT")
    parser.add_argument("--output_file", type=str, default=None, help="批量预测结果输出 CSV 路径")
    parser.add_argument("--checkpoint", type=str, default=None, help="模型检查点路径（默认用最佳模型）")
    parser.add_argument("--device", type=str, default=None, help="设备：cuda / cpu（默认自动选择）")
    args = parser.parse_args()

    if not args.text and not args.input_file:
        print("用法示例：")
        print('  python scripts/predict.py --category 图书音像 --text "是真品 跟在海关买的一样"')
        print("  python scripts/predict.py --category 图书音像 --input_file data/data_pre/xx.csv --output_file results/xx.csv")
        sys.exit(1)

    device = torch.device(get_device(args.device))
    print(f"[设备] 使用 {device} 推理")

    # 单条预测
    if args.text:
        category = args.category or "其他"
        result = predict_aspects(category, args.text, device=device,
                                 checkpoint_path=args.checkpoint, return_detail=True)
        print("\n输入类别：", result["category"])
        print("输入评论：", result["text"])
        print("预测标签列表：", result["labels"])  # 需求格式：如 ['物流快', '质量好']
        print("\n各属性明细：")
        for item in result["aspects"]:
            print(f"  {item['aspect']}: {item['polarity']} "
                  f"(好概率 {item['prob_pos']:.3f} / 坏概率 {item['prob_neg']:.3f})")
        return

    # 批量预测
    if not os.path.exists(args.input_file):
        raise FileNotFoundError(f"[文件缺失] 找不到输入文件：{args.input_file}")
    output_file = predict_file(args.input_file, args.output_file, device=device,
                               checkpoint_path=args.checkpoint, category=args.category or "其他")
    print(f"[完成] 批量预测结果已写入：{output_file}")


if __name__ == "__main__":
    main()
