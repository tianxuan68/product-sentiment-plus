"""
案例:
    评论数据 → 因果表 → 按类目估计服务体验干预对正向评价的效应。

大白话:
    对齐 data2causal.py：提及服务体验=干预，正向/好评=结果，节假日/图书品类=混杂。
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

SERVICE_KEYWORDS: Tuple[str, ...] = (
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


def _contains_any(text: str, keywords: Sequence[str]) -> int:
    if not text:
        return 0
    return int(any(k in text for k in keywords))


def _parse_dt(raw: Any) -> Optional[datetime]:
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        return raw
    text = str(raw).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(text[:19], fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _is_holiday(dt: Optional[datetime]) -> int:
    if not dt:
        return 0
    if dt.weekday() >= 5:
        return 1
    return int((dt.month, dt.day) in HOLIDAY_MD)


def _is_positive(review: Dict[str, Any]) -> int:
    sentiment = str(review.get("sentiment") or "").strip().lower()
    if sentiment == "positive":
        return 1
    if sentiment in {"negative", "neutral"}:
        return 0
    # 兼容评分字段
    try:
        score = float(review.get("rating") if review.get("rating") is not None else review.get("score"))
        if score >= 4:
            return 1
        if score > 0:
            return 0
    except (TypeError, ValueError):
        pass
    return 0


def _review_text(review: Dict[str, Any]) -> str:
    parts = [
        str(review.get("content") or ""),
        str(review.get("title") or ""),
        str(review.get("summary") or ""),
        str(review.get("keywords") or ""),
        str(review.get("keywordsText") or ""),
    ]
    return " ".join(parts)


def prepare_reviews(reviews: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """把原始评论转成因果表行。"""
    rows: List[Dict[str, Any]] = []
    for rev in reviews or []:
        text = _review_text(rev)
        category = str(rev.get("categoryName") or rev.get("category_name") or "").strip() or "未分类"
        dt = _parse_dt(rev.get("createTime") or rev.get("create_time"))
        row = {
            "id": str(rev.get("id") or ""),
            "productId": str(rev.get("productId") or rev.get("product_id") or ""),
            "productName": str(rev.get("productName") or rev.get("product_name") or ""),
            "categoryName": category,
            "treatment": _contains_any(text, SERVICE_KEYWORDS),
            "holiday": _is_holiday(dt),
            "bookCategory": _contains_any(category, BOOK_CATEGORY_KEYWORDS),
            "outcome": _is_positive(rev),
        }
        rows.append(row)
    return rows


def _estimate_group(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
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
            "controls": {"holidayRate": 0.0, "bookCategoryRate": 0.0},
        }

    t1_y1 = t1_y0 = t0_y1 = t0_y0 = 0
    treat_n = out_n = holiday_n = book_n = 0
    for r in rows:
        t = int(r.get("treatment") or 0)
        y = int(r.get("outcome") or 0)
        treat_n += t
        out_n += y
        holiday_n += int(r.get("holiday") or 0)
        book_n += int(r.get("bookCategory") or 0)
        if t and y:
            t1_y1 += 1
        elif t and not y:
            t1_y0 += 1
        elif (not t) and y:
            t0_y1 += 1
        else:
            t0_y0 += 1

    n_t1 = t1_y1 + t1_y0
    n_t0 = t0_y1 + t0_y0
    p1 = (t1_y1 / n_t1) if n_t1 else None
    p0 = (t0_y1 / n_t0) if n_t0 else None
    ate = round(p1 - p0, 4) if p1 is not None and p0 is not None else None

    def _pct(v):
        try:
            return f"{round(float(v) * 100, 1)}%"
        except (TypeError, ValueError):
            return "-"

    if ate is None:
        conclusion = (
            f"一共看了 {n} 条评价，但「提到服务」或「没提到服务」的一边太少，"
            "暂时不好下结论。建议再多收集一些评价。"
        )
    elif ate > 0.05:
        conclusion = (
            f"说到物流、客服这些服务时，好评更多"
            f"（提到服务好评约 {_pct(p1)}，没提到约 {_pct(p0)}，大约高 {ate:.1%}）。"
            f"说明把服务做好，顾客更容易满意。"
        )
    elif ate < -0.05:
        conclusion = (
            f"说到物流、客服这些服务时，好评反而更少"
            f"（提到服务好评约 {_pct(p1)}，没提到约 {_pct(p0)}，大约低 {abs(ate):.1%}）。"
            f"说明服务问题可能在拉低满意度，建议优先改进服务。"
        )
    else:
        conclusion = (
            f"提到服务和没提到服务的好评差不多"
            f"（分别约 {_pct(p1)} 和 {_pct(p0)}），"
            f"看不出服务体验对满意度有明显影响。"
        )

    return {
        "sampleSize": n,
        "treatmentRate": round(treat_n / n, 4),
        "outcomeRate": round(out_n / n, 4),
        "ate": ate,
        "ateText": conclusion,
        "conclusion": conclusion,
        "treatedPositiveRate": round(p1, 4) if p1 is not None else None,
        "controlPositiveRate": round(p0, 4) if p0 is not None else None,
        "table": {"t1_y1": t1_y1, "t1_y0": t1_y0, "t0_y1": t0_y1, "t0_y0": t0_y0},
        "controls": {
            "holidayRate": round(holiday_n / n, 4),
            "bookCategoryRate": round(book_n / n, 4),
        },
    }


def analyze_prepared(
    prepared: List[Dict[str, Any]],
    *,
    category_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    对已处理因果表按类目分组估计。
    category_name 有值时只分析该类目；否则返回各类目 + 全部。
    """
    rows = list(prepared or [])
    if category_name and category_name.strip():
        key = category_name.strip()
        rows = [r for r in rows if str(r.get("categoryName") or "") == key]

    by_cat: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        by_cat[str(r.get("categoryName") or "未分类")].append(r)

    items = []
    for cat in sorted(by_cat.keys()):
        est = _estimate_group(by_cat[cat])
        items.append(
            {
                "categoryName": cat,
                **est,
                "treatmentKeywords": list(SERVICE_KEYWORDS),
                "explanation": (
                    "怎么看：把评价分成两类——一类提到了物流/客服/售后等服务，一类没提。"
                    "再比较两边好评谁更多。数字越大，说明服务对满意度的影响越明显。"
                ),
            }
        )

    overall = _estimate_group(rows)
    return {
        "preparedCount": len(prepared or []),
        "filteredCount": len(rows),
        "categoryName": (category_name or "").strip() or None,
        "overall": {
            "categoryName": "全部",
            **overall,
            "treatmentKeywords": list(SERVICE_KEYWORDS),
            "explanation": "把全部评价放在一起粗算，方便和各类目对照着看。",
        },
        "items": items,
    }


def prepare_and_analyze(
    reviews: List[Dict[str, Any]],
    *,
    category_name: Optional[str] = None,
) -> Dict[str, Any]:
    prepared = prepare_reviews(reviews)
    result = analyze_prepared(prepared, category_name=category_name)
    result["prepared"] = prepared
    return result
