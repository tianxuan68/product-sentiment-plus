# -*- coding: utf-8 -*-
"""
data_utils.py —— 数据处理工具模块

职责：
    1. load_tag_vocab()         加载品类标签字典，得到全部标签列表（多标签分类的类别集合）
    2. generate_synthetic_data() 生成合成多标签数据（训练数据未就绪前用于跑通流程）
    3. load_labeled_data()       读取标注数据（兼容两种格式，见下）
    4. build_tag_templates()     合成数据用的「标签 → 模板句子」映射

标注数据支持的两种格式：
    - 扁平格式（推荐）：每行一条评论，tags 列为逗号分隔的标签
        review_id,category,sentence,tags
        r001,女装,质量很好 发货快,质量好|发货快
    - 长表格式（与 review_tags.csv 一致）：每行一个标签明细，程序自动按 review_id 聚合
        review_id,product_id,category,aspect,opinion,polarity,tag
"""

import random
import pandas as pd
from pathlib import Path


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
# 2. 标签词表加载
# ---------------------------------------------------------------------------
def load_tag_vocab(vocab_file: str, alt_vocab_file: str = "") -> list:
    """
    从品类标签字典 CSV 中读取「全部标签」，作为多标签分类的类别集合。

    字典文件格式（category_tag_vocab.csv）：
        category,aspect,tag,polarity
        女装,面料,面料不错,positive
        ...

    参数：
        vocab_file:     品类标签字典路径。
        alt_vocab_file: 备用路径（主路径不存在时尝试）。

    返回：
        去重后排序的标签名列表，例如 ["不发烫", "价格贵", ...]。
    """
    # 主路径不存在时回退到备用路径
    candidates = [vocab_file] + ([alt_vocab_file] if alt_vocab_file else [])
    chosen = None
    for cand in candidates:
        if Path(cand).exists():
            chosen = cand
            break

    if chosen is None:
        # 两个候选都不存在，给出明确提示
        raise FileNotFoundError(
            f"[标签词表缺失] 主路径 {vocab_file} 与备用路径 {alt_vocab_file} 均不存在。\n"
            f"请确认品类标签字典文件已就绪（参考 data/examples/category_tag_vocab.csv）。"
        )

    # utf-8-sig 可兼容带 BOM 的 Excel 导出文件
    df = pd.read_csv(chosen, encoding="utf-8-sig")

    # 字典必须包含 tag 列
    if "tag" not in df.columns:
        raise ValueError(
            f"[标签词表格式错误] 文件 {chosen} 缺少 tag 列，"
            f"请检查是否为品类标签字典（含 category,aspect,tag,polarity）。"
        )

    # 去重 + 排序，保证标签顺序稳定（可复现）
    tags = sorted(set(df["tag"].dropna().astype(str).str.strip()))
    if not tags:
        raise ValueError(f"[标签词表为空] 文件 {chosen} 中没有任何有效标签。")

    return tags


# ---------------------------------------------------------------------------
# 3. 合成数据生成
# ---------------------------------------------------------------------------
def build_tag_templates() -> dict:
    """
    构造「标签 → 多个近义模板句子」的映射，用于生成合成数据。

    说明：
        每个标签给出若干句不同表达的同义句，生成时随机挑选，
        让合成数据具备一定多样性，模型需要学会把不同表述映射到同一标签。

    返回：
        {标签名: [句子1, 句子2, ...], ...}
    """
    templates = {
        # ------------------- 女装 -------------------
        "面料不错": ["面料很好", "料子很不错", "面料质感很棒", "布料摸起来舒服"],
        "面料差": ["面料很差", "布料太差了", "料子不行，容易起球", "面料摸起来很廉价"],
        "做工细致": ["做工细致", "做工很精致", "走线缝合得很整齐", "细节处理得很好"],
        "做工粗糙": ["做工粗糙", "针脚都不齐", "缝线歪歪扭扭", "做工马马虎虎"],
        "版型好看": ["版型好看", "版型显瘦", "剪裁很正", "穿上很显身材"],
        "容易卷边": ["会卷边", "衣服下摆容易卷起来", "边缘老是卷着", "洗一次就卷边了"],
        "尺码合适": ["尺码合适", "大小正好", "尺码刚刚好", "穿着大小很合适"],
        "建议买大一码": ["建议买大一码", "这款偏小，建议拍大一号", "正常码穿不了，要买大点", "尺码偏小，大一号合适"],
        "发货快": ["发货也很快", "物流很快", "发货速度一流", "当天就发货了"],
        "质量好": ["质量很好", "质量杠杠的", "质量没得说", "做工质量都很好"],
        # ------------------- 鞋靴 -------------------
        "外观好看": ["外观很好看", "样子非常好看", "颜值很高", "款式时尚好看"],
        "穿着舒适": ["穿着很舒适", "上脚舒服", "走起来不累脚", "鞋底软，很舒服"],
        "鞋垫不平": ["鞋垫的胶凹凸不平", "鞋垫不平整", "鞋垫有点硌脚", "鞋垫粘歪了"],
        "疑似非正品": ["感觉不是正品", "怀疑是假货", "不像正品", "包装像高仿的"],
        # ------------------- 数码 -------------------
        "质量好": ["质量很好", "做工扎实", "质量可靠", "用起来很稳"],
        "续航久": ["续航很久", "电池耐用", "电量很扛用", "充满能用好几天"],
        "续航差": ["续航太差了", "电池不耐用", "一会儿就没电了", "半天就要充电"],
        "不发烫": ["不怎么发热", "散热很好", "连续用也不烫手", "温度控制得很好"],
        "容易发热": ["用一会就发热", "容易发烫", "发热严重", "玩一会儿就很烫"],
        "性价比高": ["性价比很高", "物美价廉", "这个价位很值", "价格不贵还好用"],
        "价格贵": ["价格太贵了", "价钱有点高", "比别家贵不少", "性价比不高，偏贵"],
        "容易坏": ["一个星期就坏了", "用几天就坏了", "质量太差，容易坏", "很快就出故障了"],
        "客服差": ["客服没人管", "客服态度差", "找客服也没人理", "售后一直联系不上"],
        # ------------------- 食品 -------------------
        "味道不错": ["味道很不错", "口感很好", "很好吃", "味道正"],
        "味道一般": ["味道一般", "口感平平", "味道不咋地", "没什么特别"],
        "香味纯正": ["香气很纯正", "香味浓郁", "闻着很香", "香味自然不刺鼻"],
        "香味不对": ["香气跟以前不一样", "香味怪怪的", "香精味太重", "闻起来不对劲"],
        "疑似假货": ["不知道是不是假的", "怀疑买到假货了", "可能是假货", "跟以前买的不一样，像假的"],
        "很新鲜": ["很新鲜", "食材很新鲜", "日期很新，很新鲜", "收到的都很新鲜"],
    }
    return templates


def generate_synthetic_data(
    vocab_file: str,
    output_dir: str,
    sizes: dict,
    min_tags: int = 1,
    max_tags: int = 3,
    seed: int = 42,
    alt_vocab_file: str = "",
) -> dict:
    """
    生成合成多标签数据（训练 / 验证 / 测试），输出到指定目录。

    生成规则：
        1. 加载标签词表得到全部标签；
        2. 为每条评论随机挑选 1~max_tags 个标签；
        3. 每个标签从模板池里随机抽一句同义句；
        4. 将若干句用标点连接成一条完整评论，同时记录其对应标签集合。

    参数：
        vocab_file: 品类标签字典路径。
        output_dir: 输出目录（会自动创建）。
        sizes:      各集合样本量，形如 {"train": 600, "val": 100, "test": 100}。
        min_tags:   每条评论最少标签数。
        max_tags:   每条评论最多标签数。
        seed:       随机种子，保证可复现。
        alt_vocab_file: 备用标签字典路径（主路径不存在时使用）。

    返回：
        {集合名: 输出 CSV 绝对路径, ...}
    """
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    # 加载全部标签，作为随机抽取的候选池
    tags = load_tag_vocab(vocab_file, alt_vocab_file)
    templates = build_tag_templates()

    # 过滤出有模板的标签（避免生成空评论）
    valid_tags = [t for t in tags if templates.get(t)]
    if not valid_tags:
        raise ValueError("[合成数据生成失败] 标签词表与模板没有交集，无法生成数据。")

    rng = random.Random(seed)
    # 标点连接符：让生成的句子更有真实评论的感觉
    connectors = ["，", "，而且", "，同时", "，另外", "。"]

    result_paths = {}
    for split_name, size in sizes.items():
        rows = []
        for i in range(size):
            # 随机抽取本评论要包含的标签（个数在 min~max 之间）
            n_tags = rng.randint(min(min_tags, len(valid_tags)), min(max_tags, len(valid_tags)))
            chosen_tags = rng.sample(valid_tags, n_tags)

            # 每个标签随机抽一句同义句，用连接符拼成完整评论
            sentences = [rng.choice(templates[t]) for t in chosen_tags]
            # 打乱顺序，避免模型学到「固定顺序」这种虚假特征
            rng.shuffle(sentences)
            text = connectors[rng.randrange(len(connectors))].join(sentences)

            # 标签用 | 分隔存入单列（避免与评论里的中文逗号冲突）
            rows.append({
                "review_id": f"{split_name}_{i:04d}",
                "sentence": text,
                "tags": "|".join(chosen_tags),
            })

        df = pd.DataFrame(rows, columns=["review_id", "sentence", "tags"])
        save_path = output / f"{split_name}_reviews.csv"
        # index=False 避免写出多余序号列；utf-8-sig 便于 Excel 直接打开
        df.to_csv(save_path, index=False, encoding="utf-8-sig")
        result_paths[split_name] = str(save_path)
        print(f"[合成数据] 已生成 {split_name} 集：{size} 条 -> {save_path}")

    return result_paths


# ---------------------------------------------------------------------------
# 4. 标注数据读取（兼容扁平格式与长表格式）
# ---------------------------------------------------------------------------
def load_labeled_data(file_path: str, sep_in_tags: str = "|") -> list:
    """
    读取多标签标注数据，统一返回 (文本, 标签列表) 结构。

    支持的格式：
        - 扁平格式：包含 sentence 与 tags 两列，tags 内用 | 分隔。
        - 长表格式：包含 review_id 与 tag 两列（可含 aspect/opinion 等明细列），
          程序按 review_id 自动聚合，并将 sentence 去重。

    参数：
        file_path:    数据文件路径。
        sep_in_tags:  扁平格式中标签的分隔符，默认 |。

    返回：
        [(句子字符串, [标签1, 标签2, ...]), ...]
    """
    ensure_file_exists(
        file_path,
        hint="训练/验证/测试数据未就绪。可先运行 generate_synthetic_data 生成合成数据，"
             "或用 python scripts/data_utils.py 直接生成。",
    )

    df = pd.read_csv(file_path, encoding="utf-8-sig")

    # ---- 情况 A：扁平格式（sentence + tags） ----
    if {"sentence", "tags"}.issubset(df.columns):
        samples = []
        for _, row in df.iterrows():
            text = str(row["sentence"]).strip()
            # 拆分标签，过滤空标签
            tag_list = [t.strip() for t in str(row["tags"]).split(sep_in_tags) if str(t).strip()]
            if text:  # 跳过空评论
                samples.append((text, tag_list))
        return samples

    # ---- 情况 B：长表格式（review_id + tag，需聚合） ----
    if {"review_id", "tag"}.issubset(df.columns):
        # 按 review_id 分组，每个评论聚合出标签集合
        grouped = df.groupby("review_id")
        samples = []
        for review_id, group in grouped:
            # 评论正文：长表中通常只有一行带 sentence；若没有则用标签拼一个占位
            sentence_series = group["sentence"] if "sentence" in group.columns else None
            text = None
            if sentence_series is not None:
                texts = sentence_series.dropna().astype(str).str.strip()
                texts = texts[texts != ""]
                if len(texts) > 0:
                    text = texts.iloc[0]
            # 评论正文缺失时，把该评论的标签拼起来当作正文（便于跑通流程）
            if not text:
                text = "，".join(group["tag"].astype(str).tolist())
            # 该评论对应的标签集合（去重）
            tag_list = sorted(set(group["tag"].dropna().astype(str).str.strip().tolist()))
            samples.append((text, tag_list))
        return samples

    # ---- 两种格式都不满足 ----
    raise ValueError(
        f"[数据格式错误] 文件 {file_path} 无法识别为多标签数据。\n"
        f"需要包含列：sentence,tags（扁平格式）或 review_id,tag（长表格式），"
        f"实际列为：{list(df.columns)}"
    )


# ---------------------------------------------------------------------------
# 5. 直接运行入口：一键生成合成数据
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # 独立运行本脚本时，生成一份合成数据，方便快速准备数据
    from config import Config

    sizes = {
        "train": Config["synthetic_train_size"],
        "val": Config["synthetic_val_size"],
        "test": Config["synthetic_test_size"],
    }
    paths = generate_synthetic_data(
        vocab_file=Config["vocab_file"],
        alt_vocab_file=Config["vocab_file_alt"],
        output_dir=Config["synthetic_data_dir"],
        sizes=sizes,
        min_tags=Config["synthetic_min_tags"],
        max_tags=Config["synthetic_max_tags"],
        seed=Config["seed"],
    )
    print("生成完成：", paths)
