"""读划分后的原表 CSV（列与队员一致），内存中转成英文 key 宽表再编码。

训练宽表示例（不落盘）:
{"category":"服饰服装","text":"...", "size":null,"fabric":1,"color":0,"fit":0,...}
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import pandas as pd
import torch
from torch.utils.data import Dataset
from transformers import PreTrainedTokenizerBase

LABEL2ID = {None: 0, 0: 1, 1: 2}
ID2LABEL = {0: None, 1: 0, 2: 1}


def _parse_attributes(raw: Any) -> list[dict]:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return []
    if isinstance(raw, list):
        return raw
    s = str(raw).strip()
    if not s:
        return []
    try:
        data = json.loads(s)
    except json.JSONDecodeError:
        data = ast.literal_eval(s)
    if not isinstance(data, list):
        return []
    return data


def polarity_to_label(polarity: Any) -> int | None:
    if polarity is None or (isinstance(polarity, float) and pd.isna(polarity)):
        return None
    if isinstance(polarity, str):
        p = polarity.strip().lower()
        if p in {"pos", "positive", "1"}:
            return 1
        if p in {"neg", "negative", "0"}:
            return 0
        if p in {"", "null", "none", "nan"}:
            return None
    if polarity == 1:
        return 1
    if polarity == 0:
        return 0
    return None


def row_to_wide(
    category: str,
    text: str,
    attributes_raw: Any,
    aspect_map: dict[str, str],
) -> dict[str, Any]:
    """aspect_map: en_key -> zh_name（对齐 CSV attributes）。"""
    sample: dict[str, Any] = {"category": category, "text": text}
    for en in aspect_map:
        sample[en] = None

    zh_to_en = {zh: en for en, zh in aspect_map.items()}
    for item in _parse_attributes(attributes_raw):
        if not isinstance(item, dict):
            continue
        aspect_zh = item.get("aspect")
        en = zh_to_en.get(aspect_zh)
        if en is None:
            continue
        sample[en] = polarity_to_label(item.get("polarity"))
    return sample


def load_wide_records(
    csv_path: Path,
    category: str,
    aspect_map: dict[str, str],
    text_col: str = "评论内容_clean",
    category_col: str = "类别",
    attributes_col: str = "attributes",
) -> list[dict[str, Any]]:
    if not aspect_map:
        raise ValueError(f"品类 {category} 无属性，跳过")
    if not csv_path.exists():
        raise FileNotFoundError(
            f"未找到划分文件: {csv_path}\n请先运行: python split_data.py"
        )

    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    for col in (text_col, category_col, attributes_col):
        if col not in df.columns:
            raise ValueError(f"CSV 缺少列 {col}，当前={list(df.columns)}")

    sub = df[df[category_col].astype(str) == str(category)].copy()
    records: list[dict[str, Any]] = []
    for _, row in sub.iterrows():
        text = row[text_col]
        if pd.isna(text) or not str(text).strip():
            continue
        records.append(
            row_to_wide(
                category=str(category),
                text=str(text).strip(),
                attributes_raw=row[attributes_col],
                aspect_map=aspect_map,
            )
        )
    return records


def random_sample_records(
    records: list[dict[str, Any]],
    max_samples: int | None,
    seed: int,
) -> list[dict[str, Any]]:
    """随机抽，避免按文件顺序只抽到单一类目排序块。"""
    if max_samples is None:
        return records
    n = int(max_samples)
    if n <= 0 or len(records) <= n:
        return records
    idx = pd.Series(range(len(records))).sample(n=n, random_state=seed).tolist()
    return [records[i] for i in idx]


def labels_to_tensor(sample: dict[str, Any], aspects: list[str]) -> torch.Tensor:
    ids = []
    for a in aspects:
        lab = sample.get(a, None)
        if lab not in LABEL2ID:
            lab = None
        ids.append(LABEL2ID[lab])
    return torch.tensor(ids, dtype=torch.long)


class AspectDataset(Dataset):
    def __init__(
        self,
        records: list[dict[str, Any]],
        tokenizer: PreTrainedTokenizerBase,
        aspects: list[str],
        max_length: int = 128,
    ) -> None:
        self.records = list(records)
        self.tokenizer = tokenizer
        self.aspects = aspects
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        sample = self.records[idx]
        encoded = self.tokenizer(
            str(sample["text"]),
            truncation=True,
            padding="max_length",
            max_length=self.max_length,
            return_tensors="pt",
        )
        item = {k: v.squeeze(0) for k, v in encoded.items()}
        item["labels"] = labels_to_tensor(sample, self.aspects)
        return item


if __name__ == "__main__":
    from config import get_aspect_map, load_config, resolve_path

    cfg = load_config()
    cat = "服饰服装"
    amap = get_aspect_map(cfg, cat)
    path = resolve_path(cfg["data"]["processed_dir"]) / cfg["data"]["train_file"]
    recs = load_wide_records(path, cat, amap)
    print(f"品类={cat} 样本数={len(recs)}")
    if recs:
        print(json.dumps(recs[0], ensure_ascii=False))
