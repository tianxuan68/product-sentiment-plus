"""统一读取 processed 评论切分。"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
PROCESSED = ROOT / "data" / "processed"


def load_split(name: str = "train") -> pd.DataFrame:
    mapping = {
        "train": PROCESSED / "reviews_train.csv",
        "val": PROCESSED / "reviews_val.csv",
        "all": PROCESSED / "reviews.csv",
        "test": PROCESSED / "reviews_test.csv",
    }
    path = mapping[name]
    if not path.exists():
        raise FileNotFoundError(
            f"缺少 {path}，请先运行 data/scripts/preprocess/prepare_reviews.py"
        )
    return pd.read_csv(path, encoding="utf-8-sig")


def load_xy(name: str = "train"):
    df = load_split(name)
    if "sentiment" not in df.columns:
        raise ValueError(f"{name} 无 sentiment 列，不能用于有监督训练")
    texts = df["sentence"].fillna("").astype(str).tolist()
    labels = df["sentiment"].astype(int).tolist()
    return texts, labels, df
