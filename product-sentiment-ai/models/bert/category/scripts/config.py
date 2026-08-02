"""读取类目 BERT 配置：default.yaml + aspects_vocab。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

# scripts → category → bert → models → product-sentiment-ai
AI_ROOT = Path(__file__).resolve().parents[4]
CATEGORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = CATEGORY_ROOT / "configs" / "default.yaml"


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"配置应为字典: {path}")
    return data


def resolve_path(p: str | Path | None) -> Path | None:
    if p is None:
        return None
    path = Path(p)
    if path.is_absolute():
        return path
    return (AI_ROOT / path).resolve()


def load_config(config_path: Path | None = None) -> dict[str, Any]:
    cfg = load_yaml(config_path or DEFAULT_CONFIG)
    vocab_path = resolve_path(cfg.get("aspects_vocab"))
    if vocab_path is None or not vocab_path.exists():
        raise FileNotFoundError(f"未找到方面词表: {vocab_path}")
    vocab = load_yaml(vocab_path)
    cfg["aspects_by_category"] = vocab.get("categories") or {}
    cfg["_ai_root"] = str(AI_ROOT)
    cfg["_config_path"] = str(config_path or DEFAULT_CONFIG)
    return cfg


def get_aspect_map(cfg: dict[str, Any], category: str) -> dict[str, str]:
    """英文 key → 中文（CSV attributes 里的 aspect 名）。"""
    mapping = cfg.get("aspects_by_category", {}).get(category)
    if mapping is None:
        raise KeyError(f"词表中无品类: {category}")
    if isinstance(mapping, list):
        # 兼容旧列表格式：中英文同名
        return {str(x): str(x) for x in mapping}
    return {str(k): str(v) for k, v in mapping.items()}


def get_aspects(cfg: dict[str, Any], category: str) -> list[str]:
    """英文属性 key 列表（模型头 / JSON 输出用）。"""
    return list(get_aspect_map(cfg, category).keys())


def list_trainable_categories(cfg: dict[str, Any]) -> list[str]:
    return [c for c, m in cfg.get("aspects_by_category", {}).items() if m]


def resolve_model_name(cfg: dict[str, Any]) -> str:
    model_name = cfg["model_name"]
    local = resolve_path(model_name)
    if local is not None and local.exists():
        return str(local)
    return str(model_name)


if __name__ == "__main__":
    c = load_config()
    print(f"AI_ROOT: {AI_ROOT}")
    print(f"model_name: {resolve_model_name(c)}")
    print(f"processed: {resolve_path(c['data']['processed_dir'])}")
    print(f"服饰服装: {get_aspect_map(c, '服饰服装')}")
    print(f"可训练品类数: {len(list_trainable_categories(c))}")
