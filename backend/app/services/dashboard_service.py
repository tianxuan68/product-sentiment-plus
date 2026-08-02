"""评价看板统计：情感 / 方面词 / 热门商品 / 类目 / 因果视角 / 时序。"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.biz import BizSentimentQuery
from app.services.causal_service import DEFAULT_SERVICE_KEYWORDS, _contains_any

_SENT_KEYS = ("positive", "neutral", "negative")


def _parse_keywords(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
        if isinstance(parsed, str) and parsed.strip():
            return [parsed.strip()]
    except Exception:
        pass
    parts = [p.strip() for p in str(raw).replace("、", ",").split(",")]
    return [p for p in parts if p]


def _norm_sentiment(raw: Optional[str]) -> str:
    key = str(raw or "").strip().lower()
    return key if key in _SENT_KEYS else "other"


def _product_label(row: BizSentimentQuery) -> str:
    name = (row.product_name or "").strip()
    if name:
        return name
    if row.product_id:
        return f"商品#{row.product_id[:6]}"
    return "未关联商品"


def _base_query(
    db: Session,
    *,
    product_id: Optional[str] = None,
    days: Optional[int] = None,
):
    q = db.query(BizSentimentQuery)
    if product_id and product_id.strip():
        q = q.filter(BizSentimentQuery.product_id == product_id.strip())
    if days and days > 0:
        since = datetime.now() - timedelta(days=days)
        q = q.filter(BizSentimentQuery.create_time >= since)
    return q


def _load_rows(
    db: Session,
    *,
    product_id: Optional[str] = None,
    days: Optional[int] = None,
) -> List[BizSentimentQuery]:
    return (
        _base_query(db, product_id=product_id, days=days)
        .order_by(BizSentimentQuery.create_time.asc())
        .all()
    )


def _summary_from_rows(rows: List[BizSentimentQuery]) -> Dict[str, Any]:
    total = len(rows)
    dist = {"positive": 0, "neutral": 0, "negative": 0, "other": 0}
    for row in rows:
        dist[_norm_sentiment(row.sentiment)] += 1
    return {
        "total": total,
        "positive": dist["positive"],
        "neutral": dist["neutral"],
        "negative": dist["negative"],
        "other": dist["other"],
        "positiveRate": round(dist["positive"] / total, 4) if total else 0.0,
        "negativeRate": round(dist["negative"] / total, 4) if total else 0.0,
    }


def _tag_top_from_rows(rows: List[BizSentimentQuery], limit: int = 10) -> Dict[str, Any]:
    limit = max(1, min(int(limit or 10), 50))
    counter: Counter[str] = Counter()
    for row in rows:
        for tag in _parse_keywords(row.keywords):
            counter[tag] += 1
    top = counter.most_common(limit)
    return {
        "labels": [name for name, _ in top],
        "values": [count for _, count in top],
        "items": [{"name": name, "count": count} for name, count in top],
        "totalReviews": len(rows),
    }


def _aspect_sentiment_from_rows(rows: List[BizSentimentQuery], limit: int = 8) -> Dict[str, Any]:
    limit = max(1, min(int(limit or 8), 20))
    tag_total: Counter[str] = Counter()
    matrix: Dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        sent = _norm_sentiment(row.sentiment)
        if sent == "other":
            continue
        for tag in _parse_keywords(row.keywords):
            tag_total[tag] += 1
            matrix[tag][sent] += 1
    labels = [name for name, _ in tag_total.most_common(limit)]
    return {
        "labels": labels,
        "series": [
            {"name": "正向", "key": "positive", "data": [matrix[t]["positive"] for t in labels]},
            {"name": "中性", "key": "neutral", "data": [matrix[t]["neutral"] for t in labels]},
            {"name": "负向", "key": "negative", "data": [matrix[t]["negative"] for t in labels]},
        ],
    }


def _service_lens_from_rows(rows: List[BizSentimentQuery]) -> Dict[str, Any]:
    groups = {
        "treated": {"positive": 0, "neutral": 0, "negative": 0, "total": 0},
        "control": {"positive": 0, "neutral": 0, "negative": 0, "total": 0},
    }
    for row in rows:
        text = f"{row.content or ''} {row.keywords or ''} {row.summary or ''}"
        bucket = "treated" if _contains_any(text, DEFAULT_SERVICE_KEYWORDS) else "control"
        sent = _norm_sentiment(row.sentiment)
        groups[bucket]["total"] += 1
        if sent in _SENT_KEYS:
            groups[bucket][sent] += 1

    def rates(g: Dict[str, int]) -> Dict[str, float]:
        t = g["total"] or 1
        return {
            "positiveRate": round(g["positive"] / t, 4),
            "neutralRate": round(g["neutral"] / t, 4),
            "negativeRate": round(g["negative"] / t, 4),
            "count": g["total"],
        }

    treated = rates(groups["treated"])
    control = rates(groups["control"])
    ate = None
    if groups["treated"]["total"] and groups["control"]["total"]:
        ate = round(treated["positiveRate"] - control["positiveRate"], 4)
    return {
        "categories": ["提及服务体验", "未提及服务体验"],
        "positiveRates": [treated["positiveRate"], control["positiveRate"]],
        "negativeRates": [treated["negativeRate"], control["negativeRate"]],
        "counts": [treated["count"], control["count"]],
        "ate": ate,
        "keywords": list(DEFAULT_SERVICE_KEYWORDS),
    }


def _daily_trend_from_rows(rows: List[BizSentimentQuery]) -> Dict[str, Any]:
    by_day: Dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        if not row.create_time:
            continue
        day = row.create_time.strftime("%Y-%m-%d")
        by_day[day][_norm_sentiment(row.sentiment)] += 1
    labels = sorted(by_day.keys())
    return {
        "labels": labels,
        "series": [
            {"name": "正向", "key": "positive", "data": [by_day[d]["positive"] for d in labels]},
            {"name": "中性", "key": "neutral", "data": [by_day[d]["neutral"] for d in labels]},
            {"name": "负向", "key": "negative", "data": [by_day[d]["negative"] for d in labels]},
        ],
    }


def _product_top_from_rows(rows: List[BizSentimentQuery], limit: int = 10) -> Dict[str, Any]:
    """最热商品 TopN：按评价条数。"""
    limit = max(1, min(int(limit or 10), 20))
    counts: Counter[str] = Counter()
    pos: Counter[str] = Counter()
    for row in rows:
        label = _product_label(row)
        counts[label] += 1
        if _norm_sentiment(row.sentiment) == "positive":
            pos[label] += 1
    top = counts.most_common(limit)
    labels = [name for name, _ in top]
    values = [count for _, count in top]
    return {
        "labels": labels,
        "values": values,
        "positiveRates": [round(pos[n] / counts[n], 4) if counts[n] else 0.0 for n in labels],
        "items": [
            {
                "name": name,
                "count": count,
                "positiveRate": round(pos[name] / count, 4) if count else 0.0,
            }
            for name, count in top
        ],
    }


def _product_sentiment_from_rows(rows: List[BizSentimentQuery], limit: int = 8) -> Dict[str, Any]:
    """各热门商品的评论情感分类（堆叠柱）。"""
    limit = max(1, min(int(limit or 8), 20))
    counts: Counter[str] = Counter()
    matrix: Dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        label = _product_label(row)
        sent = _norm_sentiment(row.sentiment)
        counts[label] += 1
        if sent in _SENT_KEYS:
            matrix[label][sent] += 1
    labels = [name for name, _ in counts.most_common(limit)]
    return {
        "labels": labels,
        "series": [
            {"name": "正向", "key": "positive", "data": [matrix[n]["positive"] for n in labels]},
            {"name": "中性", "key": "neutral", "data": [matrix[n]["neutral"] for n in labels]},
            {"name": "负向", "key": "negative", "data": [matrix[n]["negative"] for n in labels]},
        ],
    }


def _category_mix_from_rows(rows: List[BizSentimentQuery], limit: int = 8) -> Dict[str, Any]:
    """类目评价占比。"""
    limit = max(1, min(int(limit or 8), 20))
    counter: Counter[str] = Counter()
    for row in rows:
        name = (row.category_name or "").strip() or "未分类"
        counter[name] += 1
    top = counter.most_common(limit)
    return {
        "labels": [n for n, _ in top],
        "values": [c for _, c in top],
        "items": [{"name": n, "value": c} for n, c in top],
    }


def _aspect_radar_from_rows(rows: List[BizSentimentQuery], limit: int = 6) -> Dict[str, Any]:
    """方面关注雷达：Top 方面词的提及强度 + 正向占比。"""
    limit = max(3, min(int(limit or 6), 10))
    tag_total: Counter[str] = Counter()
    tag_pos: Counter[str] = Counter()
    for row in rows:
        sent = _norm_sentiment(row.sentiment)
        for tag in _parse_keywords(row.keywords):
            tag_total[tag] += 1
            if sent == "positive":
                tag_pos[tag] += 1
    labels = [n for n, _ in tag_total.most_common(limit)]
    max_c = max((tag_total[n] for n in labels), default=1) or 1
    mention = [round(tag_total[n] / max_c * 100, 1) for n in labels]
    positive = [round((tag_pos[n] / tag_total[n] * 100) if tag_total[n] else 0.0, 1) for n in labels]
    return {
        "indicators": [{"name": n, "max": 100} for n in labels],
        "series": [
            {"name": "提及强度", "data": mention},
            {"name": "正向占比", "data": positive},
        ],
    }


def tag_top(db: Session, *, limit: int = 10, product_id: Optional[str] = None, days: Optional[int] = None) -> Dict[str, Any]:
    return _tag_top_from_rows(_load_rows(db, product_id=product_id, days=days), limit)


def summary(db: Session, *, product_id: Optional[str] = None, days: Optional[int] = None) -> Dict[str, Any]:
    return _summary_from_rows(_load_rows(db, product_id=product_id, days=days))


def aspect_sentiment(
    db: Session, *, limit: int = 8, product_id: Optional[str] = None, days: Optional[int] = None
) -> Dict[str, Any]:
    return _aspect_sentiment_from_rows(_load_rows(db, product_id=product_id, days=days), limit)


def service_lens(db: Session, *, product_id: Optional[str] = None, days: Optional[int] = None) -> Dict[str, Any]:
    return _service_lens_from_rows(_load_rows(db, product_id=product_id, days=days))


def daily_trend(db: Session, *, product_id: Optional[str] = None, days: Optional[int] = None) -> Dict[str, Any]:
    return _daily_trend_from_rows(_load_rows(db, product_id=product_id, days=days))


def overview(
    db: Session,
    *,
    product_id: Optional[str] = None,
    days: Optional[int] = None,
    tag_limit: int = 10,
) -> Dict[str, Any]:
    rows = _load_rows(db, product_id=product_id, days=days)
    return {
        "summary": _summary_from_rows(rows),
        "tagTop": _tag_top_from_rows(rows, tag_limit),
        "aspectSentiment": _aspect_sentiment_from_rows(rows, 8),
        "serviceLens": _service_lens_from_rows(rows),
        "dailyTrend": _daily_trend_from_rows(rows),
        "productTop": _product_top_from_rows(rows, 10),
        "productSentiment": _product_sentiment_from_rows(rows, 8),
        "categoryMix": _category_mix_from_rows(rows, 8),
        "aspectRadar": _aspect_radar_from_rows(rows, 6),
    }
