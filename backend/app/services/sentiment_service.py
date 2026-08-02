"""
评论分析：对接 product-sentiment-ai，组装前端 Insight 所需字段。
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_PRODUCT_DRAFTS: dict[str, Any] = {}


def _mock_predict(content: str, product: Optional[dict] = None) -> dict:
    text = content or ""
    neg_words = ("差", "坏", "慢", "假", "坑", "后悔", "破损", "不推荐")
    pos_words = ("好", "快", "棒", "推荐", "喜欢", "满意", "不错")
    neg = sum(1 for w in neg_words if w in text)
    pos = sum(1 for w in pos_words if w in text)
    if neg > pos:
        sentiment, score = "negative", 72
    elif pos > neg:
        sentiment, score = "positive", 78
    else:
        sentiment, score = "neutral", 55
    keywords = []
    for w in ("质量好", "质量差", "发货快", "物流慢", "包装差", "性价比高", "不推荐", "会回购"):
        # 粗匹配：去掉「好/差」等后的主干
        stem = w[:2]
        if stem in text or w in text:
            keywords.append(w)
    if not keywords:
        keywords = ["等待模型", "接口预留"] if settings.sentiment_ai_mock else []
    name = (product or {}).get("name") or "该商品"
    tone = {"positive": "偏正向", "negative": "偏负向", "neutral": "偏中性"}[sentiment]
    summary = f"针对{name}的反馈整体{tone}（Mock）。关键词：{'、'.join(keywords[:5])}。"
    return {
        "sentiment": sentiment,
        "score": score,
        "summary": summary,
        "keywords": keywords[:8],
    }


def predict(content: str, product_id: Optional[str] = None, product: Optional[dict] = None) -> dict:
    content = (content or "").strip()
    if not content:
        raise ValueError("content 不能为空")

    if settings.sentiment_ai_mock:
        logger.info("sentiment mock predict len=%s", len(content))
        return _mock_predict(content, product)

    url = settings.sentiment_ai_base_url.rstrip("/") + "/api/front/predict"
    payload = {
        "content": content,
        "productId": product_id,
        "product": product,
    }
    timeout = settings.sentiment_ai_timeout
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=payload)
        if resp.status_code >= 400:
            logger.warning("sentiment-ai error %s: %s", resp.status_code, resp.text[:300])
            raise RuntimeError(f"sentiment-ai 返回 {resp.status_code}")
        data = resp.json()
        # 兼容：直接返回 / {result|data: {...}}
        if isinstance(data, dict) and "sentiment" not in data:
            nested = data.get("result") or data.get("data")
            if isinstance(nested, dict):
                data = nested
        if isinstance(data, dict) and "sentiment" in data:
            sentiment = data.get("sentiment") or "neutral"
            if sentiment not in {"positive", "neutral", "negative"}:
                sentiment = "neutral"
            try:
                score = int(round(float(data.get("score") or 0)))
            except (TypeError, ValueError):
                score = 0
            score = max(0, min(100, score))
            keywords = [str(k) for k in (data.get("keywords") or []) if str(k).strip()]
            return {
                "sentiment": sentiment,
                "score": score,
                "summary": str(data.get("summary") or ""),
                "keywords": keywords,
            }
        raise RuntimeError("sentiment-ai 响应缺少 sentiment 字段")
    except Exception as exc:
        logger.exception("调用 sentiment-ai 失败，回退 mock: %s", exc)
        out = _mock_predict(content, product)
        out["summary"] = f"（模型服务暂不可用，已降级）{out['summary']}"
        return out


def save_product_draft(product: dict, user_key: str = "anon") -> dict:
    _PRODUCT_DRAFTS[user_key] = product or {}
    logger.info("保存商品草稿 user=%s keys=%s", user_key, list((product or {}).keys()))
    return {"ok": True, "saved": True}
