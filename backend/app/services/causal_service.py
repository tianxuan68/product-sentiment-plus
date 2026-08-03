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


def _pp(v: Any) -> str:
    """百分点文案，如 12.0 个百分点。"""
    try:
        return f"{round(abs(float(v)) * 100, 1)} 个百分点"
    except (TypeError, ValueError):
        return "-"


def _effect_strength(ate: float) -> str:
    mag = abs(float(ate))
    if mag >= 0.15:
        return "强"
    if mag >= 0.08:
        return "中等"
    if mag >= 0.05:
        return "偏弱"
    return "很弱"


def _conclusion_from_estimate(est: Dict[str, Any]) -> str:
    """动态因果结论文案：反事实对比 + 类目/效应强弱/样本结构，避免三句模板刷屏。"""
    n = int(est.get("sampleSize") or 0)
    cat = str(est.get("categoryName") or "该类目").strip() or "该类目"
    if n <= 0:
        return f"「{cat}」还没有可用评价。请先导入评价，再点「运行分析」。"

    ate = est.get("ate")
    p1 = est.get("treatedPositiveRate")
    p0 = est.get("controlPositiveRate")
    treat_rate = est.get("treatmentRate")
    outcome_rate = est.get("outcomeRate")
    table = est.get("table") or {}
    n_t1 = int(table.get("t1_y1") or 0) + int(table.get("t1_y0") or 0)
    n_t0 = int(table.get("t0_y1") or 0) + int(table.get("t0_y0") or 0)

    if ate is None or p1 is None or p0 is None:
        side = "提到服务" if n_t1 == 0 else "没提到服务"
        return (
            f"「{cat}」共 {n} 条评价，但「{side}」一侧样本不足，"
            f"无法做稳定的反事实对比（需要两边都有评价才能估计服务对好评的净影响）。"
            f"建议补采该类目评价后再跑分析。"
        )

    ate_f = float(ate)
    strength = _effect_strength(ate_f)
    treat_txt = _pct(treat_rate) if treat_rate is not None else "-"
    overall_txt = _pct(outcome_rate) if outcome_rate is not None else "-"
    cover = (
        f"在 {n} 条评价中，约 {treat_txt}（{n_t1} 条）主动提到物流/客服/售后等服务，"
        f"其余 {n_t0} 条未提；类目整体好评约 {overall_txt}。"
    )

    # 反事实核心：提到服务(处理组) vs 未提(对照组) 的好评差 = 估计的服务效应
    contrast = (
        f"反事实对比：若把「提到服务」看作处理、把「未提服务」看作对照，"
        f"两组好评率分别为 {_pct(p1)} 与 {_pct(p0)}，"
        f"估计效应约 {ate_f:+.1%}（{strength}）。"
    )

    if ate_f > 0.05:
        action = (
            f"解读：在「{cat}」里，顾客一旦谈到服务，满意度往往更高——"
            f"服务体验很可能是在「抬升」口碑（相对未提服务的评价高出 {_pp(ate_f)}）。"
            f"建议把物流时效、客服响应做成该类目的显性卖点，并在详情页强化承诺。"
        )
    elif ate_f < -0.05:
        action = (
            f"解读：在「{cat}」里，谈到服务的评价好评率反而更低——"
            f"服务问题更像在「拖累」满意度（相对未提服务低 {_pp(ate_f)}）。"
            f"优先复盘差评里的物流延误、包装破损、客服推诿，属于因果信号较强的改进抓手。"
        )
    else:
        action = (
            f"解读：在「{cat}」里，提到服务与否的好评差距只有 {_pp(ate_f)}（{strength}），"
            f"说明当前数据下「服务」不是拉开满意度的主因；"
            f"口碑差异更可能来自商品本身（品质/尺码/性价比等），服务可维持现状、把精力放在产品侧。"
        )

    # 样本结构提示：处理组过稀/过密时降低因果可信度表述
    caveats = []
    if n < 80:
        caveats.append("样本量偏少，效应估计波动可能较大")
    if treat_rate is not None:
        tr = float(treat_rate)
        if tr < 0.08:
            caveats.append("很少人提到服务，处理组偏稀，结论宜谨慎")
        elif tr > 0.85:
            caveats.append("绝大多数评价都提到服务，对照组偏稀，对比稳定性一般")
    if min(n_t1, n_t0) < 15:
        caveats.append("某一侧少于 15 条，显著性有限")
    caveat_txt = (" 注意：" + "；".join(caveats) + "。") if caveats else ""

    return cover + contrast + action + caveat_txt


def _explanation_plain() -> str:
    return (
        "因果读法（不是简单好评率）："
        "把「是否提到物流/客服/售后」当作处理变量，把「是否好评」当作结果；"
        "比较处理组与对照组的好评差，得到服务对满意度的估计效应。"
        "正效应≈服务在加分，负效应≈服务在拖后腿，接近 0≈服务不是主因。"
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
