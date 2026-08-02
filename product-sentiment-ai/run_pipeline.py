"""
案例:
    一键流水线：数据处理 → 动态打标 → 基线 → FastText → BERT → 蒸馏。

用法（在 product-sentiment-ai 目录下）:
    python run_pipeline.py --smoke
    python run_pipeline.py --full
"""

# 导包
import argparse
import subprocess
import sys

from models.common.pretrained_path import ensure_bert_pretrained

PY = sys.executable


# 1. 定义函数, 跑子进程
def run(cmd):
    print(f'\n>>> {" ".join(cmd)}')
    subprocess.run(cmd, check=True)


# 2. 定义函数, 确保本地 BERT 权重就绪
def ensure_bert():
    path = ensure_bert_pretrained()
    print(f'BERT 权重就绪: {path}')


# 3. 定义函数, 主流程
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

    # 3.1 数据准备 + 打标
    if not args.skip_prepare:
        run([PY, "data/scripts/preprocess/prepare_reviews.py"])
        run([PY, "data/scripts/preprocess/verify_processed.py"])
        run([PY, "data/scripts/annotate/dynamic_tagging.py"])

    # 3.2 训练（用 python -m 包导包）
    if args.smoke:
        run([PY, "-m", "models.baseline.scripts.train", "--max-samples", "3000"])
        run([PY, "-m", "models.fasttext.scripts.train", "--max-samples", "3000"])
        if not args.skip_bert:
            ensure_bert()
            run(
                [
                    PY, "-m", "models.bert.common.scripts.train",
                    "--max-samples", "1500", "--epochs", "1", "--batch-size", "16",
                ]
            )
            run(
                [
                    PY, "-m", "models.bert.category.scripts.train",
                    "--max-samples", "1200", "--epochs", "1", "--batch-size", "16",
                    "--top-n-categories", "3",
                ]
            )
            if not args.skip_distill:
                run(
                    [
                        PY, "-m", "models.bert.distill.scripts.train",
                        "--max-samples", "1500", "--epochs", "2", "--batch-size", "16",
                    ]
                )
    else:
        run([PY, "-m", "models.baseline.scripts.train"])
        run([PY, "-m", "models.fasttext.scripts.train"])
        if not args.skip_bert:
            ensure_bert()
            run([PY, "-m", "models.bert.common.scripts.train", "--epochs", "2"])
            run(
                [
                    PY, "-m", "models.bert.category.scripts.train",
                    "--epochs", "2", "--top-n-categories", "3",
                ]
            )
            if not args.skip_distill:
                run([PY, "-m", "models.bert.distill.scripts.train", "--epochs", "3"])

    # 3.3 对比结果
    run([PY, "-m", "models.common.scripts.compare_results"])
    print(f'\n流水线完成。')
    print(f'对比表: models/common/results/model_compare.csv')
    print(f'商品标签墙: data/processed/product_tags.csv')


if __name__ == "__main__":
    # 1. 跑流水线
    main()
