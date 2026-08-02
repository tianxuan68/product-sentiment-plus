"""
基线：jieba 分词 + TF-IDF + LogisticRegression
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import jieba
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "models"))

from common.dataset.load_reviews import load_xy  # noqa: E402
from common.metrics.evaluate import compute_metrics, save_metrics  # noqa: E402

CKPT = Path(__file__).resolve().parents[1] / "checkpoints" / "baseline.joblib"
RESULT = Path(__file__).resolve().parents[1] / "results" / "metrics.json"


def tokenize(text: str) -> str:
    return " ".join(jieba.lcut(text))


def build_pipeline() -> Pipeline:
    return Pipeline(
        steps=[
            (
                "tfidf",
                TfidfVectorizer(
                    max_features=50000,
                    ngram_range=(1, 2),
                    min_df=2,
                ),
            ),
            (
                "clf",
                LogisticRegression(
                    max_iter=1000,
                    class_weight="balanced",
                    random_state=42,
                ),
            ),
        ]
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-samples", type=int, default=None)
    args = parser.parse_args()

    print("=" * 50)
    print("基线训练 TF-IDF + LR")
    print("=" * 50)

    x_train, y_train, _ = load_xy("train")
    x_val, y_val, _ = load_xy("val")
    if args.max_samples:
        x_train, y_train = x_train[: args.max_samples], y_train[: args.max_samples]
        x_val, y_val = x_val[: max(args.max_samples // 5, 200)], y_val[: max(args.max_samples // 5, 200)]
        print(f"调试样本: train={len(x_train)} val={len(x_val)}")

    print("分词中...")
    x_train_tok = [tokenize(t) for t in x_train]
    x_val_tok = [tokenize(t) for t in x_val]

    pipe = build_pipeline()
    print("训练中...")
    pipe.fit(x_train_tok, y_train)

    pred = pipe.predict(x_val_tok)
    metrics = compute_metrics(y_val, pred)
    print(metrics["report"])

    CKPT.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipe, CKPT)
    save_metrics(metrics, RESULT, {"model": "baseline_tfidf_lr", "train_size": len(x_train)})
    print(f"模型: {CKPT}")


if __name__ == "__main__":
    main()
