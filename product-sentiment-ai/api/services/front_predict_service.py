"""
案例:
    给前端 Insight 页用的聚合预测：情绪 + 标签关键词。

大白话:
    前端只要 sentiment/score/summary/keywords；这里把分层打标和情感分类拼成一份。
    混合评价（又有好又有差）要同时保留正负方面标签，不能按整句情绪把另一半滤掉。
"""

# 导包
from api.services import predict_service, tag_service

# 前端商品类别 → 训练数据类目（与 reviews_train.csv 对齐）
_TRAIN_CATEGORIES = (
    "图书音像",
    "电脑/办公",
    "手机/数码",
    "美妆个护",
    "家用电器",
    "家居生活",
    "其他",
    "母婴/玩具",
    "家具/家装/建材",
    "钟表/首饰/眼镜/礼品",
    "食品/保健",
    "鞋类箱包",
    "运动户外",
    "服饰服装",
    "机票/充值/票务/虚拟",
)
_CATEGORY_ALIAS = {c: c for c in _TRAIN_CATEGORIES}

# 转折/对比：整句二分类容易一边倒，优先看方面标签是否正负并存
_CONTRAST_CUES = (
    "但是",
    "但",
    "不过",
    "可是",
    "然而",
    "虽然",
    "就是",
    "美中不足",
    "唯一",
)


def _map_category(raw):
    raw = (raw or "").strip()
    if not raw:
        return None
    return _CATEGORY_ALIAS.get(raw, raw)


_NEUTRAL_CUES = (
    "一般般",
    "一般",
    "还行",
    "凑合",
    "中规中矩",
    "没什么特别",
    "没有特别",
    "普通",
    "马马虎虎",
    "不好不坏",
)


def _looks_neutral(text: str) -> bool:
    t = text or ""
    return any(c in t for c in _NEUTRAL_CUES)


def _looks_contrast(text: str) -> bool:
    t = text or ""
    return any(c in t for c in _CONTRAST_CUES)


def _sentiment_label(pred: int, conf: float, text: str = ""):
    """二分类映射到前端三态；低置信或中性措辞 → neutral。"""
    if _looks_neutral(text):
        return "neutral"
    if conf is not None and conf < 0.55:
        return "neutral"
    return "positive" if int(pred) == 1 else "negative"


def _tag_polarity(tag: dict) -> str:
    return str(tag.get("polarity") or "").strip().lower()


def _collect_keywords(tag_out: dict) -> tuple[list[str], list[str], list[str]]:
    """返回 (全部标签名, 正向, 负向)，方面标签正负都保留。"""
    tags = list(tag_out.get("tags") or [])
    pos, neg, names = [], [], []
    seen = set()
    for t in tags:
        name = str(t.get("tag") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
        pol = _tag_polarity(t)
        if pol in {"positive", "pos"}:
            pos.append(name)
        elif pol in {"negative", "neg"}:
            neg.append(name)
    if not names:
        names = [str(x).strip() for x in (tag_out.get("tag_names") or []) if str(x).strip()]
    return names[:8], pos, neg


def _build_summary(
    sentiment: str,
    keywords: list[str],
    pos_tags: list[str],
    neg_tags: list[str],
    category: str | None,
    product_name: str | None,
):
    who = product_name or category or "该商品"
    if pos_tags and neg_tags:
        return (
            f"针对{who}的反馈正负并存："
            f"正向方面「{'、'.join(pos_tags[:4])}」，"
            f"负向方面「{'、'.join(neg_tags[:4])}」。"
        )
    tone = {"positive": "偏正向", "negative": "偏负向", "neutral": "偏中性"}.get(
        sentiment, "偏中性"
    )
    if keywords:
        tag_txt = "、".join(keywords[:6])
        return f"针对{who}的反馈整体{tone}；模型识别到的方面标签：{tag_txt}。"
    return f"针对{who}的反馈整体{tone}；未识别到明确方面标签，可补充更具体的评价内容。"


def predict_for_front(content: str, product_id: str | None = None, product: dict | None = None):
    text = (content or "").strip()
    if not text:
        raise ValueError("content 不能为空")

    product = product or {}
    mapped_cat = _map_category(product.get("category"))
    product_name = (product.get("name") or "").strip() or None
    pid = (product_id or "").strip() or None

    # 1) 标准短标签（与 /api/tag/one 默认一致）
    tag_out = tag_service.predict_tags(
        text,
        product_id=pid or "DRAFT",
        method="model",
        category=mapped_cat,
        product_name=product_name,
    )
    keywords, pos_tags, neg_tags = _collect_keywords(tag_out)

    # 2) 情感二分类（有 BERT 用 BERT，否则 fasttext）
    sentiment_model = "bert"
    try:
        sent = predict_service.predict_one(text, model=sentiment_model)
    except FileNotFoundError:
        try:
            sent = predict_service.predict_one(text, model="fasttext")
            sentiment_model = "fasttext"
        except FileNotFoundError:
            sent = predict_service.predict_one(text, model="baseline")
            sentiment_model = "baseline"

    conf = sent.get("confidence")
    if conf is None:
        conf = max(sent.get("prob_pos") or 0.0, sent.get("prob_neg") or 0.0)
    conf = float(conf or 0.0)
    sentiment = _sentiment_label(int(sent.get("pred", 0)), conf, text)

    # 方面标签正负并存，或文案有明显转折 → 整句标成中性（混合），避免「正向 100%」盖住差评点
    if pos_tags and neg_tags:
        sentiment = "neutral"
        conf = 0.55
    elif _looks_contrast(text) and (pos_tags or neg_tags) and sentiment in {"positive", "negative"}:
        # 有转折但只打出一侧标签时，略降置信，提示勿过度解读整句
        conf = min(conf, 0.72)

    if sentiment == "neutral":
        score = int(round(max(0.0, 1.0 - abs(conf - 0.5) * 2) * 55 + 40))
    else:
        score = int(round(conf * 100))
    score = max(0, min(100, score))

    summary = _build_summary(
        sentiment,
        keywords,
        pos_tags,
        neg_tags,
        tag_out.get("category") or mapped_cat,
        product_name or tag_out.get("product_name"),
    )

    print(
        f'前端聚合预测 model={sentiment_model} sentiment={sentiment} '
        f'score={score} tags={keywords[:5]} pos={pos_tags[:3]} neg={neg_tags[:3]}'
    )
    return {
        "sentiment": sentiment,
        "score": score,
        "summary": summary,
        "keywords": keywords,
    }
