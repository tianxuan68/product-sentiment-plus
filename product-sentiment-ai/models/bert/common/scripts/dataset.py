# -*- coding: utf-8 -*-
"""
dataset.py —— 多标签分类数据集

职责：
    1. build_label_index()：根据标签列表构建 标签名 <-> 下标 的映射；
    2. make_multi_hot()：把标签名列表转换为 multi-hot 0/1 向量；
    3. MultiLabelDataset：PyTorch Dataset，负责把文本 token 化并和标签对齐。

说明：
    多标签分类中，一条评论可以同时属于多个标签，
    因此标签被编码成「0/1 的 one-hot 向量」，向量的每一位代表一个标签是否命中。
"""

import torch
from torch.utils.data import Dataset


# ---------------------------------------------------------------------------
# 1. 标签索引构建
# ---------------------------------------------------------------------------
def build_label_index(tags: list) -> tuple:
    """
    把标签列表转成两个映射，供编码 / 解码使用。

    参数：
        tags: 全部标签名列表，例如 ["发货快", "尺码合适", ...]。

    返回：
        (tag_to_idx, idx_to_tag)
        tag_to_idx: {标签名: 下标}
        idx_to_tag: {下标: 标签名}
    """
    tag_to_idx = {tag: i for i, tag in enumerate(tags)}
    idx_to_tag = {i: tag for i, tag in enumerate(tags)}
    return tag_to_idx, idx_to_tag


# ---------------------------------------------------------------------------
# 2. multi-hot 标签编码
# ---------------------------------------------------------------------------
def make_multi_hot(tag_list: list, tag_to_idx: dict, num_labels: int) -> torch.Tensor:
    """
    把一条评论的标签名列表转成 multi-hot 向量。

    参数：
        tag_list:   该评论的标签名列表，例如 ["发货快", "尺码合适"]。
        tag_to_idx: {标签名: 下标}。
        num_labels: 标签总数（向量长度）。

    返回：
        shape = (num_labels,) 的 0/1 张量。
    """
    label_vec = torch.zeros(num_labels, dtype=torch.float)
    for tag in tag_list:
        tag = tag.strip()
        # 遇到词表中不存在的标签直接跳过（未来字典扩充时，旧数据不至于报错）
        if tag in tag_to_idx:
            label_vec[tag_to_idx[tag]] = 1.0
    return label_vec


# ---------------------------------------------------------------------------
# 3. 多标签数据集
# ---------------------------------------------------------------------------
class MultiLabelDataset(Dataset):
    """
    文本多标签分类数据集。

    每个样本返回：
        {
            "input_ids":      token id 序列 (max_len,)
            "attention_mask": 注意力掩码 (max_len,)，padding 位置为 0
            "token_type_ids": 段类型 id (max_len,)，单句分类恒为 0
            "labels":         multi-hot 标签向量 (num_labels,)
        }
    """

    def __init__(self, texts, tag_lists, tokenizer, tag_to_idx, max_len, num_labels):
        """
        参数：
            texts:      评论文本列表。
            tag_lists:  每条评论的标签名列表（与 texts 一一对应）。
            tokenizer:  HuggingFace 分词器。
            tag_to_idx: 标签名到下标映射。
            max_len:    文本最大长度。
            num_labels: 标签总数。
        """
        self.texts = texts
        self.tag_lists = tag_lists
        self.tokenizer = tokenizer
        self.tag_to_idx = tag_to_idx
        self.max_len = max_len
        self.num_labels = num_labels

    def __len__(self) -> int:
        """数据集样本数。"""
        return len(self.texts)

    def __getitem__(self, idx: int) -> dict:
        """返回第 idx 个样本的模型输入与标签。"""
        text = self.texts[idx]

        # 文本 token 化：截断到 max_len，并填充到定长（方便批处理）
        encoding = self.tokenizer(
            text,
            max_length=self.max_len,
            truncation=True,   # 超出部分截断
            padding="max_length",  # 填充到 max_len
            return_tensors="pt",   # 返回 PyTorch 张量
        )

        # 去掉 batch 维度（DataLoader 会自动重新加 batch）
        input_ids = encoding["input_ids"].squeeze(0)
        attention_mask = encoding["attention_mask"].squeeze(0)
        # token_type_ids 仅在部分老 tokenizer 中存在，缺失时构造全 0 掩码
        if "token_type_ids" in encoding:
            token_type_ids = encoding["token_type_ids"].squeeze(0)
        else:
            token_type_ids = torch.zeros_like(input_ids)

        # 标签编码为 multi-hot 向量
        labels = make_multi_hot(self.tag_lists[idx], self.tag_to_idx, self.num_labels)

        return {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "token_type_ids": token_type_ids,
            "labels": labels,
        }


# ---------------------------------------------------------------------------
# 4. 批数据整理函数（DataLoader 的 collate_fn）
# ---------------------------------------------------------------------------
def collate_batch(batch: list) -> dict:
    """
    把一批样本堆叠成张量。

    参数：
        batch: MultiLabelDataset.__getitem__ 返回的字典列表。

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
