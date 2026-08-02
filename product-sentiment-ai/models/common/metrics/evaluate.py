"""共用分类评测。"""

from __future__ import annotations

import json
from pathlib import Path

from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
)


def compute_metrics(y_true, y_pred) -> dict:
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, average="binary", zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, average="binary", zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, average="binary", zero_division=0)),
        "report": classification_report(
            y_true, y_pred, digits=4, zero_division=0
        ),
    }


def save_metrics(metrics: dict, path: Path, extra: dict | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {k: v for k, v in metrics.items() if k != "report"}
    if extra:
        payload.update(extra)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    report_path = path.with_suffix(".report.txt")
    report_path.write_text(metrics.get("report", ""), encoding="utf-8")
    print(f"指标已保存: {path}")
    print(f"accuracy={payload['accuracy']:.4f} f1={payload['f1']:.4f}")
