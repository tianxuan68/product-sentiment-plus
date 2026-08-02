"""
FastText 风格模型测试 / 推理。

用法：
  # 验证集评测
  python predict.py --eval-val

  # 单句
  python predict.py --text "质量很好，发货也快"

  # 官方测试集批量预测
  python predict.py --predict-test
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "models"))

from common.dataset.load_reviews import load_split, load_xy  # noqa: E402
from common.metrics.evaluate import compute_metrics, save_metrics  # noqa: E402

CKPT = Path(__file__).resolve().parents[1] / "checkpoints" / "fasttext_style.joblib"
OUT_TEST = Path(__file__).resolve().parents[1] / "results" / "test_predictions.csv"
# 与 train.py 的 metrics.json 分开，避免评测覆盖训练指标
RESULT_VAL = Path(__file__).resolve().parents[1] / "results" / "metrics_eval.json"

LABEL_NAME = {0: "差评", 1: "好评"}


def load_model():
    if not CKPT.exists():
        raise FileNotFoundError(f"缺少模型 {CKPT}，请先运行 train.py")
    return joblib.load(CKPT)


def predict_texts(pipe, texts: list[str]):
    pred = pipe.predict(texts)
    classes = list(pipe.classes_)
    if hasattr(pipe, "predict_proba"):
        proba = pipe.predict_proba(texts)
        # 按类别列对齐：P(差评), P(好评)
        p_neg = proba[:, classes.index(0)] if 0 in classes else None
        p_pos = proba[:, classes.index(1)] if 1 in classes else None
        conf = proba.max(axis=1)
    else:
        p_neg = p_pos = None
        conf = [None] * len(texts)
    return pred, conf, p_neg, p_pos


def eval_val(pipe) -> None:
    x_val, y_val, _ = load_xy("val")
    pred, _, _, _ = predict_texts(pipe, x_val)
    metrics = compute_metrics(y_val, pred)
    print("=" * 50)
    print("验证集评测")
    print("=" * 50)
    print(metrics["report"])
    save_metrics(
        metrics,
        RESULT_VAL,
        {"model": "fasttext_style_char_ngram", "train_size": "eval_only"},
    )


def predict_one(pipe, text: str) -> None:
    pred, conf, p_neg, p_pos = predict_texts(pipe, [text])
    label = int(pred[0])
    print("=" * 50)
    print("单句预测")
    print("=" * 50)
    print(f"文本: {text}")
    print(f"预测类别: {label}（{LABEL_NAME[label]}）")
    if p_neg is not None and p_pos is not None:
        print(f"P(差评)= {float(p_neg[0]):.4f}")
        print(f"P(好评)= {float(p_pos[0]):.4f}")
        print(f"置信度  = {float(conf[0]):.4f}  ← 取两类中较大的那个，不是数据集好评率")
    print("说明: 置信度=模型认为当前预测有多稳；训练时用了 class_weight=balanced，")
    print("      会压一点多数类(好评)概率，所以清晰好评也可能在 0.8~0.9，不代表判错。")


def predict_test(pipe) -> None:
    df = load_split("test")
    texts = df["sentence"].fillna("").astype(str).tolist()
    pred, conf, p_neg, p_pos = predict_texts(pipe, texts)
    out = df[["review_id", "product_id", "category", "sentence"]].copy()
    out["pred_sentiment"] = pred
    out["pred_label"] = out["pred_sentiment"].map(LABEL_NAME)
    if conf[0] is not None:
        out["confidence"] = conf
        out["prob_neg"] = p_neg
        out["prob_pos"] = p_pos
    OUT_TEST.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_TEST, index=False, encoding="utf-8-sig")
    print("=" * 50)
    print("官方测试集预测完成")
    print("=" * 50)
    print(f"条数: {len(out)}")
    print(out["pred_label"].value_counts().to_string())
    print(f"已保存: {OUT_TEST}")
    print("样例:")
    cols = ["review_id", "pred_label", "prob_pos", "sentence"]
    print(out[cols].head(5).to_string(index=False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval-val", action="store_true", help="在验证集上评测")
    parser.add_argument("--text", type=str, default=None, help="单句预测")
    parser.add_argument("--predict-test", action="store_true", help="预测官方测试集")
    args = parser.parse_args()

    if not (args.eval_val or args.text or args.predict_test):
        args.eval_val = True
        print("未指定模式，默认 --eval-val")

    pipe = load_model()
    print(f"已加载: {CKPT}")

    if args.eval_val:
        eval_val(pipe)
    if args.text:
        predict_one(pipe, args.text)
    if args.predict_test:
        predict_test(pipe)


if __name__ == "__main__":
    main()
