"""
案例:
    统一读取 processed 评论切分。

大白话:
    train/val/test 都从这里读，训练脚本别各自拼路径。
"""

# 导包
import os

import pandas as pd


# 1. 定义函数, 读某个切分
def load_split(name="train"):
    mapping = {
        "train": "./data/processed/reviews_train.csv",
        "val": "./data/processed/reviews_val.csv",
        "all": "./data/processed/reviews.csv",
        "test": "./data/processed/reviews_test.csv",
    }
    path = mapping[name]
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"缺少 {path}，请先运行 data/scripts/preprocess/prepare_reviews.py"
        )
    return pd.read_csv(path, encoding="utf-8-sig")


# 2. 定义函数, 读成 x / y
def load_xy(name="train"):
    df = load_split(name)
    if "sentiment" not in df.columns:
        raise ValueError(f"{name} 无 sentiment 列，不能用于有监督训练")
    texts = df["sentence"].fillna("").astype(str).tolist()
    labels = df["sentiment"].astype(int).tolist()
    return texts, labels, df
