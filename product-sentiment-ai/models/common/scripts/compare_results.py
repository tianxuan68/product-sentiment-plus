"""汇总各模型 results/metrics.json，写出对比表。"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "common" / "results" / "model_compare.csv"

CANDIDATES = [
    ROOT / "baseline" / "results" / "metrics.json",
    ROOT / "fasttext" / "results" / "metrics.json",
    ROOT / "bert" / "common" / "results" / "metrics.json",
    ROOT / "bert" / "category" / "results" / "metrics.json",
    ROOT / "bert" / "distill" / "results" / "metrics.json",
]


def main():
    rows = []
    for path in CANDIDATES:
        if not path.exists():
            print("跳过(无文件):", path)
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        rows.append(
            {
                "model": data.get("model", path.parent.parent.name),
                "accuracy": data.get("accuracy"),
                "precision": data.get("precision"),
                "recall": data.get("recall"),
                "f1": data.get("f1"),
                "train_size": data.get("train_size"),
                "path": str(path),
            }
        )
    if not rows:
        raise SystemExit("没有任何模型指标，请先训练")

    df = pd.DataFrame(rows).sort_values("f1", ascending=False)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False, encoding="utf-8-sig")
    print("=" * 50)
    print("模型对比")
    print("=" * 50)
    print(df.to_string(index=False))
    print("已保存:", OUT)


if __name__ == "__main__":
    main()
