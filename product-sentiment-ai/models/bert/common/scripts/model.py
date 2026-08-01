# -*- coding: utf-8 -*-
"""
model.py —— BERT 多标签分类模型

结构：
    文本 -> [CLS] BERT 编码 -> [CLS] 向量 -> Dropout -> Linear(标签数) -> logits

    多标签分类输出一个与标签数量等长的 logits 向量，
    每个维度对应「某个标签是否命中」，训练时用 BCEWithLogitsLoss 逐位二分类。
"""

import torch
import torch.nn as nn
from transformers import AutoModel


class BertMultiLabelModel(nn.Module):
    """
    基于 bert-base-chinese 的多标签分类模型。

    在预训练 BERT 之上加一层全连接分类头：
        BERT 的 [CLS] 输出向量（768 维）-> Dropout -> Linear(num_labels)。
    """

    def __init__(self, bert_model_dir: str, num_labels: int, dropout: float = 0.3):
        """
        参数：
            bert_model_dir: 本地预训练 BERT 模型目录（含 config.json / pytorch_model.bin）。
            num_labels:     标签总数（分类头输出维度）。
            dropout:        分类头前 Dropout 比例。
        """
        super().__init__()

        # 加载本地预训练 BERT 编码器（只取编码部分，不含预训练任务头）
        self.bert = AutoModel.from_pretrained(
            bert_model_dir,
            local_files_only=True,  # 只使用本地文件，不联网
        )
        # 冻结中间层特征：BERT 输出 [CLS] 的隐藏维度
        hidden_size = self.bert.config.hidden_size

        # 分类头：先 Dropout 防过拟合，再映射到标签数
        self.dropout = nn.Dropout(dropout)
        self.classifier = nn.Linear(hidden_size, num_labels)

    def forward(self, input_ids, attention_mask=None, token_type_ids=None) -> torch.Tensor:
        """
        前向传播。

        参数：
            input_ids:      token id 序列，shape = (batch, max_len)。
            attention_mask: 注意力掩码，padding 位置为 0。
            token_type_ids: 段类型 id（单句分类可全 0）。

        返回：
            logits，shape = (batch, num_labels)，未经 sigmoid 的原始分值。
        """
        # BERT 编码，取 [CLS] 位置向量（seq 维第 0 位）作为整句表示
        outputs = self.bert(
            input_ids=input_ids,
            attention_mask=attention_mask,
            token_type_ids=token_type_ids,
        )
        # last_hidden_state: (batch, max_len, hidden)；取 [CLS] -> (batch, hidden)
        cls_vec = outputs.last_hidden_state[:, 0, :]

        # 分类头：Dropout -> 线性层 -> logits
        logits = self.classifier(self.dropout(cls_vec))
        return logits
