"""推理：输入 category+text → 英文属性 key 的 JSON（text 与输入一致）。

输入:  {"category":"服饰服装","text":"..."}
输出:  {"category":"服饰服装","text":"...","size":null,"fabric":1,"color":0,"fit":0,...}
"""

from __future__ import annotations

import argparse
import json
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

import torch
from transformers import BertTokenizer

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import get_aspects, load_config, resolve_path
from dataset import ID2LABEL
from model import CategoryAspectBert
from train import safe_subdir


def _ckpt_dir(cfg: dict, category: str) -> Path:
    return resolve_path(cfg["output_dir"]) / safe_subdir(category) / "best"


@lru_cache(maxsize=16)
def _load_bundle(ckpt: str):
    path = Path(ckpt)
    if not path.exists():
        raise FileNotFoundError(f"未找到类目权重: {path}，请先训练该品类")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = BertTokenizer.from_pretrained(path / "tokenizer")
    model = CategoryAspectBert.from_pretrained(path).to(device)
    model.eval()
    return tokenizer, model, device


def predict_fun(data: dict[str, Any], config_path: str | None = None) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise TypeError("data 应为 dict，含 category 与 text")
    category = data.get("category")
    text = data.get("text")
    if not category or text is None:
        raise ValueError('需要字段: {"category": "...", "text": "..."}')

    cfg = load_config(Path(config_path) if config_path else None)
    aspects = get_aspects(cfg, str(category))
    if not aspects:
        raise ValueError(f"品类无属性，无法预测: {category}")

    ckpt = str(_ckpt_dir(cfg, str(category)))
    tokenizer, model, device = _load_bundle(ckpt)
    max_length = int(cfg.get("max_length", 128))

    encoded = tokenizer(
        str(text),
        truncation=True,
        padding=True,
        max_length=max_length,
        return_tensors="pt",
    )
    encoded = {k: v.to(device) for k, v in encoded.items()}
    with torch.no_grad():
        logits = model(**encoded)["logits"][0]
        pred_ids = logits.argmax(dim=-1).cpu().tolist()

    result: dict[str, Any] = {"category": str(category), "text": str(text)}
    for aspect, pid in zip(aspects, pred_ids):
        result[aspect] = ID2LABEL[int(pid)]
    return result


def predict_batch(items: list[dict[str, Any]], config_path: str | None = None) -> list[dict]:
    """一次预测多条（可含多个类目）。"""
    return [predict_fun(x, config_path=config_path) for x in items]


def main() -> None:
    parser = argparse.ArgumentParser(description="类目 BERT 推理")
    parser.add_argument("--category", type=str, default=None)
    parser.add_argument("--text", type=str, default=None)
    parser.add_argument("--json", type=str, default=None, help='单条 JSON 或 JSON 数组文件路径')
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()

    cfg_path = str(args.config) if args.config else None
    if args.json:
        raw = Path(args.json).read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, list):
            out = predict_batch(data, config_path=cfg_path)
        else:
            out = predict_fun(data, config_path=cfg_path)
    else:
        if not args.category or args.text is None:
            raise SystemExit("请提供 --category 与 --text，或 --json")
        out = predict_fun(
            {"category": args.category, "text": args.text},
            config_path=cfg_path,
        )
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
