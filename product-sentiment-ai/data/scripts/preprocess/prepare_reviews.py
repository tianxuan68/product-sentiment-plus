"""
从 sources 只读整理评论主表，写入 processed（不修改任何源文件）。

清洗要点（针对标签噪声与脏文本）：
  1) 文本规范化：去 HTML/URL、压空白、压缩重复标点/叠字
  2) 丢弃中性分（评分=3），只保留明确好评(4-5)与差评(1-2)
  3) 过滤过短/无中文/纯符号垃圾句
  4) 按 sentence 去重，避免同文多标签干扰

产出：
  processed/reviews.csv
  processed/reviews_train.csv
  processed/reviews_val.csv
  processed/reviews_test.csv

用法：
  python prepare_reviews.py
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ROOT / "sources"
PROCESSED = ROOT / "processed"

TRAIN_CSV = SOURCES / "训练集.csv"
TEST_CSV = SOURCES / "测试集.csv"
PRODUCT_CSV = SOURCES / "商品信息.csv"
CATEGORY_CSV = SOURCES / "商品类别列表.csv"

OUT_ALL = PROCESSED / "reviews.csv"
OUT_TRAIN = PROCESSED / "reviews_train.csv"
OUT_VAL = PROCESSED / "reviews_val.csv"
OUT_TEST = PROCESSED / "reviews_test.csv"

RANDOM_STATE = 42
VAL_RATIO = 0.1
# 二分类只用明确极性：>=4 好评，<=2 差评；=3 中性丢弃
POS_RATING_MIN = 4.0
NEG_RATING_MAX = 2.0
MIN_TEXT_LEN = 6
MIN_CN_CHARS = 2


_RE_HTML = re.compile(r"<[^>]+>")
_RE_URL = re.compile(r"https?://\S+|www\.\S+", re.I)
_RE_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_RE_WHITESPACE = re.compile(r"\s+")
_RE_REPEAT_PUNCT = re.compile(r"([!?。！？~～…,.，、])\1{1,}")
_RE_REPEAT_CHAR = re.compile(r"(.)\1{4,}")
_RE_CN = re.compile(r"[\u4e00-\u9fff]")
_RE_JUNK_ONLY = re.compile(r"^[\W\d_]+$", re.UNICODE)


def file_md5(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def snapshot_sources() -> dict[str, str]:
    files = [TRAIN_CSV, TEST_CSV, PRODUCT_CSV, CATEGORY_CSV]
    return {str(p): file_md5(p) for p in files if p.exists()}


def assert_sources_unchanged(before: dict[str, str]) -> None:
    after = snapshot_sources()
    if before != after:
        raise RuntimeError("检测到 sources 被改动，已中止。请检查是否误写了源文件。")
    print("校验通过: sources 未被修改")


def primary_category_id(raw: object) -> str:
    if pd.isna(raw):
        return ""
    parts = str(raw).split(",")
    return parts[0].strip() if parts else ""


def clean_text(text: object) -> str:
    """单条评论文本清洗。"""
    if pd.isna(text):
        return ""
    s = str(text)
    s = _RE_HTML.sub(" ", s)
    s = _RE_URL.sub(" ", s)
    s = _RE_EMAIL.sub(" ", s)
    # 全角空格等
    s = s.replace("\u3000", " ").replace("\xa0", " ")
    s = _RE_WHITESPACE.sub(" ", s).strip()
    s = _RE_REPEAT_PUNCT.sub(r"\1\1", s)
    # 哈哈哈哈哈 → 哈哈；!!!! → !!
    s = _RE_REPEAT_CHAR.sub(r"\1\1\1", s)
    return s.strip()


def build_sentence(title: object, content: object) -> str:
    t = clean_text(title)
    c = clean_text(content)
    if t and c:
        # 标题与正文完全相同只留一份
        if t == c:
            return t
        return f"{t}。{c}"
    return t or c


def is_valid_sentence(text: str) -> bool:
    if not text or len(text) < MIN_TEXT_LEN:
        return False
    if _RE_JUNK_ONLY.match(text):
        return False
    if len(_RE_CN.findall(text)) < MIN_CN_CHARS:
        return False
    return True


def rating_to_sentiment(rating: float) -> int | None:
    """明确极性才给标签；中性返回 None 表示丢弃。"""
    if pd.isna(rating):
        return None
    if rating >= POS_RATING_MIN:
        return 1
    if rating <= NEG_RATING_MAX:
        return 0
    return None


def load_category_map() -> dict[str, str]:
    cate = pd.read_csv(CATEGORY_CSV, encoding="utf-8")
    return dict(
        zip(cate["类别ID"].astype(str), cate["类别名称"].astype(str))
    )


def load_product_table(cat_map: dict[str, str]) -> pd.DataFrame:
    products = pd.read_csv(PRODUCT_CSV, encoding="utf-8")
    products["主类目ID"] = products["所属类别"].map(primary_category_id)
    products["category"] = products["主类目ID"].map(
        lambda x: cat_map.get(str(x), "未知")
    )
    return products[["商品ID", "商品名称", "主类目ID", "category"]]


def _base_frame(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "review_id": df["数据ID"].astype(str),
            "user_id": df["用户ID"],
            "product_id": df["商品ID"].astype(str),
            "product_name": df["商品名称"].fillna("").astype(str),
            "category_id": df["主类目ID"].fillna("").astype(str),
            "category": df["category"].astype(str),
            "timestamp": df["评论时间戳"],
            "title": df["评论标题"].map(clean_text),
            "content": df["评论内容"].map(clean_text),
            "sentence": df["sentence"].astype(str),
        }
    )


def prepare_train(products: pd.DataFrame) -> pd.DataFrame:
    print("读取训练集...")
    train = pd.read_csv(TRAIN_CSV, encoding="utf-8")
    raw_n = len(train)
    print(f"  原始行数: {raw_n}")

    df = train.merge(products, on="商品ID", how="left")
    df["category"] = df["category"].fillna("未知")
    df["sentence"] = [
        build_sentence(t, c) for t, c in zip(df["评论标题"], df["评论内容"])
    ]
    df["rating"] = pd.to_numeric(df["评分"], errors="coerce")
    df["sentiment"] = df["rating"].map(rating_to_sentiment)

    out = _base_frame(df)
    out["rating"] = df["rating"].values
    out["sentiment"] = df["sentiment"].values

    stats = {"raw": raw_n}

    # 1) 丢弃无评分 / 中性分
    before = len(out)
    out = out.dropna(subset=["sentiment", "rating"]).copy()
    out["sentiment"] = out["sentiment"].astype(int)
    stats["drop_neutral_or_nan"] = before - len(out)
    print(f"  去掉中性/无效评分: {before} → {len(out)} (−{stats['drop_neutral_or_nan']})")

    # 2) 文本合法性
    before = len(out)
    out = out[out["sentence"].map(is_valid_sentence)].copy()
    stats["drop_invalid_text"] = before - len(out)
    print(f"  去掉过短/无中文/纯符号: {before} → {len(out)} (−{stats['drop_invalid_text']})")

    # 3) sentence 去重（保留首条）
    before = len(out)
    out = out.drop_duplicates(subset=["sentence"], keep="first").copy()
    stats["drop_dup_sentence"] = before - len(out)
    print(f"  按 sentence 去重: {before} → {len(out)} (−{stats['drop_dup_sentence']})")

    # 4) review_id 去重兜底
    before = len(out)
    out = out.drop_duplicates(subset=["review_id"], keep="first").copy()
    stats["drop_dup_id"] = before - len(out)
    if stats["drop_dup_id"]:
        print(f"  按 review_id 去重: {before} → {len(out)} (−{stats['drop_dup_id']})")

    stats["kept"] = len(out)
    stats["pos_rate"] = float(out["sentiment"].mean()) if len(out) else 0.0
    print(
        f"  清洗完成: {raw_n} → {len(out)} "
        f"(保留 {len(out) / raw_n:.1%}) | 好评率={stats['pos_rate']:.4f}"
    )
    print(
        f"  标签分布: 好评={(out['sentiment']==1).sum()} "
        f"差评={(out['sentiment']==0).sum()}"
    )
    return out.reset_index(drop=True)


def prepare_test(products: pd.DataFrame) -> pd.DataFrame:
    print("读取官方测试集...")
    test = pd.read_csv(TEST_CSV, encoding="utf-8")
    print(f"  原始行数: {len(test)}")

    df = test.merge(products, on="商品ID", how="left")
    df["category"] = df["category"].fillna("未知")
    df["sentence"] = [
        build_sentence(t, c) for t, c in zip(df["评论标题"], df["评论内容"])
    ]

    out = _base_frame(df)
    before = len(out)
    # 测试集不做标签过滤，但仍做文本清洗与合法性过滤，避免脏输入
    out = out[out["sentence"].map(is_valid_sentence)].copy()
    out = out.drop_duplicates(subset=["review_id"], keep="first").copy()
    print(f"  清洗后: {before} → {len(out)}")
    return out.reset_index(drop=True)


def split_train_val(reviews: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    try:
        train_df, val_df = train_test_split(
            reviews,
            test_size=VAL_RATIO,
            random_state=RANDOM_STATE,
            stratify=reviews["sentiment"],
        )
    except ValueError as e:
        print(f"警告: 分层划分失败({e})，改为普通划分")
        train_df, val_df = train_test_split(
            reviews,
            test_size=VAL_RATIO,
            random_state=RANDOM_STATE,
        )
    return (
        train_df.reset_index(drop=True),
        val_df.reset_index(drop=True),
    )


def verify(
    reviews: pd.DataFrame,
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
) -> None:
    print("=" * 50)
    print("数据校验")
    print("=" * 50)

    required = {
        "review_id",
        "product_id",
        "category",
        "sentence",
        "sentiment",
        "rating",
    }
    missing = required - set(reviews.columns)
    assert not missing, f"reviews 缺列: {missing}"

    assert reviews["review_id"].is_unique, "review_id 有重复"
    assert reviews["sentence"].is_unique, "sentence 仍有重复"
    assert reviews["sentence"].map(is_valid_sentence).all(), "存在非法 sentence"
    assert set(reviews["sentiment"].unique()) <= {0, 1}, "sentiment 只能是 0/1"
    assert not ((reviews["rating"] > NEG_RATING_MAX) & (reviews["rating"] < POS_RATING_MIN)).any(), (
        "仍存在中性评分样本"
    )
    assert ((reviews["rating"] <= NEG_RATING_MAX) | (reviews["rating"] >= POS_RATING_MIN)).all()
    assert len(train_df) + len(val_df) == len(reviews), "train+val 数量不等于全量"
    assert set(train_df["review_id"]).isdisjoint(set(val_df["review_id"])), "train/val 有交叉"

    all_pos = reviews["sentiment"].mean()
    tr_pos = train_df["sentiment"].mean()
    va_pos = val_df["sentiment"].mean()
    assert abs(tr_pos - all_pos) < 0.02, f"train 正样本比例偏离过大: {tr_pos} vs {all_pos}"
    assert abs(va_pos - all_pos) < 0.02, f"val 正样本比例偏离过大: {va_pos} vs {all_pos}"

    assert test_df["review_id"].is_unique, "测试集 review_id 有重复"
    assert "sentiment" not in test_df.columns, "官方测试集不应含 sentiment"

    print(f"全量: {len(reviews)} | train: {len(train_df)} | val: {len(val_df)} | test: {len(test_df)}")
    print(f"好评率: all={all_pos:.4f} train={tr_pos:.4f} val={va_pos:.4f}")
    print(f"品类数: {reviews['category'].nunique()}")
    print(f"商品数: {reviews['product_id'].nunique()}")
    print("评分分布:")
    print(reviews["rating"].value_counts().sort_index())
    print("样例:")
    print(reviews[["review_id", "product_id", "category", "rating", "sentiment", "sentence"]].head(3))
    print("校验通过: 清洗规则与切分均正确")


def main() -> None:
    print("=" * 50)
    print("准备评论主表（加强清洗，sources 只读）")
    print("=" * 50)
    print(
        f"规则: 好评 rating>={POS_RATING_MIN} | "
        f"差评 rating<={NEG_RATING_MAX} | "
        f"中性(3分)丢弃 | 最短{MIN_TEXT_LEN}字 | 至少{MIN_CN_CHARS}个汉字"
    )

    before = snapshot_sources()
    print("sources MD5 快照已记录")

    cat_map = load_category_map()
    products = load_product_table(cat_map)
    print(f"商品表: {len(products)} | 类别映射: {len(cat_map)}")

    reviews = prepare_train(products)
    test_df = prepare_test(products)
    train_df, val_df = split_train_val(reviews)

    PROCESSED.mkdir(parents=True, exist_ok=True)
    reviews.to_csv(OUT_ALL, index=False, encoding="utf-8-sig")
    train_df.to_csv(OUT_TRAIN, index=False, encoding="utf-8-sig")
    val_df.to_csv(OUT_VAL, index=False, encoding="utf-8-sig")
    test_df.to_csv(OUT_TEST, index=False, encoding="utf-8-sig")

    print("=" * 50)
    print("已写入 processed（未改 sources）")
    print("=" * 50)
    for p in (OUT_ALL, OUT_TRAIN, OUT_VAL, OUT_TEST):
        print(f"  {p.name}: {p.stat().st_size} bytes")

    verify(reviews, train_df, val_df, test_df)
    assert_sources_unchanged(before)


if __name__ == "__main__":
    main()
