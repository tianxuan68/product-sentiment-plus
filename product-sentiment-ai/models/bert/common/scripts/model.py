# -*- coding: utf-8 -*-
"""
model.py —— BERT 属性级情感分类模型

结构：
    类别+评论 -> BERT 编码 -> [CLS] 向量 -> Dropout -> Linear(16) -> logits

    输出 16 维 logits：前 8 位 = 各属性「好」（正面），后 8 位 = 各属性「坏」（负面）。
    训练时用 BCEWithLogitsLoss 对每一位做 sigmoid 二分类，
    即同时学习「某属性是否被提及」和「提及时的极性」。
"""

import torch
import torch.nn as nn
from transformers import AutoModel


class BertAspectModel(nn.Module):
    """
    基于 bert-base-chinese 的属性级情感分类模型。

    在预训练 BERT 之上加一层全连接分类头：
        BERT 的 [CLS] 输出向量（768 维）-> Dropout -> Linear(16)。
    """

    def __init__(self, bert_model_dir: str, num_labels: int, dropout: float = 0.3):
        """
        参数：
            bert_model_dir: 本地预训练 BERT 模型目录（含 config.json / pytorch_model.bin）。
            num_labels:     标签总数（分类头输出维度，本任务为 16）。
            dropout:        分类头前 Dropout 比例。
        """
        super().__init__()

        # 加载本地预训练 BERT 编码器（只取编码部分，不含预训练任务头）
        self.bert = AutoModel.from_pretrained(
            bert_model_dir,
            local_files_only=True,  # 只使用本地文件，不联网
        )
        hidden_size = self.bert.config.hidden_size

        # 分类头：先 Dropout 防过拟合，再映射到 16 维
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Linear(hidden_size, num_labels)

    def forward(self, input_ids, attention_mask=None, token_type_ids=None) -> torch.Tensor:
        """
        前向传播。

        参数：
            input_ids:      token id 序列，shape = (batch, max_len)。
            attention_mask: 注意力掩码，padding 位置为 0。
            token_type_ids: 段类型 id（0=类别段，1=评论段）。

        返回：
            logits，shape = (batch, 16)，未经 sigmoid 的原始分值。
        """
        outputs = self.bert(
            input_ids=input_ids,
            attention_mask=attention_mask,
            token_type_ids=token_type_ids,
        )
        # last_hidden_state: (batch, max_len, hidden)；取 [CLS] -> (batch, hidden)
        cls_vec = outputs.last_hidden_state[:, 0, :]

        logits = self.classifier(self.dropout(cls_vec))
        return logits


# 兼容旧类名：历史检查点可能以旧名引用，提供别名便于加载
BertMultiLabelModel = BertAspectModel
