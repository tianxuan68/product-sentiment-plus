"""
FastText 风格轻量模型：字符 n-gram HashingVectorizer + LogisticRegression

说明：Windows 环境常无法编译官方 fasttext，这里用等价的 char-ngram 线性模型，
接口与产出与其它模型一致（checkpoints + results）。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.linear_model import SGDClassifier
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "models"))

from common.dataset.load_reviews import load_xy  # noqa: E402
from common.metrics.evaluate import compute_metrics, save_metrics  # noqa: E402

CKPT = Path(__file__).resolve().parents[1] / "checkpoints" / "fasttext_style.joblib"
RESULT = Path(__file__).resolve().parents[1] / "results" / "metrics.json"


def build_pipeline() -> Pipeline:
    return Pipeline(
        steps=[
            (
                "hash",
                HashingVectorizer(
                    analyzer="char_wb",
                    ngram_range=(2, 5),
                    n_features=2**20,
                    alternate_sign=False,
                ),
            ),
            (
                "clf",
                SGDClassifier(
                    loss="log_loss",
                    penalty="l2",
                    alpha=1e-5,
                    max_iter=20,
                    class_weight="balanced",
                    random_state=42,
                    n_jobs=-1,
                ),
            ),
        ]
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-samples", type=int, default=None)
    args = parser.parse_args()

    print("=" * 50)
    print("FastText 风格训练 (char-ngram + SGD)")
    print("=" * 50)

    x_train, y_train, _ = load_xy("train")
    x_val, y_val, _ = load_xy("val")
    if args.max_samples:
        x_train, y_train = x_train[: args.max_samples], y_train[: args.max_samples]
        x_val, y_val = x_val[: max(args.max_samples // 5, 200)], y_val[: max(args.max_samples // 5, 200)]

    pipe = build_pipeline()
    print(f"训练中 train={len(x_train)} ...")
    pipe.fit(x_train, y_train)
    pred = pipe.predict(x_val)
    metrics = compute_metrics(y_val, pred)
    print(metrics["report"])

    CKPT.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipe, CKPT)
    save_metrics(
        metrics,
        RESULT,
        {"model": "fasttext_style_char_ngram", "train_size": len(x_train)},
    )
    print(f"模型: {CKPT}")


if __name__ == "__main__":
    main()
