"""
案例:
    共用分类评测：accuracy / precision / recall / f1。
"""

# 导包
import json
import os

from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
)


# 1. 定义函数, 算指标
def compute_metrics(y_true, y_pred):
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, average="binary", zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, average="binary", zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, average="binary", zero_division=0)),
        "report": classification_report(
            y_true, y_pred, digits=4, zero_division=0
        ),
    }


# 2. 定义函数, 保存指标到 json
def save_metrics(metrics, path, extra=None):
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)

    payload = {k: v for k, v in metrics.items() if k != "report"}
    if extra:
        payload.update(extra)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    report_path = path.replace(".json", ".report.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(metrics.get("report", ""))

    print(f'指标已保存: {path}')
    print(f'accuracy={payload["accuracy"]:.4f} f1={payload["f1"]:.4f}')
