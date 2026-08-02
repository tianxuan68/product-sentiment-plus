"""
案例:
    给前端 Insight 页用的聚合预测：情绪 + 标签关键词。

大白话:
    前端只要 sentiment/score/summary/keywords；这里把分层打标和情感分类拼成一份。
"""

# 导包
from api.services import predict_service, tag_service

# 前端商品类别 → 训练数据类目
_CATEGORY_ALIAS = {
    "电子产品": "手机/数码",
    "生活用品": "家居生活",
    "美妆个护": "美妆个护",
    "其他": "其他",
    "手机/数码": "手机/数码",
    "图书音像": "图书音像",
    "服饰服装": "服饰服装",
    "电脑/办公": "电脑/办公",
    "家用电器": "家用电器",
    "食品/保健": "食品/保健",
}


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


def _sentiment_label(pred: int, conf: float, text: str = ""):
    """二分类映射到前端三态；低置信或中性措辞 → neutral。"""
    if _looks_neutral(text):
        return "neutral"
    if conf is not None and conf < 0.55:
        return "neutral"
    return "positive" if int(pred) == 1 else "negative"


def _build_summary(sentiment: str, tags: list[str], category: str | None, product_name: str | None):
    tone = {"positive": "偏正向", "negative": "偏负向", "neutral": "偏中性"}.get(sentiment, "偏中性")
    who = product_name or category or "该商品"
    if tags:
        tag_txt = "、".join(tags[:6])
        return f"针对{who}的反馈整体{tone}；模型识别到的方面标签：{tag_txt}。"
    return f"针对{who}的反馈整体{tone}；未识别到明确方面标签，可补充更具体的评价内容。"


def _keywords_aligned(tag_out: dict, sentiment: str) -> list[str]:
    """keywords 与整体情绪对齐，避免负向文案出现「会回购」等正向标签。"""
    tags = list(tag_out.get("tags") or [])
    names = [str(t.get("tag") or "").strip() for t in tags if t.get("tag")]
    if not names:
        return [str(x).strip() for x in (tag_out.get("tag_names") or []) if str(x).strip()]

    if sentiment == "positive":
        want = {"positive", "pos"}
    elif sentiment == "negative":
        want = {"negative", "neg"}
    else:
        return names[:8]

    filtered = [
        str(t.get("tag")).strip()
        for t in tags
        if str(t.get("polarity") or "").strip().lower() in want and t.get("tag")
    ]
    return (filtered or names)[:8]


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
    # 中性时置信度用与 0.5 的距离，避免页面上出现「中性 96%」的违和感
    if sentiment == "neutral":
        score = int(round(max(0.0, 1.0 - abs(conf - 0.5) * 2) * 55 + 40))
    else:
        score = int(round(conf * 100))
    score = max(0, min(100, score))

    keywords = _keywords_aligned(tag_out, sentiment)

    summary = _build_summary(
        sentiment,
        keywords,
        tag_out.get("category") or mapped_cat,
        product_name or tag_out.get("product_name"),
    )

    print(
        f'前端聚合预测 model={sentiment_model} sentiment={sentiment} '
        f'score={score} tags={keywords[:5]}'
    )
    return {
        "sentiment": sentiment,
        "score": score,
        "summary": summary,
        "keywords": keywords,
    }
