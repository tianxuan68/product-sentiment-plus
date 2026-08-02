"""
案例:
    情感预测业务：加载模型 + 推理。

大白话:
    基线要先 jieba 分词；FastText 风格直接吃原文；BERT/蒸馏走 transformers。
"""

# 导包
import os
from functools import lru_cache

import joblib
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer


# 1. 定义函数, sklearn 管线预测（baseline / fasttext）
def _predict_sklearn(pipe, text, model_name):
    label_name = {0: "差评", 1: "好评"}
    pred = int(pipe.predict([text])[0])
    out = {
        "text": text,
        "pred": pred,
        "label": label_name.get(pred, str(pred)),
        "model": model_name,
        "prob_neg": None,
        "prob_pos": None,
        "confidence": None,
    }
    if hasattr(pipe, "predict_proba"):
        proba = pipe.predict_proba([text])[0]
        classes = list(pipe.classes_)
        mapping = {int(c): float(p) for c, p in zip(classes, proba)}
        out["prob_neg"] = mapping.get(0)
        out["prob_pos"] = mapping.get(1)
        out["confidence"] = float(max(proba))
    return out


# 2. 定义函数, 加载模型（lru_cache: 同一进程只加载一次）
@lru_cache(maxsize=1)
def _load_baseline():
    ckpt = "./models/baseline/model/baseline.joblib"
    if not os.path.exists(ckpt):
        raise FileNotFoundError(f"缺少基线模型: {ckpt}，请先训练")
    print(f'加载基线模型: {ckpt}')
    return joblib.load(ckpt)


@lru_cache(maxsize=1)
def _load_fasttext():
    ckpt = "./models/fasttext/model/fasttext_style.joblib"
    if not os.path.exists(ckpt):
        raise FileNotFoundError(f"缺少 FastText 模型: {ckpt}，请先训练")
    print(f'加载 FastText 模型: {ckpt}')
    return joblib.load(ckpt)


@lru_cache(maxsize=2)
def _load_bert_bundle(model_dir):
    print(f'加载 BERT 目录: {model_dir}')
    tok = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(
        model_dir, local_files_only=True
    )
    model.eval()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    print(f'BERT device: {device}')
    return tok, model, device


# 3. 定义函数, BERT / 蒸馏学生预测
def _predict_bert(text, model_dir, model_name):
    label_name = {0: "差评", 1: "好评"}
    if not os.path.exists(model_dir):
        raise FileNotFoundError(f"缺少模型目录: {model_dir}，请先训练")
    tok, model, device = _load_bert_bundle(model_dir)
    enc = tok(
        text,
        truncation=True,
        padding=True,
        max_length=128,
        return_tensors="pt",
    )
    enc = {k: v.to(device) for k, v in enc.items()}
    with torch.no_grad():
        logits = model(**enc).logits[0]
        probs = torch.softmax(logits, dim=-1).detach().cpu().tolist()
    pred = int(logits.argmax().item())
    return {
        "text": text,
        "pred": pred,
        "label": label_name.get(pred, str(pred)),
        "model": model_name,
        "prob_neg": float(probs[0]),
        "prob_pos": float(probs[1]),
        "confidence": float(max(probs)),
    }


# 4. 定义函数, 对外：单句预测
def predict_one(text, model="fasttext"):
    model = model.strip().lower()
    text = (text or "").strip()
    if not text:
        raise ValueError("text 不能为空")

    print(f'预测模型={model} 文本={text[:40]}...')

    if model == "baseline":
        import jieba
        tok_text = " ".join(jieba.lcut(text))
        return _predict_sklearn(_load_baseline(), tok_text, "baseline")

    if model == "fasttext":
        return _predict_sklearn(_load_fasttext(), text, "fasttext")

    if model == "bert":
        return _predict_bert(text, "./models/bert/common/model/bert_all", "bert")

    if model == "distill":
        return _predict_bert(text, "./models/bert/distill/model/bert_student", "distill")

    raise ValueError("model 只能是: baseline | fasttext | bert | distill")


# 5. 定义函数, 批量预测
def predict_batch(texts, model="fasttext"):
    return [predict_one(t, model=model) for t in texts]


# 6. 定义函数, 训练完刷新缓存
def clear_model_cache():
    _load_baseline.cache_clear()
    _load_fasttext.cache_clear()
    _load_bert_bundle.cache_clear()
    print(f'预测模型缓存已清空')
