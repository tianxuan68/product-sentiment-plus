"""
案例:
    多标签评测：micro/macro P/R/F1。
"""

# 导包
from sklearn.metrics import classification_report, f1_score, precision_score, recall_score


# 1. 定义函数, 多标签指标
def compute_multilabel_metrics(y_true, y_pred, label_names=None):
    return {
        "precision_micro": float(
            precision_score(y_true, y_pred, average="micro", zero_division=0)
        ),
        "recall_micro": float(
            recall_score(y_true, y_pred, average="micro", zero_division=0)
        ),
        "f1_micro": float(f1_score(y_true, y_pred, average="micro", zero_division=0)),
        "precision_macro": float(
            precision_score(y_true, y_pred, average="macro", zero_division=0)
        ),
        "recall_macro": float(
            recall_score(y_true, y_pred, average="macro", zero_division=0)
        ),
        "f1_macro": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        # 兼容 compare / save_metrics 里常用的字段名
        "precision": float(
            precision_score(y_true, y_pred, average="micro", zero_division=0)
        ),
        "recall": float(recall_score(y_true, y_pred, average="micro", zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, average="micro", zero_division=0)),
        "accuracy": float(
            # 子集准确率：整条样本标签完全一致才算对
            (y_true == y_pred).all(axis=1).mean() if hasattr(y_true, "shape") else 0.0
        ),
        "report": classification_report(
            y_true,
            y_pred,
            target_names=label_names,
            digits=4,
            zero_division=0,
        ),
    }
