"""
下载中文 BERT 预训练权重到 models/bert/common/pretrained/

优先 ModelScope（国内更稳），失败再提示 HuggingFace。

用法：
  python download_bert.py
"""

from __future__ import annotations

from pathlib import Path

OUT = (
    Path(__file__).resolve().parents[2]
    / "bert"
    / "common"
    / "pretrained"
)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        from modelscope import snapshot_download
    except ImportError as e:
        raise ImportError("请先: pip install modelscope") from e

    print("从 ModelScope 下载 tiansz/bert-base-chinese ...")
    path = snapshot_download("tiansz/bert-base-chinese", cache_dir=str(OUT))
    print("下载完成:", path)
    print("训练时脚本会自动优先使用该本地路径。")


if __name__ == "__main__":
    main()
