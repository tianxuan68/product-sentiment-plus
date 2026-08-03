"""
案例:
    一键预测几条演示评论（情绪 + 关键词，对齐 Insight 页字段）

用法（在 product-sentiment-ai 目录）:
    python scripts/predict_demo.py
"""

# 导包
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# 必须先切到 AI 根目录：下游大量 "./models/..." 相对路径依赖 cwd
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.services.front_predict_service import predict_for_front  # noqa: E402

# 演示数据（可直接改这里）
SAMPLES = [
    {
        "content": "质量很好，发货很快，很满意，会回购",
        "product": {"name": "澄见智能水杯", "category": "生活用品", "rating": "5", "note": ""},
    },
    {
        "content": "包装破损，物流太慢，质量差，非常后悔，不推荐购买",
        "product": {"name": "某品牌耳机", "category": "电子产品", "rating": "1", "note": ""},
    },
    {
        "content": "一般般吧，还行，没什么特别的感觉",
        "product": {"name": "基础款T恤", "category": "其他", "rating": "3", "note": ""},
    },
    {
        "content": "面料舒服，版型好看，就是有点贵",
        "product": {"name": "夏季连衣裙", "category": "其他", "rating": "4", "note": ""},
    },
    {
        "content": "假货吧，用两天就坏了，客服也不理人",
        "product": {"name": "蓝牙音箱", "category": "电子产品", "rating": "1", "note": ""},
    },
]


def main() -> None:
    rows = []
    for i, sample in enumerate(SAMPLES, 1):
        out = predict_for_front(
            content=sample["content"],
            product=sample.get("product"),
        )
        row = {"id": i, "content": sample["content"], **out}
        rows.append(row)
        print(
            f"[{i}] {out['sentiment']:8} {out['score']:3}%  "
            f"keywords={out['keywords'][:6]}  | {sample['content'][:28]}"
        )
        print(f"    summary: {out['summary']}")

    out_path = ROOT / "models" / "bert" / "common" / "results" / "demo_predictions.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已写入: {out_path}")


if __name__ == "__main__":
    main()
