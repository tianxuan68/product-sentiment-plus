"""评价看板统计：情感 / 方面词 / 热门商品 / 类目 / 因果视角 / 时序。

性能要点：一次轻量列查询 + 单遍扫描，避免 ORM 全表 hydrate 与多次遍历。
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, NamedTuple, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.biz import BizSentimentQuery
from app.services.causal_service import DEFAULT_SERVICE_KEYWORDS, _contains_any

_SENT_KEYS = ("positive", "neutral", "negative")


class _LightRow(NamedTuple):
    product_id: Optional[str]
    product_name: Optional[str]
    category_name: Optional[str]
    content: Optional[str]
    sentiment: Optional[str]
    keywords: Optional[str]
    summary: Optional[str]
    create_time: Optional[datetime]


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


def _product_label(row: _LightRow) -> str:
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
) -> List[_LightRow]:
    rows = (
        _base_query(db, product_id=product_id, days=days)
        .with_entities(
            BizSentimentQuery.product_id,
            BizSentimentQuery.product_name,
            BizSentimentQuery.category_name,
            BizSentimentQuery.content,
            BizSentimentQuery.sentiment,
            BizSentimentQuery.keywords,
            BizSentimentQuery.summary,
            BizSentimentQuery.create_time,
        )
        .all()
    )
    return [_LightRow(*r) for r in rows]


def _summary_from_rows(rows: Iterable[_LightRow]) -> Dict[str, Any]:
    dist = {"positive": 0, "neutral": 0, "negative": 0, "other": 0}
    total = 0
    for row in rows:
        total += 1
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


def _sql_summary(
    db: Session,
    *,
    product_id: Optional[str] = None,
    days: Optional[int] = None,
) -> Dict[str, Any]:
    """情感汇总走 SQL GROUP BY，避免全表进 Python。"""
    q = _base_query(db, product_id=product_id, days=days).with_entities(
        BizSentimentQuery.sentiment, func.count()
    ).group_by(BizSentimentQuery.sentiment)
    dist = {"positive": 0, "neutral": 0, "negative": 0, "other": 0}
    total = 0
    for sent, cnt in q.all():
        key = _norm_sentiment(sent)
        dist[key] += int(cnt or 0)
        total += int(cnt or 0)
    return {
        "total": total,
        "positive": dist["positive"],
        "neutral": dist["neutral"],
        "negative": dist["negative"],
        "other": dist["other"],
        "positiveRate": round(dist["positive"] / total, 4) if total else 0.0,
        "negativeRate": round(dist["negative"] / total, 4) if total else 0.0,
    }


def _build_overview_payload(rows: List[_LightRow], tag_limit: int = 10) -> Dict[str, Any]:
    """单遍扫描生成看板全部图所需数据。"""
    tag_limit = max(1, min(int(tag_limit or 10), 50))
    dist = {"positive": 0, "neutral": 0, "negative": 0, "other": 0}
    tag_counter: Counter[str] = Counter()
    tag_matrix: Dict[str, Counter[str]] = defaultdict(Counter)
    tag_pos: Counter[str] = Counter()
    product_counts: Counter[str] = Counter()
    product_matrix: Dict[str, Counter[str]] = defaultdict(Counter)
    category_counter: Counter[str] = Counter()
    by_day: Dict[str, Counter[str]] = defaultdict(Counter)
    lens = {
        "treated": {"positive": 0, "neutral": 0, "negative": 0, "total": 0},
        "control": {"positive": 0, "neutral": 0, "negative": 0, "total": 0},
    }

    for row in rows:
        sent = _norm_sentiment(row.sentiment)
        dist[sent] += 1

        label = _product_label(row)
        product_counts[label] += 1
        if sent in _SENT_KEYS:
            product_matrix[label][sent] += 1

        cat = (row.category_name or "").strip() or "未分类"
        category_counter[cat] += 1

        if row.create_time:
            # 历史跨年数据按月聚合，避免前端画几千个点卡死
            day = row.create_time.strftime("%Y-%m")
            by_day[day][sent] += 1

        tags = _parse_keywords(row.keywords)
        for tag in tags:
            tag_counter[tag] += 1
            if sent in _SENT_KEYS:
                tag_matrix[tag][sent] += 1
            if sent == "positive":
                tag_pos[tag] += 1

        text = f"{row.content or ''} {row.keywords or ''} {row.summary or ''}"
        bucket = "treated" if _contains_any(text, DEFAULT_SERVICE_KEYWORDS) else "control"
        lens[bucket]["total"] += 1
        if sent in _SENT_KEYS:
            lens[bucket][sent] += 1

    total = sum(dist.values())
    summary = {
        "total": total,
        "positive": dist["positive"],
        "neutral": dist["neutral"],
        "negative": dist["negative"],
        "other": dist["other"],
        "positiveRate": round(dist["positive"] / total, 4) if total else 0.0,
        "negativeRate": round(dist["negative"] / total, 4) if total else 0.0,
    }

    top_tags = tag_counter.most_common(tag_limit)
    tag_labels = [n for n, _ in top_tags]
    tag_top = {
        "labels": tag_labels,
        "values": [c for _, c in top_tags],
        "items": [{"name": n, "count": c} for n, c in top_tags],
        "totalReviews": total,
    }

    aspect_labels = [n for n, _ in tag_counter.most_common(8)]
    aspect_sentiment = {
        "labels": aspect_labels,
        "series": [
            {"name": "正向", "key": "positive", "data": [tag_matrix[t]["positive"] for t in aspect_labels]},
            {"name": "中性", "key": "neutral", "data": [tag_matrix[t]["neutral"] for t in aspect_labels]},
            {"name": "负向", "key": "negative", "data": [tag_matrix[t]["negative"] for t in aspect_labels]},
        ],
    }

    def _rates(g: Dict[str, int]) -> Dict[str, float]:
        t = g["total"] or 1
        return {
            "positiveRate": round(g["positive"] / t, 4),
            "neutralRate": round(g["neutral"] / t, 4),
            "negativeRate": round(g["negative"] / t, 4),
            "count": g["total"],
        }

    treated = _rates(lens["treated"])
    control = _rates(lens["control"])
    ate = None
    if lens["treated"]["total"] and lens["control"]["total"]:
        ate = round(treated["positiveRate"] - control["positiveRate"], 4)
    service_lens = {
        "categories": ["提及服务体验", "未提及服务体验"],
        "positiveRates": [treated["positiveRate"], control["positiveRate"]],
        "negativeRates": [treated["negativeRate"], control["negativeRate"]],
        "counts": [treated["count"], control["count"]],
        "ate": ate,
        "keywords": list(DEFAULT_SERVICE_KEYWORDS),
    }

    day_labels = sorted(by_day.keys())
    daily_trend = {
        "labels": day_labels,
        "series": [
            {"name": "正向", "key": "positive", "data": [by_day[d]["positive"] for d in day_labels]},
            {"name": "中性", "key": "neutral", "data": [by_day[d]["neutral"] for d in day_labels]},
            {"name": "负向", "key": "negative", "data": [by_day[d]["negative"] for d in day_labels]},
        ],
    }

    top_products = product_counts.most_common(10)
    product_labels = [n for n, _ in top_products]
    product_top = {
        "labels": product_labels,
        "values": [c for _, c in top_products],
        "positiveRates": [
            round(product_matrix[n]["positive"] / product_counts[n], 4) if product_counts[n] else 0.0
            for n in product_labels
        ],
        "items": [
            {
                "name": name,
                "count": count,
                "positiveRate": round(product_matrix[name]["positive"] / count, 4) if count else 0.0,
            }
            for name, count in top_products
        ],
    }

    sent_labels = [n for n, _ in product_counts.most_common(8)]
    product_sentiment = {
        "labels": sent_labels,
        "series": [
            {"name": "正向", "key": "positive", "data": [product_matrix[n]["positive"] for n in sent_labels]},
            {"name": "中性", "key": "neutral", "data": [product_matrix[n]["neutral"] for n in sent_labels]},
            {"name": "负向", "key": "negative", "data": [product_matrix[n]["negative"] for n in sent_labels]},
        ],
    }

    cat_top = category_counter.most_common(8)
    category_mix = {
        "labels": [n for n, _ in cat_top],
        "values": [c for _, c in cat_top],
        "items": [{"name": n, "value": c} for n, c in cat_top],
    }

    radar_labels = [n for n, _ in tag_counter.most_common(6)]
    max_c = max((tag_counter[n] for n in radar_labels), default=1) or 1
    aspect_radar = {
        "indicators": [{"name": n, "max": 100} for n in radar_labels],
        "series": [
            {
                "name": "提及强度",
                "data": [round(tag_counter[n] / max_c * 100, 1) for n in radar_labels],
            },
            {
                "name": "正向占比",
                "data": [
                    round((tag_pos[n] / tag_counter[n] * 100) if tag_counter[n] else 0.0, 1)
                    for n in radar_labels
                ],
            },
        ],
    }

    return {
        "summary": summary,
        "tagTop": tag_top,
        "aspectSentiment": aspect_sentiment,
        "serviceLens": service_lens,
        "dailyTrend": daily_trend,
        "productTop": product_top,
        "productSentiment": product_sentiment,
        "categoryMix": category_mix,
        "aspectRadar": aspect_radar,
    }


def _tag_top_from_rows(rows: List[_LightRow], limit: int = 10) -> Dict[str, Any]:
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


def _aspect_sentiment_from_rows(rows: List[_LightRow], limit: int = 8) -> Dict[str, Any]:
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


def _service_lens_from_rows(rows: List[_LightRow]) -> Dict[str, Any]:
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


def _daily_trend_from_rows(rows: List[_LightRow]) -> Dict[str, Any]:
    by_day: Dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        if not row.create_time:
            continue
        day = row.create_time.strftime("%Y-%m")
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


def _product_top_from_rows(rows: List[_LightRow], limit: int = 10) -> Dict[str, Any]:
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


def _product_sentiment_from_rows(rows: List[_LightRow], limit: int = 8) -> Dict[str, Any]:
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


def _category_mix_from_rows(rows: List[_LightRow], limit: int = 8) -> Dict[str, Any]:
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


def _aspect_radar_from_rows(rows: List[_LightRow], limit: int = 6) -> Dict[str, Any]:
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
    return _sql_summary(db, product_id=product_id, days=days)


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
    return _build_overview_payload(rows, tag_limit=tag_limit)
