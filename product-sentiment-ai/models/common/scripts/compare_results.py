"""
案例:
    汇总各模型 results/metrics.json，写出对比表。

用法（在 product-sentiment-ai 目录下）:
    python -m models.common.scripts.compare_results
"""

# 导包
import json
import os

import pandas as pd


# 1. 定义函数, 汇总对比
def main():
    out = "./models/common/results/model_compare.csv"
    candidates = [
        "./models/baseline/results/metrics.json",
        "./models/fasttext/results/metrics.json",
        "./models/bert/common/results/metrics.json",
        "./models/bert/category/results/metrics.json",
        "./models/bert/distill/results/metrics.json",
        "./models/tagging/results/metrics.json",
        "./models/tagging/results/metrics_bert.json",
        "./models/tagging/results/metrics_hierarchical.json",
    ]

    rows = []
    for path in candidates:
        if not os.path.exists(path):
            print(f'跳过(无文件): {path}')
            continue
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        rows.append(
            {
                "model": data.get("model", path),
                "accuracy": data.get("accuracy"),
                "precision": data.get("precision"),
                "recall": data.get("recall"),
                "f1": data.get("f1"),
                "train_size": data.get("train_size"),
                "path": path,
            }
        )
    if not rows:
        raise SystemExit("没有任何模型指标，请先训练")

    df = pd.DataFrame(rows).sort_values("f1", ascending=False)
    os.makedirs("./models/common/results", exist_ok=True)
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print('-' * 50)
    print(f'模型对比')
    print('-' * 50)
    print(df.to_string(index=False))
    print(f'已保存: {out}')


if __name__ == "__main__":
    # 1. 对比各模型指标
    main()
