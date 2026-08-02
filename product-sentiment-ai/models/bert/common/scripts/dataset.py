# -*- coding: utf-8 -*-
"""
dataset.py —— 属性级情感分类数据集

职责：
    1. AspectDataset：PyTorch Dataset。
       每个样本输入 = 「商品类别 + 评论文本」两个文本段，
       标签 = 16 维 multi-hot（8 属性 × 2 极性：前 8 位「好」，后 8 位「坏」）。
    2. collate_batch：把一批样本堆叠成张量（DataLoader 的 collate_fn）。

输入拼接方式（利用 BERT 的段编码）：
    [CLS] 图书音像 [SEP] 是真品 跟在海关买的一样 ... [SEP]
    tokenizer 会自动生成 token_type_ids：类别段=0，评论段=1，
    让模型能区分「商品类别」与「评论内容」两部分。
"""

import torch
from torch.utils.data import Dataset


# ---------------------------------------------------------------------------
# 1. 属性级情感数据集
# ---------------------------------------------------------------------------
class AspectDataset(Dataset):
    """
    商品评论「属性级情感」分类数据集。

    每个样本返回：
        {
            "input_ids":      token id 序列 (max_len,)
            "attention_mask": 注意力掩码 (max_len,)，padding 位置为 0
            "token_type_ids": 段类型 id (max_len,)，0=类别段，1=评论段
            "labels":         multi-hot 标签向量 (16,)
        }
    """

    def __init__(self, categories, texts, label_vectors, tokenizer, max_len, num_labels):
        """
        参数：
            categories:    类别名列表（与 texts 一一对应）。
            texts:         评论文本列表。
            label_vectors: 每条评论的 16 维 0/1 标签（与 texts 一一对应）。
            tokenizer:     HuggingFace 分词器。
            max_len:       输入最大长度。
            num_labels:    标签总数（16）。
        """
        self.categories = categories
        self.texts = texts
        self.label_vectors = label_vectors
        self.tokenizer = tokenizer
        self.max_len = max_len
        self.num_labels = num_labels

    def __len__(self) -> int:
        return len(self.texts)

    def __getitem__(self, idx: int) -> dict:
        category = self.categories[idx]
        text = self.texts[idx]

        # 类别 + 评论 作为两个文本段一起编码，自动生成 [CLS] 类别 [SEP] 评论 [SEP]
        encoding = self.tokenizer(
            text=category,
            text_pair=text,
            max_length=self.max_len,
            truncation=True,
            padding="max_length",
            return_tensors="pt",
        )

        input_ids = encoding["input_ids"].squeeze(0)
        attention_mask = encoding["attention_mask"].squeeze(0)
        if "token_type_ids" in encoding:
            token_type_ids = encoding["token_type_ids"].squeeze(0)
        else:
            token_type_ids = torch.zeros_like(input_ids)

        labels = torch.tensor(self.label_vectors[idx], dtype=torch.float)

        return {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "token_type_ids": token_type_ids,
            "labels": labels,
        }


# ---------------------------------------------------------------------------
# 2. 批数据整理函数（DataLoader 的 collate_fn）
# ---------------------------------------------------------------------------
def collate_batch(batch: list) -> dict:
    """
    把一批样本堆叠成张量。

    参数：
        batch: AspectDataset.__getitem__ 返回的字典列表。

    返回：
        各字段在第 0 维堆叠后的字典。
    """
    input_ids = torch.stack([item["input_ids"] for item in batch])
    attention_mask = torch.stack([item["attention_mask"] for item in batch])
    token_type_ids = torch.stack([item["token_type_ids"] for item in batch])
    labels = torch.stack([item["labels"] for item in batch])
    return {
        "input_ids": input_ids,
        "attention_mask": attention_mask,
        "token_type_ids": token_type_ids,
        "labels": labels,
    }
