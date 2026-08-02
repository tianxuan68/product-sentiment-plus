"""把队员原 train.csv 拷入项目，并按类别分层划分为 train/val/test（列结构不变）。

用法:
  python split_data.py
  python split_data.py --src "C:/Users/28771/Desktop/dmeo_temp/情感分析/train.csv"
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import load_config, resolve_path

DEFAULT_SRC = Path(r"C:\Users\28771\Desktop\dmeo_temp\情感分析\train.csv")


def split_dataframe(df: pd.DataFrame, category_col: str, val_ratio: float, test_ratio: float, seed: int):
    test_size = val_ratio + test_ratio
    # 分层：保证各品类在三个集合都有（样本极少的类可能失败，再回退非分层）
    try:
        train_df, temp_df = train_test_split(
            df,
            test_size=test_size,
            random_state=seed,
            stratify=df[category_col],
        )
        relative_test = test_ratio / test_size if test_size > 0 else 0.0
        val_df, test_df = train_test_split(
            temp_df,
            test_size=relative_test,
            random_state=seed,
            stratify=temp_df[category_col],
        )
    except ValueError:
        print("[warn] 分层失败，改用普通随机划分")
        train_df, temp_df = train_test_split(df, test_size=test_size, random_state=seed)
        relative_test = test_ratio / test_size if test_size > 0 else 0.0
        val_df, test_df = train_test_split(temp_df, test_size=relative_test, random_state=seed)
    return train_df.reset_index(drop=True), val_df.reset_index(drop=True), test_df.reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="拷贝并划分 train.csv")
    parser.add_argument("--src", type=Path, default=DEFAULT_SRC)
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()

    cfg = load_config(args.config)
    data_cfg = cfg["data"]
    raw_path = resolve_path(data_cfg["raw_csv"])
    processed_dir = resolve_path(data_cfg["processed_dir"])
    category_col = data_cfg.get("category_col", "类别")

    src = args.src
    if not src.exists():
        raise FileNotFoundError(f"源文件不存在: {src}")

    raw_path.parent.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    print(f"[copy] {src} -> {raw_path}")
    shutil.copy2(src, raw_path)

    df = pd.read_csv(raw_path, encoding="utf-8-sig")
    if category_col not in df.columns:
        raise ValueError(f"缺少列 {category_col}，当前={list(df.columns)}")

    train_df, val_df, test_df = split_dataframe(
        df,
        category_col=category_col,
        val_ratio=float(data_cfg.get("val_ratio", 0.1)),
        test_ratio=float(data_cfg.get("test_ratio", 0.1)),
        seed=int(cfg["random_seed"]),
    )

    train_out = processed_dir / data_cfg.get("train_file", "train.csv")
    val_out = processed_dir / data_cfg.get("val_file", "val.csv")
    test_out = processed_dir / data_cfg.get("test_file", "test.csv")
    train_df.to_csv(train_out, index=False, encoding="utf-8-sig")
    val_df.to_csv(val_out, index=False, encoding="utf-8-sig")
    test_df.to_csv(test_out, index=False, encoding="utf-8-sig")

    print(f"[split] train={len(train_df)} -> {train_out}")
    print(f"[split] val={len(val_df)} -> {val_out}")
    print(f"[split] test={len(test_df)} -> {test_out}")
    print("[split] 列与原表一致，未另建宽表；训练脚本按需读 类别/评论内容_clean/attributes")


if __name__ == "__main__":
    main()
