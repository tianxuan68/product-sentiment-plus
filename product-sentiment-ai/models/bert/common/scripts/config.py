# -*- coding: utf-8 -*-
"""
config.py —— 全局配置字典

说明：
    本项目所有超参数与路径都集中在这个 Config 字典中管理，
    训练脚本（train.py）与推理脚本（predict.py）都从这里读取，
    便于统一调整，避免散落在各处。

    路径约定：本文件位于 common/scripts/ 下，
    因此 common/ 根目录 = 本文件上一级目录的上一级目录。
    所有相对路径都基于 common/ 根目录计算，保证任意目录下运行都不会出错。
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# 1. 目录基础：自动定位项目根目录（common/）
# ---------------------------------------------------------------------------
# 本文件所在目录：common/scripts/
_SCRIPT_DIR = Path(__file__).resolve().parent
# 项目根目录：common/
PROJECT_ROOT = _SCRIPT_DIR.parent

# ---------------------------------------------------------------------------
# 2. 全局配置字典
# ---------------------------------------------------------------------------
Config = {
    # ------------------------- 模型相关 -------------------------
    # 预训练 BERT 模型所在目录（本地已有，无需联网下载）
    "model_name_or_path": str(PROJECT_ROOT / "bert-base-chinese"),
    # 输入文本最大长度（超出的部分会被截断）
    "max_len": 64,
    # 分类头前面的 Dropout 比例（防止过拟合）
    "dropout": 0.3,
    # 标签数量（训练时自动从标签词表推断，无需手工指定）
    "num_labels": None,

    # ------------------------- 数据相关 -------------------------
    # 品类标签字典：定义了「每个品类下有哪些标签」，所有标签集合作为多标签分类的类别
    "vocab_file": str(PROJECT_ROOT.parent.parent.parent / "data" / "examples" / "category_tag_vocab.csv"),
    # 训练 / 验证 / 测试数据文件（合成数据由 generate_synthetic_data 生成）
    "train_file": str(PROJECT_ROOT / "data" / "synthetic" / "train_reviews.csv"),
    "val_file": str(PROJECT_ROOT / "data" / "synthetic" / "val_reviews.csv"),
    "test_file": str(PROJECT_ROOT / "data" / "synthetic" / "test_reviews.csv"),
    # 标签词表兜底：如果上面的 vocab_file 不存在，回退到同一目录下的 04_ 前缀文件
    "vocab_file_alt": str(PROJECT_ROOT.parent.parent.parent / "data" / "examples" / "04_category_tag_vocab.csv"),

    # ------------------------- 训练相关 -------------------------
    # 训练轮数
    "epochs": 4,
    # 批大小（CPU 环境下建议小一点，如 16）
    "batch_size": 16,
    # 学习率（多标签稀疏正样本场景下，稍高的学习率有助于分类头更快学习）
    "lr": 5e-5,
    # 权重衰减（AdamW 正则化）
    "weight_decay": 0.01,
    # 学习率线性预热比例
    "warmup_ratio": 0.1,
    # BCE 损失的正样本权重上限（pos_weight = 负样本数/正样本数，裁剪到该上限）。
    # 多标签任务正样本稀少，不加平衡会让模型退化成「什么都不预测」。
    "pos_weight_clamp": 8.0,
    # DataLoader 并行加载进程数（Windows 下默认 0 最稳妥）
    "num_workers": 0,
    # 多标签判定阈值：logits > threshold 视为命中该标签。
    # 0.5 是最常见默认，但本任务经 pos_weight 平衡后概率偏高，
    # 实测在验证集上 0.65 左右 Macro-F1 最优（见 README 运行结果），
    # 且平均预测标签数接近真实标签数，故默认取 0.65。
    "threshold": 0.65,
    # 随机种子（保证可复现）
    "seed": 42,
    # 计算设备：留空则自动选择 GPU，没有 GPU 自动退回 CPU
    "device": None,

    # ------------------------- 保存 / 日志路径 -------------------------
    # 模型保存目录（common/checkpoints/）
    "save_dir": str(PROJECT_ROOT / "checkpoints"),
    # 最佳模型（验证集指标最优）保存路径
    "best_model_path": str(PROJECT_ROOT / "checkpoints" / "best_model.pt"),
    # 最终模型（全部训练结束后）保存路径
    "final_model_path": str(PROJECT_ROOT / "checkpoints" / "final_model.pt"),
    # 结果目录（指标、日志，common/results/）
    "result_dir": str(PROJECT_ROOT / "results"),
    # 训练过程指标记录文件（CSV）
    "log_file": str(PROJECT_ROOT / "results" / "train_log.csv"),
    # 最终测试集指标文件（JSON）
    "metrics_file": str(PROJECT_ROOT / "results" / "test_metrics.json"),
    # 标签列表备份文件（推理时需要用到）
    "tags_file": str(PROJECT_ROOT / "results" / "tags.txt"),

    # ------------------------- 合成数据生成 -------------------------
    # 各集合生成样本数量（训练数据未就绪前，用合成数据跑通流程）
    "synthetic_train_size": 600,
    "synthetic_val_size": 100,
    "synthetic_test_size": 100,
    # 每条评论至少 / 最多包含几个标签
    "synthetic_min_tags": 1,
    "synthetic_max_tags": 3,
    # 合成数据输出目录（common/data/synthetic/）
    "synthetic_data_dir": str(PROJECT_ROOT / "data" / "synthetic"),
}


# ---------------------------------------------------------------------------
# 3. 设备自动选择：优先 GPU，无 GPU 自动回退 CPU
# ---------------------------------------------------------------------------
def get_device(force_device: str = None) -> str:
    """
    根据配置自动选择计算设备。

    参数：
        force_device: 可手动指定 "cuda" / "cpu"，一般传 None 走自动判断。

    返回：
        设备字符串，如 "cuda" 或 "cpu"。
    """
    # 手动指定了设备则优先使用
    if force_device:
        return force_device

    # 尝试导入 torch 并检测 CUDA 是否可用
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
    except ImportError:
        pass

    # 没有 GPU（或未安装 torch）时回退到 CPU
    return "cpu"


if __name__ == "__main__":
    # 独立运行本文件时，打印配置便于检查
    for key, value in Config.items():
        print(f"{key} = {value}")
    print("当前自动选择设备 =", get_device())
