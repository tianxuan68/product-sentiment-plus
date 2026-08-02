"""
把商品评论数据转换为因果推理所需格式（对齐 DoWhy / AURA 因果引擎）。

输出列角色：
  - 提及服务体验：干预变量 treatment
  - 好评：结果变量 outcome
  - 节假日、图书品类：混杂变量 common causes

因果问题示例：
  「评论是否提及物流/包装/客服等服务」对「是否好评」的效应，
  控制节假日与图书品类后估计。

用法：
  python data2causal.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

# ==================================================
# 路径
# ==================================================

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ROOT / "sources"
PROCESSED = ROOT / "processed"

TRAIN_CSV = SOURCES / "训练集.csv"
PRODUCT_CSV = SOURCES / "商品信息.csv"
CATEGORY_CSV = SOURCES / "商品类别列表.csv"
OUTPUT_CSV = PROCESSED / "causal_reviews.csv"

# ==================================================
# 规则配置
# ==================================================

# 干预：评论是否提及服务相关内容
SERVICE_KEYWORDS = (
    "物流",
    "发货",
    "快递",
    "配送",
    "包装",
    "客服",
    "售后",
    "退货",
    "换货",
    "送货",
)

# 结果：评分 >= 该阈值视为好评
GOOD_RATING_THRESHOLD = 4.0

# 混杂：主类目名称中含这些词视为图书品类
BOOK_CATEGORY_KEYWORDS = (
    "图书",
    "小说",
    "文学",
    "教材",
    "教辅",
    "童书",
    "杂志",
    "期刊",
)

# 混杂：中国常见节假日（月-日），用于从评论时间戳判断
HOLIDAY_MD = {
    (1, 1),
    (5, 1),
    (5, 2),
    (5, 3),
    (10, 1),
    (10, 2),
    (10, 3),
    (10, 4),
    (10, 5),
    (10, 6),
    (10, 7),
}


def _contains_any(text: str, keywords: tuple[str, ...]) -> int:
    if not text:
        return 0
    return int(any(k in text for k in keywords))


def _primary_category_id(raw: object) -> str:
    """所属类别形如 CATE_990,CATE_594 → 取第一个。"""
    if pd.isna(raw):
        return ""
    parts = str(raw).split(",")
    return parts[0].strip() if parts else ""


def _is_holiday(ts: object) -> int:
    if pd.isna(ts):
        return 0
    try:
        dt = pd.to_datetime(float(ts), unit="s")
    except (TypeError, ValueError, OverflowError):
        return 0
    # 周末或法定节假日窗口
    if dt.dayofweek >= 5:
        return 1
    return int((dt.month, dt.day) in HOLIDAY_MD)


def load_sources() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    print("=" * 50)
    print("读取源数据")
    print("=" * 50)

    train = pd.read_csv(TRAIN_CSV, encoding="utf-8")
    products = pd.read_csv(PRODUCT_CSV, encoding="utf-8")
    categories = pd.read_csv(CATEGORY_CSV, encoding="utf-8")

    print(f"训练集: {len(train)} 行, 列={list(train.columns)}")
    print(f"商品信息: {len(products)} 行")
    print(f"类别列表: {len(categories)} 行")
    return train, products, categories


def build_causal_table(
    train: pd.DataFrame,
    products: pd.DataFrame,
    categories: pd.DataFrame,
) -> pd.DataFrame:
    """
    拼表并构造因果变量。

    输出列（与 AURA generate_causal_data 同构）：
      提及服务体验, 节假日, 图书品类, 好评
    """
    print("=" * 50)
    print("构造因果表")
    print("=" * 50)

    cat_map = dict(
        zip(
            categories["类别ID"].astype(str),
            categories["类别名称"].astype(str),
        )
    )

    products = products.copy()
    products["主类目ID"] = products["所属类别"].map(_primary_category_id)
    products["主类目名称"] = products["主类目ID"].map(
        lambda x: cat_map.get(str(x), "")
    )

    df = train.merge(
        products[["商品ID", "商品名称", "主类目ID", "主类目名称"]],
        on="商品ID",
        how="left",
    )

    text = (
        df["评论标题"].fillna("").astype(str)
        + " "
        + df["评论内容"].fillna("").astype(str)
    )

    treatment = text.map(lambda t: _contains_any(t, SERVICE_KEYWORDS))
    outcome = (pd.to_numeric(df["评分"], errors="coerce") >= GOOD_RATING_THRESHOLD).astype(
        int
    )
    holiday = df["评论时间戳"].map(_is_holiday)
    book_cate = df["主类目名称"].fillna("").astype(str).map(
        lambda name: _contains_any(name, BOOK_CATEGORY_KEYWORDS)
    )

    causal = pd.DataFrame(
        {
            "提及服务体验": treatment.astype(int),
            "节假日": holiday.astype(int),
            "图书品类": book_cate.astype(int),
            "好评": outcome.astype(int),
        }
    )

    # 附带 ID，方便排查；因果脚本可只读上面 4 列
    causal.insert(0, "数据ID", df["数据ID"].astype(str))
    causal.insert(1, "商品ID", df["商品ID"].astype(str))
    causal.insert(2, "主类目名称", df["主类目名称"].fillna("").astype(str))

    # 去掉无法判定好评的行（评分缺失）
    before = len(causal)
    causal = causal.dropna(subset=["好评"]).reset_index(drop=True)
    print(f"合并后: {before} → 有效 {len(causal)} 行")
    return causal


def print_summary(df: pd.DataFrame) -> None:
    cols = ["提及服务体验", "节假日", "图书品类", "好评"]
    print("\n因果核心列分布:")
    print(df[cols].apply(pd.Series.value_counts).fillna(0).astype(int))

    # 粗相关：未控制混杂时的均值差，仅作对照，不是因果效应
    t1 = df.loc[df["提及服务体验"] == 1, "好评"].mean()
    t0 = df.loc[df["提及服务体验"] == 0, "好评"].mean()
    if np.isfinite(t1) and np.isfinite(t0):
        print(f"\n未调整均值差 E[Y|T=1]-E[Y|T=0] ≈ {t1 - t0:.4f}")
        print(f"  T=1 好评率: {t1:.4f}")
        print(f"  T=0 好评率: {t0:.4f}")


def main() -> None:
    train, products, categories = load_sources()
    causal = build_causal_table(train, products, categories)

    PROCESSED.mkdir(parents=True, exist_ok=True)
    causal.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")

    print("=" * 50)
    print("转换完成")
    print("=" * 50)
    print("输出:", OUTPUT_CSV)
    print("形状:", causal.shape)
    print("列:", list(causal.columns))
    print(causal.head())
    print_summary(causal)
    print(
        "\nDoWhy 用法提示:\n"
        '  treatment="提及服务体验"\n'
        '  outcome="好评"\n'
        '  common_causes=["节假日", "图书品类"]'
    )


if __name__ == "__main__":
    main()
