"""
案例:
    多标签打标模型：字符 n-gram + OneVsRest，缓解规则 OOV。

大白话:
    银标仍来自规则明细，但特征按「字片」切，能认「质量很好」这类近义说法。
    推理时再和规则取并集，精确命中 + 语义泛化一起上。

用法（在 product-sentiment-ai 目录下）:
    python -m models.tagging.scripts.train
    python -m models.tagging.scripts.train --max-samples 8000
"""

# 导包
import argparse
import os

import joblib
import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.linear_model import SGDClassifier
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import MultiLabelBinarizer

from models.common.dataset.load_multilabel_tags import (
    all_tag_names,
    load_multilabel,
    tag_meta_map,
)
from models.common.metrics.evaluate import save_metrics
from models.common.metrics.evaluate_multilabel import compute_multilabel_metrics


# 1. 构建流水线：char n-gram 是扛 OOV 的关键
def build_pipeline():
    return Pipeline(
        steps=[
            (
                "hash",
                HashingVectorizer(
                    analyzer="char_wb",       # 参1: 按字符窗口，不依赖分词词表
                    ngram_range=(2, 5),       # 参2: 2~5 元字片，「质量很好」能蹭到「质量好」
                    n_features=2**18,
                    alternate_sign=False,
                ),
            ),
            (
                "clf",
                OneVsRestClassifier(
                    SGDClassifier(
                        loss="log_loss",
                        penalty="l2",
                        alpha=1e-5,
                        max_iter=40,
                        class_weight="balanced",
                        random_state=42,
                    ),
                    n_jobs=-1,
                ),
            ),
        ]
    )


# 2. 主流程
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-samples", type=int, default=None)
    parser.add_argument("--threshold", type=float, default=0.28, help="概率阈值，略低换召回/抗 OOV")
    parser.add_argument("--no-augment", action="store_true", help="关掉近义改写")
    args = parser.parse_args()

    ckpt = "./models/tagging/model/tagging_multilabel.joblib"
    result = "./models/tagging/results/metrics.json"

    print('-' * 50)
    print(f'多标签打标训练 (char-ngram + OneVsRest)')
    print('-' * 50)

    # 2.1 数据
    x_train, y_train_lists, _ = load_multilabel(
        "train", max_samples=args.max_samples, augment=not args.no_augment
    )
    x_val, y_val_lists, _ = load_multilabel(
        "val",
        max_samples=(max(args.max_samples // 5, 200) if args.max_samples else None),
        augment=False,
    )

    classes = all_tag_names()
    mlb = MultiLabelBinarizer(classes=classes)
    y_train = mlb.fit_transform(y_train_lists)
    y_val = mlb.transform(y_val_lists)
    print(f'标签维数: {len(classes)} | 训练正例密度={y_train.mean():.4f}')

    # 2.2 训练
    pipe = build_pipeline()
    print(f'训练中 train={len(x_train)} ...')
    pipe.fit(x_train, y_train)

    # 2.3 评估（概率阈值）
    if hasattr(pipe, "predict_proba"):
        proba = pipe.predict_proba(x_val)
        y_pre = (np.asarray(proba) >= args.threshold).astype(int)
    else:
        y_pre = pipe.predict(x_val)

    metrics = compute_multilabel_metrics(y_val, y_pre, label_names=list(mlb.classes_))
    print(metrics["report"])

    # 2.4 保存
    os.makedirs("./models/tagging/model", exist_ok=True)
    bundle = {
        "pipe": pipe,
        "mlb": mlb,
        "threshold": args.threshold,
        "tag_meta": tag_meta_map(),
        "classes": list(mlb.classes_),
    }
    joblib.dump(bundle, ckpt)
    save_metrics(
        metrics,
        result,
        {
            "model": "tagging_multilabel_char_ngram",
            "train_size": len(x_train),
            "threshold": args.threshold,
            "n_labels": len(classes),
        },
    )
    print(f'模型已保存: {ckpt}')


if __name__ == "__main__":
    main()
