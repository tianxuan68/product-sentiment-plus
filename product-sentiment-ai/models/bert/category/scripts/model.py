"""类目专属多属性模型：共享 BERT + 每个属性一个 3 类头。

# 自定义 Module：1个继承2个重写
"""

from __future__ import annotations

from pathlib import Path

import torch
import torch.nn as nn
from transformers import BertModel, BertConfig


class CategoryAspectBert(nn.Module):
    """输入 [CLS] 表征，对 N 个属性各输出 3 类 logits。"""

    def __init__(self, pretrained_name_or_path: str, aspects: list[str], num_labels: int = 3):
        super().__init__()
        self.aspects = list(aspects)
        self.num_labels = num_labels
        self.bert = BertModel.from_pretrained(pretrained_name_or_path)
        hidden = self.bert.config.hidden_size
        self.heads = nn.ModuleDict(
            {a: nn.Linear(hidden, num_labels) for a in self.aspects}
        )
        self.dropout = nn.Dropout(self.bert.config.hidden_dropout_prob)

    # 前向：返回 loss(可选) + 各方 logits
    def forward(
        self,
        input_ids=None,
        attention_mask=None,
        token_type_ids=None,
        labels=None,
    ):
        outputs = self.bert(
            input_ids=input_ids,
            attention_mask=attention_mask,
            token_type_ids=token_type_ids,
        )
        pooled = self.dropout(outputs.pooler_output)
        # logits: [batch, n_aspects, 3]
        logits_list = [self.heads[a](pooled) for a in self.aspects]
        logits = torch.stack(logits_list, dim=1)

        loss = None
        if labels is not None:
            # labels: [batch, n_aspects]
            loss_fn = nn.CrossEntropyLoss()
            loss = loss_fn(logits.reshape(-1, self.num_labels), labels.reshape(-1))

        return {"loss": loss, "logits": logits}

    def save_pretrained(self, save_dir: str | Path) -> None:
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)
        self.bert.save_pretrained(save_dir / "bert")
        torch.save(
            {
                "aspects": self.aspects,
                "num_labels": self.num_labels,
                "heads": self.heads.state_dict(),
            },
            save_dir / "aspect_heads.pt",
        )
        # 方便核对
        (save_dir / "aspects.txt").write_text("\n".join(self.aspects), encoding="utf-8")

    @classmethod
    def from_pretrained(cls, load_dir: str | Path, bert_fallback: str | None = None):
        load_dir = Path(load_dir)
        try:
            meta = torch.load(load_dir / "aspect_heads.pt", map_location="cpu", weights_only=False)
        except TypeError:
            meta = torch.load(load_dir / "aspect_heads.pt", map_location="cpu")
        aspects = meta["aspects"]
        num_labels = int(meta.get("num_labels", 3))
        bert_dir = load_dir / "bert"
        bert_name = str(bert_dir if bert_dir.exists() else (bert_fallback or bert_dir))
        model = cls(bert_name, aspects=aspects, num_labels=num_labels)
        model.heads.load_state_dict(meta["heads"])
        return model


if __name__ == "__main__":
    # 3. 冒烟：随机输入看 logits 形状
    cfg_path = Path(__file__).resolve().parents[1] / "configs" / "default.yaml"
    print(f"配置路径占位: {cfg_path}（完整冒烟请先放好 bert-base-chinese）")
    config = BertConfig(hidden_size=32, num_hidden_layers=1, num_attention_heads=4, intermediate_size=64)
    bert = BertModel(config)
    m = CategoryAspectBert.__new__(CategoryAspectBert)
    nn.Module.__init__(m)
    m.aspects = ["面料", "版型"]
    m.num_labels = 3
    m.bert = bert
    m.dropout = nn.Dropout(0.1)
    m.heads = nn.ModuleDict({a: nn.Linear(32, 3) for a in m.aspects})
    x = torch.randint(0, 100, (2, 8))
    mask = torch.ones_like(x)
    out = m(input_ids=x, attention_mask=mask, labels=torch.zeros(2, 2, dtype=torch.long))
    print(f"logits形状: {tuple(out['logits'].shape)} loss={float(out['loss']):.4f}")
