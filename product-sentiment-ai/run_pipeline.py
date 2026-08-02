"""
一键流水线：
  数据处理 → 动态打标 → 基线 → FastText → BERT → 蒸馏

用法：
  python run_pipeline.py --smoke          # 小样本冒烟
  python run_pipeline.py --full           # 完整训练
  python run_pipeline.py --full --skip-bert
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable


def run(cmd: list[str]) -> None:
    print("\n>>>", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def ensure_bert() -> None:
    sys.path.insert(0, str(ROOT / "models"))
    from common.pretrained_path import ensure_bert_pretrained

    path = ensure_bert_pretrained()
    print("BERT 权重就绪:", path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true", help="小样本冒烟")
    parser.add_argument("--full", action="store_true", help="完整训练")
    parser.add_argument("--skip-bert", action="store_true")
    parser.add_argument("--skip-distill", action="store_true")
    parser.add_argument("--skip-prepare", action="store_true")
    args = parser.parse_args()
    if not args.smoke and not args.full:
        args.smoke = True

    if not args.skip_prepare:
        run([PY, "data/scripts/preprocess/prepare_reviews.py"])
        run([PY, "data/scripts/preprocess/verify_processed.py"])
        run([PY, "data/scripts/annotate/dynamic_tagging.py"])

    if args.smoke:
        run([PY, "models/baseline/scripts/train.py", "--max-samples", "3000"])
        run([PY, "models/fasttext/scripts/train.py", "--max-samples", "3000"])
        if not args.skip_bert:
            ensure_bert()
            run(
                [
                    PY,
                    "models/bert/common/scripts/train.py",
                    "--max-samples",
                    "1500",
                    "--epochs",
                    "1",
                    "--batch-size",
                    "16",
                ]
            )
            run(
                [
                    PY,
                    "models/bert/category/scripts/train.py",
                    "--max-samples",
                    "1200",
                    "--epochs",
                    "1",
                    "--batch-size",
                    "16",
                    "--top-n-categories",
                    "3",
                ]
            )
            if not args.skip_distill:
                run(
                    [
                        PY,
                        "models/bert/distill/scripts/train.py",
                        "--max-samples",
                        "1500",
                        "--epochs",
                        "2",
                        "--batch-size",
                        "16",
                    ]
                )
    else:
        run([PY, "models/baseline/scripts/train.py"])
        run([PY, "models/fasttext/scripts/train.py"])
        if not args.skip_bert:
            ensure_bert()
            run([PY, "models/bert/common/scripts/train.py", "--epochs", "2"])
            run(
                [
                    PY,
                    "models/bert/category/scripts/train.py",
                    "--epochs",
                    "2",
                    "--top-n-categories",
                    "3",
                ]
            )
            if not args.skip_distill:
                run(
                    [
                        PY,
                        "models/bert/distill/scripts/train.py",
                        "--epochs",
                        "3",
                    ]
                )

    run([PY, "models/common/scripts/compare_results.py"])
    print("\n流水线完成。")
    print("对比表: models/common/results/model_compare.csv")
    print("商品标签墙: data/processed/product_tags.csv")


if __name__ == "__main__":
    main()
