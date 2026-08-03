"""
案例:
    总 BERT 测试 / 推理。

用法（在 product-sentiment-ai 目录下）:
    python -m models.bert.common.scripts.predict --eval-val
    python -m models.bert.common.scripts.predict --text "太差了，坏了没人管，别买"
    python -m models.bert.common.scripts.predict --predict-test
"""

# 导包
import argparse
import os

import torch
import torch.nn.functional as F
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from models.common.dataset.load_reviews import load_split, load_xy
from models.common.metrics.evaluate import compute_metrics, save_metrics


# 1. 定义函数, 加载模型
def load_model():
    ckpt_dir = "./models/bert/common/model/bert_all"
    if not os.path.exists(os.path.join(ckpt_dir, "config.json")):
        raise FileNotFoundError(
            f"缺少模型 {ckpt_dir}，请先训练:\n"
            "  python -m models.bert.common.scripts.train"
        )
    print(f'加载模型: {ckpt_dir}')
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    my_tokenizer = AutoTokenizer.from_pretrained(ckpt_dir, local_files_only=True)
    my_model = AutoModelForSequenceClassification.from_pretrained(
        ckpt_dir, local_files_only=True
    ).to(device)
    my_model.eval()

    # 读训练时保存的阈值（没有就用 0.5）
    thr_path = os.path.join(ckpt_dir, "threshold.txt")
    threshold = 0.5
    if os.path.exists(thr_path):
        with open(thr_path, "r", encoding="utf-8") as f:
            threshold = float(f.read().strip())
    print(f'device: {device} | threshold: {threshold}')
    return my_tokenizer, my_model, device, threshold


# 2. 定义函数, 批量预测
@torch.no_grad()
def predict_texts(my_tokenizer, my_model, device, texts, threshold=0.5, max_len=128, batch_size=32):
    preds, confs, p_negs, p_poss = [], [], [], []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        enc = my_tokenizer(
            batch,
            truncation=True,
            padding=True,
            max_length=max_len,
            return_tensors="pt",
        )
        enc = {k: v.to(device) for k, v in enc.items()}
        logits = my_model(**enc).logits
        probs = F.softmax(logits, dim=-1).cpu()
        p_neg = probs[:, 0]
        p_pos = probs[:, 1]
        # 按阈值判好评；阈值来自训练时的 threshold.txt
        pred = (p_pos >= threshold).long()
        conf = probs.max(dim=-1).values
        preds.extend(pred.tolist())
        confs.extend(conf.tolist())
        p_negs.extend(p_neg.tolist())
        p_poss.extend(p_pos.tolist())
    return preds, confs, p_negs, p_poss


# 3. 定义函数, 验证集评测
def eval_val(my_tokenizer, my_model, device, threshold):
    result_val = "./models/bert/common/results/metrics_eval.json"
    x_val, y_val, _ = load_xy("val")
    pred, _, _, _ = predict_texts(my_tokenizer, my_model, device, x_val, threshold)
    metrics = compute_metrics(y_val, pred)
    print('-' * 50)
    print(f'验证集评测（总 BERT）')
    print('-' * 50)
    print(metrics["report"])
    save_metrics(
        metrics,
        result_val,
        {"model": "bert_all", "train_size": "eval_only", "threshold": threshold},
    )


# 4. 定义函数, 单句预测
def predict_one(my_tokenizer, my_model, device, threshold, text):
    label_name = {0: "差评", 1: "好评"}
    pred, conf, p_neg, p_pos = predict_texts(
        my_tokenizer, my_model, device, [text], threshold
    )
    label = int(pred[0])
    print('-' * 50)
    print(f'单句预测（总 BERT）')
    print('-' * 50)
    print(f'文本: {text}')
    print(f'预测类别: {label}（{label_name[label]}）')
    print(f'P(差评)= {float(p_neg[0]):.4f}')
    print(f'P(好评)= {float(p_pos[0]):.4f}')
    print(f'置信度  = {float(conf[0]):.4f}')
    print(f'阈值    = {threshold:.2f}')


# 5. 定义函数, 官方测试集批量预测
def predict_test(my_tokenizer, my_model, device, threshold):
    out_test = "./models/bert/common/results/test_predictions.csv"
    label_name = {0: "差评", 1: "好评"}
    df = load_split("test")
    texts = df["sentence"].fillna("").astype(str).tolist()
    pred, conf, p_neg, p_pos = predict_texts(
        my_tokenizer, my_model, device, texts, threshold
    )
    out = df[["review_id", "product_id", "category", "sentence"]].copy()
    out["pred_sentiment"] = pred
    out["pred_label"] = out["pred_sentiment"].map(label_name)
    out["confidence"] = conf
    out["prob_neg"] = p_neg
    out["prob_pos"] = p_pos
    os.makedirs("./models/bert/common/results", exist_ok=True)
    out.to_csv(out_test, index=False, encoding="utf-8-sig")
    print('-' * 50)
    print(f'官方测试集预测完成（总 BERT）')
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

    my_tokenizer, my_model, device, threshold = load_model()

    if args.eval_val:
        eval_val(my_tokenizer, my_model, device, threshold)
    if args.text:
        predict_one(my_tokenizer, my_model, device, threshold, args.text)
    if args.predict_test:
        predict_test(my_tokenizer, my_model, device, threshold)


if __name__ == "__main__":
    # 1. 推理入口
    main()
