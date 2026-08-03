"""
案例:
    下载中文 BERT 预训练权重。

用法（在 product-sentiment-ai 目录下）:
    python -m models.common.scripts.download_bert
"""

# 导包
import os


# 1. 定义函数, 下载
def main():
    out = "./models/bert/common/pretrained"
    os.makedirs(out, exist_ok=True)
    try:
        from modelscope import snapshot_download
    except ImportError as e:
        raise ImportError("请先: pip install modelscope") from e

    print(f'从 ModelScope 下载 tiansz/bert-base-chinese ...')
    path = snapshot_download("tiansz/bert-base-chinese", cache_dir=out)
    print(f'下载完成: {path}')
    print(f'训练时脚本会自动优先使用该本地路径。')


if __name__ == "__main__":
    # 1. 下载预训练
    main()
