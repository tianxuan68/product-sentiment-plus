# -*- coding: utf-8 -*-
"""
data_utils.py —— 数据处理工具模块（属性级情感分类）

职责：
    1. ensure_file_exists()        文件存在性检查（带友好中文提示）
    2. load_raw_data()             读取原始预处理 CSV（解析 类别 / attributes JSON）
    3. make_label_vector()         把 (属性, 极性) 列表转成 16 维 multi-hot 标签向量
    4. split_and_save()            把全量数据按类别分层拆分为 训练/验证/测试 并保存
    5. load_processed_data()       读取拆分后的 CSV，返回训练需要的结构化数据

关于分词列的选择（数据格式说明）：
    原始数据提供 4 种分词列：tokens_jieba / text_clean_jieba / tokens_char / text_clean_char。
    BERT-base-Chinese 的分词器本身按「字」切分（词表是汉字），
    再额外用 jieba 分词并不会带来增益，反而可能引入错误切分；且预测新评论时未必有 jieba 依赖。
    因此模型输入采用「原始清洗文本」评论内容_clean（BERT 分词器会自行按字切分）。
    同时把 text_clean_char（字级分词、空格分隔）保留到处理后文件，方便人工阅读与排查。
"""

import json
import random
import pandas as pd
from pathlib import Path
from sklearn.model_selection import train_test_split


# ---------------------------------------------------------------------------
# 1. 文件存在性检查（带友好中文提示的异常处理）
# ---------------------------------------------------------------------------
def ensure_file_exists(file_path: str, hint: str = "") -> None:
    """
    检查文件是否存在，不存在则抛出 FileNotFoundError 并给出中文提示。

    参数：
        file_path: 待检查的文件路径。
        hint:      补充说明（例如该文件应由谁提供、放哪里），便于排查。
    """
    path = Path(file_path)
    if not path.exists():
        msg = f"[数据文件缺失] 找不到文件：{file_path}"
        if hint:
            msg += f"\n说明：{hint}"
        raise FileNotFoundError(msg)


# ---------------------------------------------------------------------------
# 2. 原始数据读取与解析
# ---------------------------------------------------------------------------
def load_raw_data(raw_file: str) -> pd.DataFrame:
    """
    读取原始预处理 CSV，并把 JSON 字符串列解析成结构化数据。

    原始列说明：
        评论内容_clean   清洗后的评论文本（模型输入）
        tokens_jieba    jieba 词级分词（JSON 列表，备选列）
        text_clean_jieba jieba 分词空格连接（备选列）
        tokens_char     字级分词（JSON 列表，备选列）
        text_clean_char 字级分词空格连接（备选列，保留）
        类别             JSON：[{"类别": "图书音像", "类别ID": 0}]
        attributes       JSON：[{"aspect": "价格", "polarity": 1}, ...]

    参数：
        raw_file: 原始 CSV 路径。

    返回：
        处理后的 DataFrame，新增两列：
            category_str  类别名（str）
            attributes_list   [(属性名, 极性1/0), ...] 列表
    """
    ensure_file_exists(raw_file, hint="原始数据文件缺失，请确认 data/data_pre/数据集最终版.csv 存在。")

    df = pd.read_csv(raw_file, encoding="utf-8-sig")

    # 必要列校验
    required = ["评论内容_clean", "类别", "attributes"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            f"[数据格式错误] 原始数据缺少必要列：{missing}\n"
            f"实际列：{list(df.columns)}"
        )

    # 解析「类别」JSON -> 类别名字符串
    def parse_category(v):
        try:
            lst = json.loads(v)
            return lst[0]["类别"]
        except Exception:
            return ""

    # 解析「attributes」JSON -> [(aspect, polarity), ...]
    def parse_attributes(v):
        try:
            lst = json.loads(v)
            return [(a["aspect"], int(a["polarity"])) for a in lst]
        except Exception:
            return []

    df["category_str"] = df["类别"].apply(parse_category)
    df["attributes_list"] = df["attributes"].apply(parse_attributes)

    # 去掉没有任何属性标注的行（无法用于监督训练）
    df = df[df["attributes_list"].map(len) > 0].reset_index(drop=True)
    return df


# ---------------------------------------------------------------------------
# 3. 标签向量：8 属性 × 2 极性 -> 16 维 multi-hot
# ---------------------------------------------------------------------------
def make_label_vector(attributes_list: list, aspects: list) -> list:
    """
    把一条评论的 [(属性, 极性), ...] 转成 16 维 0/1 标签向量。

    规则（与 config.build_label_names 一致）：
        前 8 位 = 各属性「好」（正面），后 8 位 = 各属性「坏」（负面）。

    参数：
        attributes_list: [(属性名, 极性), ...]，如 [("质量", 1), ("价格", 0)]。
        aspects:         8 个属性名列表。

    返回：
        长度为 16 的 0/1 列表。例如 "质量好" 则第 0 位为 1。
    """
    n = len(aspects)
    vec = [0] * (2 * n)
    for aspect, polarity in attributes_list:
        if aspect not in aspects:
            continue  # 未知属性直接跳过，避免越界
        idx = aspects.index(aspect) if polarity == 1 else aspects.index(aspect) + n
        vec[idx] = 1
    return vec


# ---------------------------------------------------------------------------
# 4. 拆分并保存 训练/验证/测试 数据
# ---------------------------------------------------------------------------
def split_and_save(
    raw_file: str,
    processed_dir: str,
    aspects: list,
    ratios: dict = None,
    random_state: int = 42,
) -> dict:
    """
    把全量数据按「类别」分层拆分为训练/验证/测试集，并保存为 CSV。

    说明：
        数据集只有一份（data_pre/数据集最终版.csv），训练/验证/测试需自行拆分。
        为避免类别分布被破坏（例如「图书音像」占了 61%），
        采用按类别分层的随机抽样（stratified），保证三个集合的类别比例一致。

    参数：
        raw_file:      原始 CSV 路径。
        processed_dir: 处理后数据输出目录（自动创建）。
        aspects:       8 个属性名列表。
        ratios:        拆分比例字典，如 {"train": 0.8, "val": 0.1, "test": 0.1}。
        random_state:  随机种子，保证可复现。

    返回：
        {集合名: 输出 CSV 绝对路径, ...}
    """
    ratios = ratios or {"train": 0.8, "val": 0.1, "test": 0.1}
    out_dir = Path(processed_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = load_raw_data(raw_file)
    total = len(df)
    print(f"[数据读取] 原始数据共 {total} 条，类别数 = {df['category_str'].nunique()}")

    # 标签向量列（转成 0/1 拼接字符串，便于保存与阅读）
    label_vecs = df["attributes_list"].apply(lambda lst: make_label_vector(lst, aspects))
    df["labels"] = label_vecs.apply(lambda v: ",".join(str(x) for x in v))
    # 命中的属性（去重），便于快速人工核对
    df["aspects_hit"] = df["attributes_list"].apply(
        lambda lst: ",".join(dict.fromkeys(a for a, _ in lst))
    )

    # 按「类别」分层：保证训练/验证/测试三者的类别比例一致。
    # 注意：不能再加「属性数」做组合分层——存在只有 1 条的稀有组合，
    # 会导致 StratifiedShuffleSplit 报「类内成员不足 2」错误。
    stratify_key = df["category_str"].astype(str)

    # 先切出测试集，再从剩余部分切出训练/验证
    train_val, test = train_test_split(
        df, test_size=ratios["test"], random_state=random_state,
        stratify=stratify_key, shuffle=True,
    )
    val_ratio = ratios["val"] / (ratios["train"] + ratios["val"])
    train, val = train_test_split(
        train_val, test_size=val_ratio, random_state=random_state,
        stratify=train_val["category_str"].astype(str), shuffle=True,
    )

    # 保存列：类别、评论文本、字级分词（参考）、原始 attributes、标签、命中属性
    keep_cols = [
        "category_str", "评论内容_clean", "text_clean_char",
        "attributes", "attributes_list", "labels", "aspects_hit",
    ]
    result_paths = {}
    for name, part in [("train", train), ("val", val), ("test", test)]:
        save_path = out_dir / f"{name}.csv"
        part[keep_cols].to_csv(save_path, index=False, encoding="utf-8-sig")
        result_paths[name] = str(save_path)
        # 打印每个集合的类别与属性分布，方便核对拆分质量
        print(f"\n[{name}] 共 {len(part)} 条 -> {save_path}")
        print("  类别分布：", part["category_str"].value_counts().to_dict())
        print("  属性命中分布：", part["attributes_list"].apply(len).value_counts().to_dict())

    # 打印全局属性×极性分布，供对照
    pos_neg = {"好": 0, "坏": 0}
    for lst in df["attributes_list"]:
        for _, p in lst:
            pos_neg["好" if p == 1 else "坏"] += 1
    print(f"\n[全量] 属性极性分布（好/坏）：{pos_neg}")
    return result_paths


# ---------------------------------------------------------------------------
# 5. 加载拆分后的数据
# ---------------------------------------------------------------------------
def load_processed_data(split_file: str, aspects: list) -> tuple:
    """
    读取拆分后的 CSV，返回训练/评估直接可用的结构化数据。

    参数：
        split_file: train.csv / val.csv / test.csv 路径。
        aspects:    8 个属性名列表。

    返回：
        (categories, texts, label_vectors, attributes_lists)
        categories:       类别名列表
        texts:            评论文本列表（评论内容_clean）
        label_vectors:    16 维 0/1 列表（嵌套列表）
        attributes_lists: [(属性名, 极性), ...] 列表
    """
    ensure_file_exists(split_file, hint="请先运行 data_utils.py 生成训练/验证/测试拆分文件。")

    df = pd.read_csv(split_file, encoding="utf-8-sig")

    def parse_attributes(v):
        # attributes 列保存的是原始 JSON（[{"aspect": "价格", "polarity": 1}]），可直接解析
        try:
            lst = json.loads(v)
            return [(a["aspect"], int(a["polarity"])) for a in lst]
        except Exception:
            return []

    categories = df["category_str"].fillna("").astype(str).tolist()
    texts = df["评论内容_clean"].fillna("").astype(str).tolist()
    attributes_lists = df["attributes"].apply(parse_attributes).tolist()
    label_vectors = [
        make_label_vector(lst, aspects) for lst in attributes_lists
    ]
    return categories, texts, label_vectors, attributes_lists


# ---------------------------------------------------------------------------
# 6. 直接运行入口：一键拆分数据
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from config import Config

    paths = split_and_save(
        raw_file=Config["raw_data_file"],
        processed_dir=Config["processed_data_dir"],
        aspects=Config["aspects"],
        ratios=Config["split_ratios"],
        random_state=Config["split_random_state"],
    )
    print("\n拆分完成：", paths)
