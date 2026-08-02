"""
因果分析：按类目拉取评价 → 调 AI prepare/analyze → 落库结果表。
AI 不可用时本地按类目粗估计兜底。
"""
from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence, Tuple

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.biz import BizCausalResult, BizSentimentQuery
from app.schemas.response import PageResult
from app.utils.common import model_to_dict, new_id, paginate_query

logger = logging.getLogger(__name__)

DEFAULT_SERVICE_KEYWORDS: Tuple[str, ...] = (
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

BOOK_CATEGORY_KEYWORDS: Tuple[str, ...] = (
    "图书",
    "小说",
    "文学",
    "教材",
    "教辅",
    "童书",
    "杂志",
    "期刊",
    "音像",
)

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


def _now() -> datetime:
    return datetime.now()


def _contains_any(text: str, keywords: Sequence[str]) -> int:
    if not text:
        return 0
    return int(any(k in text for k in keywords))


def _is_holiday(dt: Optional[datetime]) -> int:
    if not dt:
        return 0
    if dt.weekday() >= 5:
        return 1
    return int((dt.month, dt.day) in HOLIDAY_MD)


def _is_book_category(category_name: Optional[str]) -> int:
    return _contains_any(category_name or "", BOOK_CATEGORY_KEYWORDS)


def _is_positive(sentiment: Optional[str]) -> int:
    return int(str(sentiment or "").strip().lower() == "positive")


def _clean_text(text: Optional[str]) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _normalize_sentiment(raw: Optional[str]) -> Optional[str]:
    text = str(raw or "").strip()
    if not text:
        return None
    mapping = {
        "positive": "positive",
        "pos": "positive",
        "正向": "positive",
        "好评": "positive",
        "neutral": "neutral",
        "中性": "neutral",
        "negative": "negative",
        "neg": "negative",
        "负向": "negative",
        "差评": "negative",
    }
    return mapping.get(text) or mapping.get(text.lower())


def _pct(v: Any) -> str:
    try:
        return f"{round(float(v) * 100, 1)}%"
    except (TypeError, ValueError):
        return "-"


def _conclusion_from_estimate(est: Dict[str, Any]) -> str:
    """小白话结论：普通人也能看懂「提服务好不好」。"""
    n = int(est.get("sampleSize") or 0)
    if n <= 0:
        return "还没有可用的评价，请先导入或新增评价，再点「运行分析」。"
    ate = est.get("ate")
    p1 = est.get("treatedPositiveRate")
    p0 = est.get("controlPositiveRate")
    if ate is None or p1 is None or p0 is None:
        return (
            f"一共看了 {n} 条评价，但「提到服务」或「没提到服务」的一边太少，"
            "暂时不好下结论。建议再多收集一些评价。"
        )
    mention_good = _pct(p1)
    silent_good = _pct(p0)
    diff = abs(float(ate))
    diff_txt = f"{round(diff * 100, 1)}%"
    if float(ate) > 0.05:
        return (
            f"说到物流、客服这些服务时，好评更多"
            f"（提到服务好评约 {mention_good}，没提到约 {silent_good}，大约高 {diff_txt}）。"
            f"说明把服务做好，顾客更容易满意。"
        )
    if float(ate) < -0.05:
        return (
            f"说到物流、客服这些服务时，好评反而更少"
            f"（提到服务好评约 {mention_good}，没提到约 {silent_good}，大约低 {diff_txt}）。"
            f"说明服务问题可能在拉低满意度，建议优先改进服务。"
        )
    return (
        f"提到服务和没提到服务的好评差不多"
        f"（分别约 {mention_good} 和 {silent_good}），"
        f"看不出服务体验对满意度有明显影响。"
    )


def _explanation_plain() -> str:
    return (
        "怎么看：把评价分成两类——"
        "一类提到了物流/客服/售后等服务，一类没提。"
        "再比较两边好评谁更多。数字越大，说明服务对满意度的影响越明显。"
    )


def _reviews_payload(
    db: Session,
    *,
    category_id: Optional[str] = None,
    category_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    q = db.query(BizSentimentQuery)
    if category_id and category_id.strip():
        q = q.filter(BizSentimentQuery.category_id == category_id.strip())
    if category_name and category_name.strip():
        q = q.filter(BizSentimentQuery.category_name.contains(category_name.strip()))
    rows = q.order_by(BizSentimentQuery.create_time.desc()).limit(5000).all()
    payload = []
    for r in rows:
        content = _clean_text(r.content)
        if not content:
            continue
        sentiment = _normalize_sentiment(r.sentiment)
        payload.append(
            {
                "id": r.id,
                "content": content,
                "summary": _clean_text(r.summary) or None,
                "keywords": r.keywords,
                "sentiment": sentiment,
                "score": r.score,
                "productId": r.product_id,
                "productName": (r.product_name or "").strip() or None,
                "categoryId": r.category_id,
                "categoryName": (r.category_name or "").strip() or "未分类",
                "createTime": r.create_time.strftime("%Y-%m-%d %H:%M:%S") if r.create_time else None,
            }
        )
    return payload


def _local_estimate(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(rows)
    if n == 0:
        return {
            "sampleSize": 0,
            "treatmentRate": 0.0,
            "outcomeRate": 0.0,
            "ate": None,
            "ateText": "暂无样本",
            "treatedPositiveRate": None,
            "controlPositiveRate": None,
            "table": {"t1_y1": 0, "t1_y0": 0, "t0_y1": 0, "t0_y0": 0},
        }
    t1_y1 = t1_y0 = t0_y1 = t0_y0 = 0
    treat_n = out_n = 0
    for rev in rows:
        text = f"{rev.get('content') or ''} {rev.get('keywords') or ''} {rev.get('summary') or ''}"
        t = _contains_any(text, DEFAULT_SERVICE_KEYWORDS)
        y = _is_positive(rev.get("sentiment"))
        treat_n += t
        out_n += y
        if t and y:
            t1_y1 += 1
        elif t and not y:
            t1_y0 += 1
        elif (not t) and y:
            t0_y1 += 1
        else:
            t0_y0 += 1
    n_t1, n_t0 = t1_y1 + t1_y0, t0_y1 + t0_y0
    p1 = (t1_y1 / n_t1) if n_t1 else None
    p0 = (t0_y1 / n_t0) if n_t0 else None
    ate = round(p1 - p0, 4) if p1 is not None and p0 is not None else None
    result = {
        "sampleSize": n,
        "treatmentRate": round(treat_n / n, 4),
        "outcomeRate": round(out_n / n, 4),
        "ate": ate,
        "treatedPositiveRate": round(p1, 4) if p1 is not None else None,
        "controlPositiveRate": round(p0, 4) if p0 is not None else None,
        "table": {"t1_y1": t1_y1, "t1_y0": t1_y0, "t0_y1": t0_y1, "t0_y0": t0_y0},
        "explanation": _explanation_plain(),
        "treatmentKeywords": list(DEFAULT_SERVICE_KEYWORDS),
    }
    result["ateText"] = _conclusion_from_estimate(result)
    result["conclusion"] = result["ateText"]
    return result


def _local_analyze_by_category(reviews: List[Dict[str, Any]], category_name: Optional[str] = None) -> List[Dict[str, Any]]:
    if category_name and category_name.strip():
        reviews = [r for r in reviews if str(r.get("categoryName") or "") == category_name.strip()]
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in reviews:
        groups[str(r.get("categoryName") or "未分类")].append(r)
    items = []
    for cat in sorted(groups.keys()):
        est = _local_estimate(groups[cat])
        items.append({"categoryName": cat, **est})
    return items


def _call_ai_analyze(reviews: List[Dict[str, Any]], category_name: Optional[str] = None) -> Dict[str, Any]:
    if settings.sentiment_ai_mock:
        raise RuntimeError("sentiment_ai_mock=true")
    base = settings.sentiment_ai_base_url.rstrip("/")
    timeout = settings.sentiment_ai_timeout
    # 1) 处理评论数据
    with httpx.Client(timeout=timeout) as client:
        prep = client.post(f"{base}/api/causal/prepare", json={"reviews": reviews})
        if prep.status_code >= 400:
            raise RuntimeError(f"AI prepare {prep.status_code}: {prep.text[:200]}")
        prep_body = prep.json()
        prepared = ((prep_body.get("data") or {}).get("rows")) if isinstance(prep_body, dict) else None
        if not isinstance(prepared, list):
            raise RuntimeError("AI prepare 响应缺少 rows")
        # 2) 因果分析
        ana = client.post(
            f"{base}/api/causal/analyze",
            json={"prepared": prepared, "categoryName": category_name},
        )
        if ana.status_code >= 400:
            raise RuntimeError(f"AI analyze {ana.status_code}: {ana.text[:200]}")
        ana_body = ana.json()
        data = ana_body.get("data") if isinstance(ana_body, dict) else None
        if not isinstance(data, dict):
            raise RuntimeError("AI analyze 响应缺少 data")
        return data


def _to_decimal(v: Any) -> Optional[Decimal]:
    if v is None:
        return None
    try:
        return Decimal(str(v))
    except Exception:
        return None


def result_to_dict(row: BizCausalResult) -> Dict[str, Any]:
    data = model_to_dict(row)
    for key in (
        "treatmentRate",
        "outcomeRate",
        "ate",
        "treatedPositiveRate",
        "controlPositiveRate",
    ):
        if isinstance(data.get(key), Decimal):
            data[key] = float(data[key])
    table = {}
    if row.table_json:
        try:
            table = json.loads(row.table_json)
        except Exception:
            table = {}
    data["table"] = table
    # 列表/详情统一用小白话重算，兼容库里旧结论文案
    data["ateText"] = _conclusion_from_estimate(data)
    data["conclusion"] = data["ateText"]
    if not (data.get("explanation") or "").strip() or "干预=" in str(data.get("explanation") or ""):
        data["explanation"] = _explanation_plain()
    return data


def list_results(
    db: Session,
    *,
    page_no: int = 1,
    page_size: int = 10,
    category_name: Optional[str] = None,
) -> Dict[str, Any]:
    q = db.query(BizCausalResult).filter(BizCausalResult.del_flag == 0)
    if category_name and category_name.strip():
        q = q.filter(BizCausalResult.category_name.contains(category_name.strip()))
    q = q.order_by(BizCausalResult.update_time.desc())
    items, total = paginate_query(q, page_no, page_size)
    return PageResult.build([result_to_dict(i) for i in items], total, page_no, page_size).model_dump()


def _upsert_item(db: Session, item: Dict[str, Any], *, username: Optional[str], source: str) -> BizCausalResult:
    cat = str(item.get("categoryName") or "未分类").strip() or "未分类"
    row = (
        db.query(BizCausalResult)
        .filter(BizCausalResult.category_name == cat, BizCausalResult.del_flag == 0)
        .first()
    )
    now = _now()
    table = item.get("table") or {}
    if row is None:
        row = BizCausalResult(id=new_id(), category_name=cat, create_by=username, create_time=now, del_flag=0)
        db.add(row)
    row.category_id = item.get("categoryId")
    row.sample_size = int(item.get("sampleSize") or 0)
    row.treatment_rate = _to_decimal(item.get("treatmentRate"))
    row.outcome_rate = _to_decimal(item.get("outcomeRate"))
    row.ate = _to_decimal(item.get("ate"))
    row.ate_text = item.get("ateText")
    row.treated_positive_rate = _to_decimal(item.get("treatedPositiveRate"))
    row.control_positive_rate = _to_decimal(item.get("controlPositiveRate"))
    row.table_json = json.dumps(table, ensure_ascii=False)
    row.explanation = item.get("explanation")
    row.source = source
    row.update_by = username
    row.update_time = now
    return row


def run_analysis(
    db: Session,
    *,
    category_id: Optional[str] = None,
    category_name: Optional[str] = None,
    username: Optional[str] = None,
) -> Dict[str, Any]:
    reviews = _reviews_payload(db, category_id=category_id, category_name=category_name)
    if not reviews:
        raise ValueError("所选条件下没有评价数据，请先在评价管理中录入")

    source = "ai"
    items: List[Dict[str, Any]] = []
    try:
        data = _call_ai_analyze(reviews, category_name=category_name)
        items = list(data.get("items") or [])
        if not items and data.get("overall"):
            items = [data["overall"]]
        logger.info("causal AI ok categories=%s reviews=%s", len(items), len(reviews))
    except Exception as exc:
        logger.warning("causal AI failed, local fallback: %s", exc)
        source = "local"
        items = _local_analyze_by_category(reviews, category_name=category_name)

    # 统一写成可读「因果预测结论」（不向前端暴露 ATE 字段语义）
    for item in items:
        item["ateText"] = _conclusion_from_estimate(item)
        item["conclusion"] = item["ateText"]

    saved = []
    for item in items:
        row = _upsert_item(db, item, username=username, source=source)
        saved.append(row)
    db.commit()
    for row in saved:
        db.refresh(row)
    return {
        "source": source,
        "reviewCount": len(reviews),
        "categoryCount": len(saved),
        "records": [result_to_dict(r) for r in saved],
    }


def delete_results(db: Session, ids: List[str]) -> int:
    id_list = [i for i in ids if i]
    if not id_list:
        return 0
    count = (
        db.query(BizCausalResult)
        .filter(BizCausalResult.id.in_(id_list), BizCausalResult.del_flag == 0)
        .update({BizCausalResult.del_flag: 1, BizCausalResult.update_time: _now()}, synchronize_session=False)
    )
    db.commit()
    return int(count or 0)


# 兼容旧看板调用
def analyze(db: Session, *, product_id: Optional[str] = None, keywords: Optional[List[str]] = None) -> Dict[str, Any]:
    q = db.query(BizSentimentQuery)
    if product_id and product_id.strip():
        q = q.filter(BizSentimentQuery.product_id == product_id.strip())
    rows = q.limit(5000).all()
    reviews = [
        {
            "content": r.content,
            "keywords": r.keywords,
            "summary": r.summary,
            "sentiment": r.sentiment,
            "categoryName": r.category_name or "未分类",
            "createTime": r.create_time,
        }
        for r in rows
    ]
    items = _local_analyze_by_category(reviews)
    overall = _local_estimate(reviews)
    return {
        **overall,
        "treatmentKeywords": keywords or list(DEFAULT_SERVICE_KEYWORDS),
        "items": items,
    }
