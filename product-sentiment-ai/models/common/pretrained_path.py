"""解析本地可用的中文 BERT 权重路径（只走本地，避免 HuggingFace 慢下载）。"""

from __future__ import annotations

from pathlib import Path

# models/common/pretrained_path.py -> models/
MODELS_ROOT = Path(__file__).resolve().parents[1]
COMMON = MODELS_ROOT / "bert" / "common"

CANDIDATES = [
    COMMON
    / "pretrained"
    / "models"
    / "tiansz--bert-base-chinese"
    / "snapshots"
    / "master",
    COMMON / "pretrained" / "bert-base-chinese",
    COMMON / "checkpoints" / "bert_all",
]


def _is_local_model_dir(path: Path) -> bool:
    if not (path / "config.json").exists():
        return False
    return (path / "model.safetensors").exists() or (path / "pytorch_model.bin").exists()


def resolve_bert_model(preferred: str | None = None) -> str:
    """
    返回本地模型目录的绝对路径。
    preferred 若给出，必须是已存在的本地目录（禁止返回 hub id）。
    """
    if preferred:
        p = Path(preferred)
        if _is_local_model_dir(p):
            return str(p.resolve())
        raise FileNotFoundError(
            f"本地模型目录无效: {preferred}\n"
            "请传已下载的目录，或先运行: python models/common/scripts/download_bert.py"
        )

    for c in CANDIDATES:
        if _is_local_model_dir(c):
            print(f"使用本地 BERT: {c}")
            return str(c.resolve())

    raise FileNotFoundError(
        "未找到本地中文 BERT 权重。请先运行（国内快）：\n"
        "  python models/common/scripts/download_bert.py\n"
        f"期望路径之一:\n  {CANDIDATES[0]}"
    )


def ensure_bert_pretrained() -> str:
    """若本地没有权重，尝试 ModelScope 下载后再 resolve。"""
    try:
        return resolve_bert_model()
    except FileNotFoundError:
        pass

    from modelscope import snapshot_download

    out = COMMON / "pretrained"
    out.mkdir(parents=True, exist_ok=True)
    print("本地无权重，开始 ModelScope 下载 tiansz/bert-base-chinese ...")
    snapshot_download("tiansz/bert-base-chinese", cache_dir=str(out))
    return resolve_bert_model()
