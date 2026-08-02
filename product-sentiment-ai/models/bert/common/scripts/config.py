# -*- coding: utf-8 -*-
"""
config.py —— 全局配置字典（属性级情感分类 / ABSA）

任务定义：
    输入「商品类别 + 评论文本」，输出 8 种属性（质量/做工/价格/物流/服务/包装/描述/外观）
    各自的情感：好(正面) / 坏(负面) / 未提及。
    建模方式：多标签分类。把 8 个属性 × 2 个极性 = 16 个「(属性, 极性)」对当作 16 个标签，
    用 BERT 编码后接一个 16 维分类头，逐位 sigmoid 二分类（BCEWithLogitsLoss）。

路径约定：
    本文件位于 common/scripts/ 下，因此 common/ 根目录 = 本文件上一级目录的上一级目录。
    所有相对路径都基于 common/ 根目录计算，保证任意目录下运行都不会出错。
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# 1. 目录基础：自动定位项目根目录（common/）
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent          # common/scripts/
PROJECT_ROOT = _SCRIPT_DIR.parent                       # common/

# ---------------------------------------------------------------------------
# 2. 全局配置字典
# ---------------------------------------------------------------------------
Config = {
    # ------------------------- 模型相关 -------------------------
    # 预训练 BERT 模型所在目录（本地已有，无需联网下载）
    "model_name_or_path": str(PROJECT_ROOT / "bert-base-chinese"),
    # 输入文本最大长度（= [CLS]+类别+[SEP]+评论+[SEP] 的总 token 数）
    # 数据统计：75% 的评论 ≤ 52 字符，取 64 可完整覆盖约 80% 的评论，
    # 且 BERT 计算量随序列长度上升明显（本机为 CPU），在速度与召回间取平衡。
    "max_len": 64,
    # 分类头前面的 Dropout 比例（防止过拟合）
    "dropout": 0.3,
    # 标签数量：16 = 8 属性 × 2 极性，训练时自动设置，无需手工修改
    "num_labels": None,

    # ------------------------- 类别 / 属性定义 -------------------------
    # 15 个商品类别（与 data_pre/类别ID对照表.csv 一致），作为模型输入的一部分
    "categories": [
        "图书音像", "电脑/办公", "手机/数码", "美妆个护", "家用电器",
        "家居生活", "其他", "母婴/玩具", "家具/家装/建材",
        "钟表/首饰/眼镜/礼品", "食品/保健", "鞋类箱包", "运动户外",
        "服饰服装", "机票/充值/票务/虚拟",
    ],
    # 8 种评价属性（attributes 中出现的全部 aspect）
    "aspects": ["质量", "做工", "价格", "物流", "服务", "包装", "描述", "外观"],

    # ------------------------- 数据相关 -------------------------
    # 原始预处理数据（用户提供，只读）
    "raw_data_file": str(PROJECT_ROOT / "data" / "data_pre" / "数据集最终版.csv"),
    # 类别 ID 对照表（只读，用于校验）
    "category_id_file": str(PROJECT_ROOT / "data" / "data_pre" / "类别ID对照表.csv"),
    # 处理后数据输出目录（本脚本生成的 train/val/test 拆分文件）
    "processed_data_dir": str(PROJECT_ROOT / "data" / "processed"),
    "train_file": str(PROJECT_ROOT / "data" / "processed" / "train.csv"),
    "val_file": str(PROJECT_ROOT / "data" / "processed" / "val.csv"),
    "test_file": str(PROJECT_ROOT / "data" / "processed" / "test.csv"),
    # 训练/验证/测试 拆分比例（数据集只有一份，由程序自行拆分）
    "split_ratios": {"train": 0.8, "val": 0.1, "test": 0.1},
    # 拆分随机种子（与训练 seed 分开，便于独立复现拆分结果）
    "split_random_state": 42,

    # ------------------------- 训练相关 -------------------------
    # 训练轮数（CPU 上可适当减少；配合早停防止过拟合）
    "epochs": 15,
    # 批大小（CPU 环境建议 16）
    "batch_size": 16,
    # 学习率（BERT 微调常用 2e-5 ~ 5e-5）
    "lr": 3e-5,
    # 权重衰减（AdamW 正则化）
    "weight_decay": 0.01,
    # 学习率线性预热比例
    "warmup_ratio": 0.1,
    # BCE 损失的正样本权重上限。16 个标签中正样本稀疏（尤其某些属性的负面标签，
    # 如「服务坏」仅几十条），pos_weight = 负样本数/正样本数 会非常大，
    # 需裁剪到该上限防止梯度过激。
    "pos_weight_clamp": 8.0,
    # DataLoader 并行加载进程数（Windows 下默认 0 最稳妥）
    "num_workers": 0,
    # 随机种子（保证可复现）
    "seed": 42,
    # 计算设备：留空则自动选择 GPU，没有 GPU 自动退回 CPU
    "device": None,
    # 早停：验证集指标连续多少轮不提升就提前结束
    "early_stop_patience": 3,

    # ------------------------- 阈值调优 -------------------------
    # 每个属性的「是否提及」判定阈值（logits sigmoid 概率 >= 阈值才认为该属性被提及）。
    # 训练结束后会在验证集上对每个属性单独搜索最优阈值并写入模型检查点。
    "threshold_grid": [0.30, 0.40, 0.50, 0.60, 0.70, 0.80],
    # 未调优前的兜底阈值
    "default_threshold": 0.50,

    # ------------------------- 保存 / 日志路径 -------------------------
    # 模型保存目录（common/checkpoints/）
    "save_dir": str(PROJECT_ROOT / "checkpoints"),
    # 最佳模型（验证集指标最优）保存路径
    "best_model_path": str(PROJECT_ROOT / "checkpoints" / "best_model.pt"),
    # 最终模型（全部训练结束后）保存路径
    "final_model_path": str(PROJECT_ROOT / "checkpoints" / "final_model.pt"),
    # 结果目录（指标、日志，common/results/）
    "result_dir": str(PROJECT_ROOT / "results"),
    # 训练过程指标记录文件（CSV：每轮一行）
    "log_file": str(PROJECT_ROOT / "results" / "train_log.csv"),
    # 训练详细日志文件（文本，保留完整训练输出）
    "train_run_log": str(PROJECT_ROOT / "results" / "train_run.log"),
    # 最终测试集指标文件（JSON）
    "metrics_file": str(PROJECT_ROOT / "results" / "test_metrics.json"),
    # 标签列表备份文件（推理时需要）
    "labels_file": str(PROJECT_ROOT / "results" / "labels.txt"),

    # ------------------------- API 配置 -------------------------
    # 属性级情感预测服务（api_server.py）监听配置
    "api_host": "0.0.0.0",
    "api_port": 8010,
    # 接口统一前缀
    "api_prefix": "/api",
}


# ---------------------------------------------------------------------------
# 3. 标签结构：8 属性 × 2 极性 -> 16 维
# ---------------------------------------------------------------------------
def build_label_names(aspects: list) -> list:
    """
    根据属性列表生成 16 个标签名（顺序固定，用于 multi-hot 编码与解码）。

    规则：
        前 8 位 = 「属性 + 好」（正面），后 8 位 = 「属性 + 坏」（负面）。
        例如 aspects=["质量","做工"] -> ["质量好","做工好","质量坏","做工坏"]。

    参数：
        aspects: 8 个属性名列表。

    返回：
        16 个标签名列表。
    """
    return [f"{a}好" for a in aspects] + [f"{a}坏" for a in aspects]


# 全局标签名：正面在前 8 位、负面在后 8 位
LABEL_NAMES = build_label_names(Config["aspects"])


# ---------------------------------------------------------------------------
# 4. 设备自动选择：优先 GPU，无 GPU 自动回退 CPU
# ---------------------------------------------------------------------------
def get_device(force_device: str = None) -> str:
    """
    根据配置自动选择计算设备。

    参数：
        force_device: 可手动指定 "cuda" / "cpu"，一般传 None 走自动判断。

    返回：
        设备字符串，如 "cuda" 或 "cpu"。
    """
    if force_device:
        return force_device

    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
    except ImportError:
        pass

    return "cpu"


# ---------------------------------------------------------------------------
# 5. 通用工具：属性/极性 <-> 标签下标
# ---------------------------------------------------------------------------
def label_index(aspect: str, polarity: int) -> int:
    """
    把一个 (属性, 极性) 映射到 16 维标签的下标。

    参数：
        aspect:   属性名，如 "质量"。
        polarity: 极性，1=正面/好，0=负面/坏。

    返回：
        标签下标：正面为 aspects.index(aspect)，负面再偏移 8。
    """
    base = Config["aspects"].index(aspect)
    return base if polarity == 1 else base + len(Config["aspects"])


if __name__ == "__main__":
    # 独立运行本文件时，打印配置便于检查
    for key, value in Config.items():
        print(f"{key} = {value}")
    print("标签名列表 =", LABEL_NAMES)
    print("当前自动选择设备 =", get_device())
