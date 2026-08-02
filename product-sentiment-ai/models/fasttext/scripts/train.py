"""
案例:
    FastText 风格轻量情感分类（字符 n-gram + SGD）。

用法（在 product-sentiment-ai 目录下）:
    python -m models.fasttext.scripts.train
"""

# 导包
import argparse
import os

import joblib                                                         # 模型落盘
from sklearn.feature_extraction.text import HashingVectorizer         # 字符 n-gram
from sklearn.linear_model import SGDClassifier                        # 线性分类器
from sklearn.pipeline import Pipeline

from models.common.dataset.load_reviews import load_xy
from models.common.metrics.evaluate import compute_metrics, save_metrics


# 1. 定义函数, 构建流水线
def build_pipeline():
    return Pipeline(
        steps=[
            (
                "hash",
                HashingVectorizer(
                    analyzer="char_wb",          # 参1: 按字符窗口
                    ngram_range=(2, 5),          # 参2: 2~5 元字符
                    n_features=2**20,            # 参3: 哈希桶大小
                    alternate_sign=False,
                ),
            ),
            (
                "clf",
                SGDClassifier(
                    loss="log_loss",             # 参1: 逻辑回归损失，可出概率
                    penalty="l2",
                    alpha=1e-5,
                    max_iter=20,
                    class_weight="balanced",     # 参5: 好评多，给差评更高权重
                    random_state=42,
                    n_jobs=-1,
                ),
            ),
        ]
    )


# 2. 定义函数, 主流程
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-samples", type=int, default=None)
    args = parser.parse_args()

    ckpt = "./models/fasttext/model/fasttext_style.joblib"
    result = "./models/fasttext/results/metrics.json"

    print('-' * 50)
    print(f'FastText 风格训练 (char-ngram + SGD)')
    print('-' * 50)

    # 2.1 加载数据
    x_train, y_train, _ = load_xy("train")
    x_val, y_val, _ = load_xy("val")
    if args.max_samples:
        x_train, y_train = x_train[: args.max_samples], y_train[: args.max_samples]
        n_val = max(args.max_samples // 5, 200)
        x_val, y_val = x_val[:n_val], y_val[:n_val]
        print(f'调试样本: train={len(x_train)} val={len(x_val)}')

    # 2.2 训练
    pipe = build_pipeline()
    print(f'训练中 train={len(x_train)} ...')
    pipe.fit(x_train, y_train)

    # 2.3 评估
    y_pre = pipe.predict(x_val)
    metrics = compute_metrics(y_val, y_pre)
    print(metrics["report"])

    # 2.4 保存
    os.makedirs("./models/fasttext/model", exist_ok=True)
    joblib.dump(pipe, ckpt)
    save_metrics(
        metrics,
        result,
        {"model": "fasttext_style_char_ngram", "train_size": len(x_train)},
    )
    print(f'模型已保存: {ckpt}')


if __name__ == "__main__":
    # 1. 训练 FastText 风格模型
    main()
