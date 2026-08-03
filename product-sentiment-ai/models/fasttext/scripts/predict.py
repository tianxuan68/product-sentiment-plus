"""
案例:
    FastText 风格模型测试 / 推理。

用法（在 product-sentiment-ai 目录下）:
    python -m models.fasttext.scripts.predict --eval-val
    python -m models.fasttext.scripts.predict --text "质量很好，发货也快"
"""

# 导包
import argparse
import os

import joblib

from models.common.dataset.load_reviews import load_split, load_xy
from models.common.metrics.evaluate import compute_metrics, save_metrics


# 1. 定义函数, 加载模型
def load_model():
    ckpt = "./models/fasttext/model/fasttext_style.joblib"
    if not os.path.exists(ckpt):
        raise FileNotFoundError(f"缺少模型 {ckpt}，请先运行 train")
    print(f'加载模型: {ckpt}')
    return joblib.load(ckpt)


# 2. 定义函数, 批量预测（返回类别、置信度、两类概率）
def predict_texts(pipe, texts):
    pred = pipe.predict(texts)
    classes = list(pipe.classes_)
    if hasattr(pipe, "predict_proba"):
        proba = pipe.predict_proba(texts)
        p_neg = proba[:, classes.index(0)] if 0 in classes else None
        p_pos = proba[:, classes.index(1)] if 1 in classes else None
        conf = proba.max(axis=1)
    else:
        p_neg = p_pos = None
        conf = [None] * len(texts)
    return pred, conf, p_neg, p_pos


# 3. 定义函数, 验证集评测
def eval_val(pipe):
    result_val = "./models/fasttext/results/metrics_eval.json"
    x_val, y_val, _ = load_xy("val")
    pred, _, _, _ = predict_texts(pipe, x_val)
    metrics = compute_metrics(y_val, pred)
    print('-' * 50)
    print(f'验证集评测')
    print('-' * 50)
    print(metrics["report"])
    save_metrics(
        metrics,
        result_val,
        {"model": "fasttext_style_char_ngram", "train_size": "eval_only"},
    )


# 4. 定义函数, 单句预测
def predict_one(pipe, text):
    label_name = {0: "差评", 1: "好评"}
    pred, conf, p_neg, p_pos = predict_texts(pipe, [text])
    label = int(pred[0])
    print('-' * 50)
    print(f'单句预测')
    print('-' * 50)
    print(f'文本: {text}')
    print(f'预测类别: {label}（{label_name[label]}）')
    if p_neg is not None and p_pos is not None:
        print(f'P(差评)= {float(p_neg[0]):.4f}')
        print(f'P(好评)= {float(p_pos[0]):.4f}')
        print(f'置信度  = {float(conf[0]):.4f}')
    print(f'说明: 置信度=模型认为当前预测有多稳，不是数据集好评率')


# 5. 定义函数, 官方测试集批量预测
def predict_test(pipe):
    out_test = "./models/fasttext/results/test_predictions.csv"
    label_name = {0: "差评", 1: "好评"}
    df = load_split("test")
    texts = df["sentence"].fillna("").astype(str).tolist()
    pred, conf, p_neg, p_pos = predict_texts(pipe, texts)
    out = df[["review_id", "product_id", "category", "sentence"]].copy()
    out["pred_sentiment"] = pred
    out["pred_label"] = out["pred_sentiment"].map(label_name)
    if conf[0] is not None:
        out["confidence"] = conf
        out["prob_neg"] = p_neg
        out["prob_pos"] = p_pos
    os.makedirs("./models/fasttext/results", exist_ok=True)
    out.to_csv(out_test, index=False, encoding="utf-8-sig")
    print('-' * 50)
    print(f'官方测试集预测完成')
    print('-' * 50)
    print(f'条数: {len(out)}')
    print(out["pred_label"].value_counts().to_string())
    print(f'已保存: {out_test}')


# 6. 主入口
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--eval-val", action="store_true", help="在验证集上评测")
    parser.add_argument("--text", type=str, default=None, help="单句预测")
    parser.add_argument("--predict-test", action="store_true", help="预测官方测试集")
    args = parser.parse_args()

    if not (args.eval_val or args.text or args.predict_test):
        args.eval_val = True
        print(f'未指定模式，默认 --eval-val')

    pipe = load_model()

    if args.eval_val:
        eval_val(pipe)
    if args.text:
        predict_one(pipe, args.text)
    if args.predict_test:
        predict_test(pipe)


if __name__ == "__main__":
    # 1. 推理入口
    main()
