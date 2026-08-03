"""
案例:
    机器学习基线：jieba 分词 + TF-IDF + LogisticRegression。

用法（在 product-sentiment-ai 目录下）:
    python -m models.baseline.scripts.train
"""

# 导包
import argparse
import os

import jieba                                                           # 中文分词
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from models.common.dataset.load_reviews import load_xy
from models.common.metrics.evaluate import compute_metrics, save_metrics


# 1. 定义函数, 分词
def tokenize(text):
    return " ".join(jieba.lcut(text))


# 2. 定义函数, 构建流水线
def build_pipeline():
    return Pipeline(
        steps=[
            (
                "tfidf",
                TfidfVectorizer(
                    max_features=50000,          # 参1: 词表上限
                    ngram_range=(1, 2),          # 参2: 1~2 元词
                    min_df=2,                    # 参3: 至少出现 2 次
                ),
            ),
            (
                "clf",
                LogisticRegression(
                    max_iter=1000,
                    class_weight="balanced",     # 参2: 类别不平衡
                    random_state=42,
                ),
            ),
        ]
    )


# 3. 定义函数, 主流程
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-samples", type=int, default=None)
    args = parser.parse_args()

    # 保存路径写在函数里
    ckpt = "./models/baseline/model/baseline.joblib"
    result = "./models/baseline/results/metrics.json"

    print('-' * 50)
    print(f'基线训练 TF-IDF + LR')
    print('-' * 50)

    # 3.1 加载
    x_train, y_train, _ = load_xy("train")
    x_val, y_val, _ = load_xy("val")
    if args.max_samples:
        x_train, y_train = x_train[: args.max_samples], y_train[: args.max_samples]
        n_val = max(args.max_samples // 5, 200)
        x_val, y_val = x_val[:n_val], y_val[:n_val]
        print(f'调试样本: train={len(x_train)} val={len(x_val)}')

    # 3.2 分词
    print(f'分词中...')
    x_train_tok = [tokenize(t) for t in x_train]
    x_val_tok = [tokenize(t) for t in x_val]

    # 3.3 训练
    estimator = build_pipeline()
    print(f'训练中...')
    estimator.fit(x_train_tok, y_train)

    # 3.4 评估
    y_pre = estimator.predict(x_val_tok)
    metrics = compute_metrics(y_val, y_pre)
    print(metrics["report"])

    # 3.5 保存
    os.makedirs("./models/baseline/model", exist_ok=True)
    joblib.dump(estimator, ckpt)
    save_metrics(metrics, result, {"model": "baseline_tfidf_lr", "train_size": len(x_train)})
    print(f'模型已保存: {ckpt}')


if __name__ == "__main__":
    # 1. 训练基线
    main()
