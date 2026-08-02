"""
案例:
    多标签：按每个标签单独搜最优阈值（抬精确率用）。

大白话:
    全局 0.35 一刀切太粗；「会回购」该严一点，「发货快」可松一点。
"""

# 导包
import numpy as np
from sklearn.metrics import f1_score


def tune_label_thresholds(
    probs,
    y_true,
    thr_min=0.20,
    thr_max=0.85,
    step=0.02,
    default=0.40,
):
    """
    对每个标签在验证集上搜使该标签 F1 最大的阈值。
    返回 shape=(n_labels,) 的 float 数组。
    """
    probs = np.asarray(probs, dtype=np.float64)
    y_true = np.asarray(y_true, dtype=np.int32)
    n_labels = probs.shape[1]
    out = np.full(n_labels, float(default), dtype=np.float64)
    grid = np.arange(thr_min, thr_max + 1e-9, step)

    for j in range(n_labels):
        yj = y_true[:, j]
        if int(yj.sum()) == 0:
            out[j] = float(default)
            continue
        best_f1, best_thr = -1.0, float(default)
        pj = probs[:, j]
        for thr in grid:
            pred = (pj >= thr).astype(np.int32)
            f1 = float(f1_score(yj, pred, zero_division=0))
            if f1 > best_f1:
                best_f1, best_thr = f1, float(thr)
        out[j] = best_thr
    return out


def thresholds_to_dict(label_names, thr_arr):
    return {str(n): float(t) for n, t in zip(label_names, thr_arr)}


def dict_to_threshold_array(label_names, thr_dict, default=0.40):
    thr_dict = thr_dict or {}
    return np.array(
        [float(thr_dict.get(str(n), default)) for n in label_names],
        dtype=np.float64,
    )


def apply_thresholds(probs, thr):
    """thr 可以是标量，或与标签维对齐的向量/列表。"""
    probs = np.asarray(probs)
    if np.isscalar(thr):
        return (probs >= float(thr)).astype(np.int32)
    thr_arr = np.asarray(thr, dtype=np.float64)
    if thr_arr.ndim == 0:
        return (probs >= float(thr_arr)).astype(np.int32)
    return (probs >= thr_arr.reshape(1, -1)).astype(np.int32)


def score_with_thresholds(probs, y_true, thr):
    pred = apply_thresholds(probs, thr)
    return float(f1_score(y_true, pred, average="micro", zero_division=0))
