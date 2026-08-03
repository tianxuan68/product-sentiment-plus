"""
案例:
    分层打标模型：共享 BERT 编码器 + 通用头 + 各类目头。

大白话:
    底座共用；通用标签走通用头；面料/续航等走对应类目头。
    长尾类目没有专属头时，只出通用标签。
"""

# 导包
import os

import torch
import torch.nn as nn
from transformers import AutoConfig, AutoModel


def cat_key(name: str) -> str:
    """ModuleDict 键不能含斜杠等特殊字符。"""
    return (
        name.replace("/", "_")
        .replace(" ", "_")
        .replace("-", "_")
    )


def _load_encoder(model_name: str, *, config_only: bool = False):
    """加载 BERT 编码器。

    config_only=True：只建结构（权重随后由 load_state_dict 灌入），
    用于部署机没有本机绝对路径下的 pretrained 目录时。
    """
    if config_only:
        config = AutoConfig.from_pretrained(model_name, local_files_only=True)
        return AutoModel.from_config(config)
    return AutoModel.from_pretrained(model_name, local_files_only=True)


class HierarchicalTagBERT(nn.Module):
    def __init__(
        self,
        model_name,
        n_general,
        category_dims: dict[str, int],
        *,
        config_only: bool = False,
    ):
        super().__init__()
        self.encoder = _load_encoder(model_name, config_only=config_only)
        hidden = self.encoder.config.hidden_size
        self.dropout = nn.Dropout(0.1)
        self.general_head = nn.Linear(hidden, n_general)
        self.category_heads = nn.ModuleDict(
            {cat_key(c): nn.Linear(hidden, n) for c, n in category_dims.items()}
        )
        # 原始类目名 → ModuleDict 键
        self.category_name_map = {c: cat_key(c) for c in category_dims}

    def encode(self, input_ids, attention_mask):
        out = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
        cls = out.last_hidden_state[:, 0]
        return self.dropout(cls)

    def forward_general(self, input_ids, attention_mask):
        pooled = self.encode(input_ids, attention_mask)
        return self.general_head(pooled)

    def forward_category(self, input_ids, attention_mask, category: str):
        key = self.category_name_map.get(category)
        if key is None or key not in self.category_heads:
            return None
        pooled = self.encode(input_ids, attention_mask)
        return self.category_heads[key](pooled)

    def forward_both(self, input_ids, attention_mask, categories: list[str]):
        """
        一批样本：通用头整批算；类目头按样本类目逐条（或分组）算。
        返回 general_logits (B, G)，以及 list[Optional[Tensor]] 各类目 logits。
        """
        pooled = self.encode(input_ids, attention_mask)
        gen_logits = self.general_head(pooled)
        cat_logits = []
        for i, cat in enumerate(categories):
            key = self.category_name_map.get(cat)
            if key is None or key not in self.category_heads:
                cat_logits.append(None)
            else:
                cat_logits.append(self.category_heads[key](pooled[i : i + 1]))
        return gen_logits, cat_logits
