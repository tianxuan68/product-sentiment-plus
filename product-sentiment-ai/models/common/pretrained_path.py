"""
案例:
    解析本地可用的中文 BERT 权重路径（只走本地，避免 HuggingFace 慢下载）。

大白话:
    有本地就用本地；没有就提示先跑 download_bert.py。
"""

# 导包
import os


# 1. 定义函数, 判断目录是否像可用模型
def _is_local_model_dir(path):
    if not os.path.exists(os.path.join(path, "config.json")):
        return False
    has_safe = os.path.exists(os.path.join(path, "model.safetensors"))
    has_bin = os.path.exists(os.path.join(path, "pytorch_model.bin"))
    return has_safe or has_bin


# 2. 定义函数, 解析本地路径
def resolve_bert_model(preferred=None):
    if preferred:
        if _is_local_model_dir(preferred):
            return os.path.abspath(preferred)
        raise FileNotFoundError(
            f"本地模型目录无效: {preferred}\n"
            "请传已下载的目录，或先运行: python -m models.common.scripts.download_bert"
        )

    # 候选路径写在函数里
    candidates = [
        "./models/bert/common/pretrained/models/tiansz--bert-base-chinese/snapshots/master",
        "./models/bert/common/pretrained/bert-base-chinese",
        "./models/bert/common/model/bert_all",
    ]
    for c in candidates:
        if _is_local_model_dir(c):
            print(f'使用本地 BERT: {c}')
            return os.path.abspath(c)

    raise FileNotFoundError(
        "未找到本地中文 BERT 权重。请先运行（国内快）：\n"
        "  python -m models.common.scripts.download_bert\n"
        f"期望路径之一:\n  {candidates[0]}"
    )


# 3. 定义函数, 没有就尝试下载
def ensure_bert_pretrained():
    try:
        return resolve_bert_model()
    except FileNotFoundError:
        pass

    out = "./models/bert/common/pretrained"
    os.makedirs(out, exist_ok=True)
    try:
        from modelscope import snapshot_download
    except ImportError as e:
        raise ImportError(
            "缺少 modelscope，请: pip install modelscope\n"
            "或手动运行: python -m models.common.scripts.download_bert"
        ) from e

    print(f'本地无 BERT，开始 ModelScope 下载...')
    snapshot_download("tiansz/bert-base-chinese", cache_dir=out)
    return resolve_bert_model()
