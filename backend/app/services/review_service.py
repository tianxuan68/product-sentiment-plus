"""评价/情感询问记录 CRUD。"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.biz import BizCategory, BizProduct, BizSentimentQuery
from app.schemas.response import PageResult
from app.utils.common import model_to_dict, new_id, paginate_query

logger = logging.getLogger(__name__)

_SENTIMENT_TEXT = {
    "positive": "正向",
    "neutral": "中性",
    "negative": "负向",
}


def _now() -> datetime:
    return datetime.now()


def _normalize_keywords(raw: Optional[Union[List[str], str]]) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    text = str(raw).strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
    except Exception:
        pass
    parts = [p.strip() for p in text.replace("、", ",").split(",")]
    return [p for p in parts if p]


def review_to_dict(row: BizSentimentQuery, *, product_cover: Optional[str] = None) -> Dict[str, Any]:
    data = model_to_dict(row)
    data["sentiment_dictText"] = _SENTIMENT_TEXT.get(str(row.sentiment or "").lower(), row.sentiment or "")
    keywords = row.keywords
    if keywords:
        try:
            parsed = json.loads(keywords)
            if isinstance(parsed, list):
                data["keywordsText"] = "、".join(str(x) for x in parsed)
                data["keywordList"] = [str(x).strip() for x in parsed if str(x).strip()]
            else:
                data["keywordsText"] = keywords
                data["keywordList"] = _normalize_keywords(keywords)
        except Exception:
            data["keywordsText"] = keywords
            data["keywordList"] = _normalize_keywords(keywords)
    else:
        data["keywordsText"] = ""
        data["keywordList"] = []
    # 评价图优先，其次商品封面（手机端列表主图）
    cover = (data.get("coverUrl") or "").strip() or (product_cover or "").strip() or None
    data["coverUrl"] = cover
    data["hasOwnCover"] = bool((getattr(row, "cover_url", None) or "").strip())
    return data


def _product_cover_map(db: Session, product_ids: List[str]) -> Dict[str, str]:
    ids = [i for i in product_ids if i]
    if not ids:
        return {}
    rows = (
        db.query(BizProduct.id, BizProduct.cover_url)
        .filter(BizProduct.id.in_(ids), BizProduct.del_flag == 0)
        .all()
    )
    return {str(r.id): str(r.cover_url) for r in rows if r.cover_url}


_SORT_COLUMNS = {
    "createTime": BizSentimentQuery.create_time,
    "score": BizSentimentQuery.score,
    "sentiment": BizSentimentQuery.sentiment,
}


def list_reviews(
    db: Session,
    *,
    page_no: int = 1,
    page_size: int = 10,
    content: Optional[str] = None,
    keyword: Optional[str] = None,
    product_name: Optional[str] = None,
    username: Optional[str] = None,
    sentiment: Optional[str] = None,
    category_id: Optional[str] = None,
    tag: Optional[str] = None,
    score_min: Optional[int] = None,
    score_max: Optional[int] = None,
    has_image: Optional[bool] = None,
    column: Optional[str] = None,
    order: Optional[str] = None,
) -> Dict[str, Any]:
    q = db.query(BizSentimentQuery)
    text = (keyword or content or "").strip()
    if text:
        q = q.filter(
            BizSentimentQuery.content.contains(text)
            | BizSentimentQuery.product_name.contains(text)
            | BizSentimentQuery.keywords.contains(text)
            | BizSentimentQuery.summary.contains(text)
        )
    if product_name and product_name.strip():
        q = q.filter(BizSentimentQuery.product_name.contains(product_name.strip()))
    if username and username.strip():
        q = q.filter(BizSentimentQuery.username.contains(username.strip()))
    if sentiment and sentiment.strip():
        q = q.filter(BizSentimentQuery.sentiment == sentiment.strip().lower())
    if category_id and category_id.strip():
        q = q.filter(BizSentimentQuery.category_id == category_id.strip())
    if tag and tag.strip():
        q = q.filter(
            BizSentimentQuery.keywords.contains(tag.strip())
            | BizSentimentQuery.content.contains(tag.strip())
        )
    if score_min is not None:
        q = q.filter(BizSentimentQuery.score >= int(score_min))
    if score_max is not None:
        q = q.filter(BizSentimentQuery.score <= int(score_max))
    if has_image is True:
        from sqlalchemy import and_, or_

        prod_ids = [
            r[0]
            for r in db.query(BizProduct.id)
            .filter(
                BizProduct.del_flag == 0,
                BizProduct.cover_url.isnot(None),
                BizProduct.cover_url != "",
            )
            .all()
        ]
        own = and_(BizSentimentQuery.cover_url.isnot(None), BizSentimentQuery.cover_url != "")
        if prod_ids:
            q = q.filter(or_(own, BizSentimentQuery.product_id.in_(prod_ids)))
        else:
            q = q.filter(own)
    elif has_image is False:
        q = q.filter((BizSentimentQuery.cover_url.is_(None)) | (BizSentimentQuery.cover_url == ""))

    col = _SORT_COLUMNS.get((column or "").strip() or "createTime", BizSentimentQuery.create_time)
    if str(order or "desc").lower() == "asc":
        q = q.order_by(col.asc(), BizSentimentQuery.create_time.desc())
    else:
        q = q.order_by(col.desc(), BizSentimentQuery.create_time.desc())

    items, total = paginate_query(q, page_no, page_size)
    covers = _product_cover_map(db, [i.product_id for i in items if i.product_id])
    records = [
        review_to_dict(i, product_cover=covers.get(str(i.product_id or "")))
        for i in items
    ]
    return PageResult.build(records, total, page_no, page_size).model_dump()


def _resolve_product(db: Session, data: Dict[str, Any]) -> Dict[str, Optional[str]]:
    product_id = (data.get("productId") or "").strip() or None
    product_name = (data.get("productName") or "").strip() or None
    category_id = (data.get("categoryId") or "").strip() or None
    category_name = (data.get("categoryName") or "").strip() or None

    if product_id:
        prod = db.query(BizProduct).filter(BizProduct.id == product_id, BizProduct.del_flag == 0).first()
        if prod:
            product_name = product_name or prod.name
            if prod.category_id:
                category_id = category_id or prod.category_id
                cat = (
                    db.query(BizCategory)
                    .filter(BizCategory.id == prod.category_id, BizCategory.del_flag == 0)
                    .first()
                )
                if cat:
                    category_name = category_name or cat.name
    return {
        "product_id": product_id,
        "product_name": product_name,
        "category_id": category_id,
        "category_name": category_name,
    }


def create_review(
    db: Session,
    data: Dict[str, Any],
    *,
    user_id: Optional[str] = None,
    username: Optional[str] = None,
) -> BizSentimentQuery:
    content = str(data.get("content") or "").strip()
    if not content:
        raise ValueError("评价内容不能为空")
    resolved = _resolve_product(db, data)
    keywords = _normalize_keywords(data.get("keywords"))
    sentiment = str(data.get("sentiment") or "").strip().lower() or None
    if sentiment and sentiment not in _SENTIMENT_TEXT:
        raise ValueError("情绪取值应为 positive / neutral / negative")
    score = data.get("score")
    cover_url = str(data.get("coverUrl") or data.get("cover_url") or "").strip() or None
    row = BizSentimentQuery(
        id=new_id(),
        user_id=user_id,
        username=(str(data.get("username") or "").strip() or username),
        product_id=resolved["product_id"],
        product_name=resolved["product_name"],
        category_id=resolved["category_id"],
        category_name=resolved["category_name"],
        content=content,
        cover_url=cover_url,
        sentiment=sentiment,
        score=int(score) if score is not None and str(score) != "" else None,
        summary=(str(data.get("summary") or "").strip() or None),
        keywords=json.dumps(keywords, ensure_ascii=False) if keywords else None,
        create_time=_now(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_review(db: Session, rid: str, data: Dict[str, Any]) -> BizSentimentQuery:
    row = db.query(BizSentimentQuery).filter(BizSentimentQuery.id == rid).first()
    if not row:
        raise ValueError("评价不存在")
    if "content" in data and data.get("content") is not None:
        content = str(data.get("content") or "").strip()
        if not content:
            raise ValueError("评价内容不能为空")
        row.content = content
    if any(k in data for k in ("productId", "productName", "categoryId", "categoryName")):
        resolved = _resolve_product(db, {**review_to_dict(row), **data})
        row.product_id = resolved["product_id"]
        row.product_name = resolved["product_name"]
        row.category_id = resolved["category_id"]
        row.category_name = resolved["category_name"]
    if "sentiment" in data:
        sentiment = str(data.get("sentiment") or "").strip().lower() or None
        if sentiment and sentiment not in _SENTIMENT_TEXT:
            raise ValueError("情绪取值应为 positive / neutral / negative")
        row.sentiment = sentiment
    if "score" in data:
        score = data.get("score")
        row.score = int(score) if score is not None and str(score) != "" else None
    if "summary" in data:
        row.summary = (str(data.get("summary") or "").strip() or None)
    if "keywords" in data:
        keywords = _normalize_keywords(data.get("keywords"))
        row.keywords = json.dumps(keywords, ensure_ascii=False) if keywords else None
    if "username" in data:
        row.username = (str(data.get("username") or "").strip() or None)
    if "coverUrl" in data or "cover_url" in data:
        cover = data.get("coverUrl") if "coverUrl" in data else data.get("cover_url")
        row.cover_url = (str(cover or "").strip() or None)
    db.commit()
    db.refresh(row)
    return row


def delete_reviews(db: Session, ids: List[str]) -> int:
    id_list = [i for i in ids if i]
    if not id_list:
        return 0
    count = (
        db.query(BizSentimentQuery)
        .filter(BizSentimentQuery.id.in_(id_list))
        .delete(synchronize_session=False)
    )
    db.commit()
    return int(count or 0)


def _sentiment_from_predict(pred_body: Dict[str, Any], content: str) -> Tuple[str, int]:
    """把 /api/predict/one 结果映射为三态情绪与 0-100 分。"""
    conf = pred_body.get("confidence")
    if conf is None:
        conf = max(float(pred_body.get("prob_pos") or 0), float(pred_body.get("prob_neg") or 0))
    try:
        conf = float(conf or 0)
    except (TypeError, ValueError):
        conf = 0.0
    neutral_cues = ("一般", "还行", "凑合", "中规中矩", "普通", "马马虎虎", "不好不坏")
    if any(c in (content or "") for c in neutral_cues) or conf < 0.55:
        sentiment = "neutral"
        score = int(round(max(0.0, 1.0 - abs(conf - 0.5) * 2) * 55 + 40))
    else:
        sentiment = "positive" if int(pred_body.get("pred") or 0) == 1 else "negative"
        score = int(round(conf * 100))
    return sentiment, max(0, min(100, score))


def _call_ai_analyze(content: str, *, product_id: Optional[str], product_name: Optional[str], category_name: Optional[str]) -> Dict[str, Any]:
    """调 AI：BERT 多标签（tag/one）+ BERT 情感（predict/one）。"""
    base = settings.sentiment_ai_base_url.rstrip("/")
    timeout = settings.sentiment_ai_timeout

    try:
        with httpx.Client(timeout=timeout) as client:
            tag_resp = client.post(
                f"{base}/api/tag/one",
                json={
                    "text": content,
                    "product_id": product_id or "DRAFT",
                    "category": category_name,
                    "product_name": product_name,
                    "method": "model",
                },
            )
            if tag_resp.status_code >= 400:
                detail = (tag_resp.text or "").strip()[:200]
                raise RuntimeError(f"AI 打标失败（tag/one {tag_resp.status_code}）{(': ' + detail) if detail else ''}")
            tag_body = tag_resp.json()
            if not isinstance(tag_body, dict):
                tag_body = {}

            pred_body: Dict[str, Any] = {}
            for model_name in ("bert", "fasttext", "baseline"):
                pred = client.post(
                    f"{base}/api/predict/one",
                    json={"text": content, "model": model_name},
                )
                if pred.status_code < 400:
                    raw = pred.json()
                    pred_body = raw if isinstance(raw, dict) else {}
                    break
                logger.warning("AI predict/one model=%s failed: %s", model_name, pred.status_code)
    except httpx.ConnectError as exc:
        raise RuntimeError(
            f"AI 服务未启动（{base}）。请在 product-sentiment-ai 目录启动：python -m uvicorn api.main:app --host 127.0.0.1 --port 8001"
        ) from exc
    except httpx.TimeoutException as exc:
        raise RuntimeError(f"AI 服务超时（{timeout}s），请稍后重试或检查模型是否卡在加载") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"AI 服务请求失败：{exc}") from exc

    tags = list(tag_body.get("tags") or [])
    tag_names = [str(x) for x in (tag_body.get("tag_names") or []) if str(x).strip()]
    if not tag_names and tags:
        tag_names = [str(t.get("tag") or "").strip() for t in tags if isinstance(t, dict) and t.get("tag")]
    backend = str(tag_body.get("backend") or tag_body.get("method") or "model")

    if pred_body:
        sentiment, score = _sentiment_from_predict(pred_body, content)
    else:
        pols = {str(t.get("polarity") or "").lower() for t in tags if isinstance(t, dict)}
        if "negative" in pols or "neg" in pols:
            sentiment = "negative"
        elif "positive" in pols or "pos" in pols:
            sentiment = "positive"
        else:
            sentiment = "neutral"
        score = 60

    # keywords：与整体情绪极性对齐（负评不展示「会回购」类正向标签）
    keywords = tag_names[:8]
    if sentiment in ("positive", "negative") and tags:
        want = {"positive", "pos"} if sentiment == "positive" else {"negative", "neg"}
        filtered = [
            str(t.get("tag")).strip()
            for t in tags
            if isinstance(t, dict)
            and t.get("tag")
            and str(t.get("polarity") or "").strip().lower() in want
        ]
        if filtered:
            keywords = filtered[:8]

    who = product_name or category_name or "该商品"
    tone = {"positive": "偏正向", "negative": "偏负向", "neutral": "偏中性"}.get(sentiment, "偏中性")
    if keywords:
        summary = f"针对{who}的反馈整体{tone}；模型识别到的方面标签：{'、'.join(keywords[:6])}。"
    else:
        summary = f"针对{who}的反馈整体{tone}；未识别到明确方面标签。"

    return {
        "sentiment": sentiment,
        "score": score,
        "summary": summary,
        "keywords": keywords,
        "tags": tags,
        "tagNames": tag_names or keywords,
        "backend": backend,
    }


def analyze_review(db: Session, rid: str) -> Dict[str, Any]:
    """对单条评价跑 BERT 多标签 + 情感分析，并回写库。"""
    row = db.query(BizSentimentQuery).filter(BizSentimentQuery.id == rid).first()
    if not row:
        raise ValueError("评价不存在")
    content = (row.content or "").strip()
    if not content:
        raise ValueError("评价内容为空，无法分析")

    if settings.sentiment_ai_mock:
        raise RuntimeError("sentiment_ai_mock=true，无法调用真实模型")

    result = _call_ai_analyze(
        content,
        product_id=row.product_id,
        product_name=row.product_name,
        category_name=row.category_name,
    )
    row.sentiment = result["sentiment"]
    row.score = result["score"]
    row.summary = result["summary"] or row.summary
    row.keywords = json.dumps(result["keywords"] or [], ensure_ascii=False)
    db.commit()
    db.refresh(row)

    data = review_to_dict(row)
    data["keywords"] = result.get("keywords") or []
    data["tags"] = result.get("tags") or []
    data["tagNames"] = result.get("tagNames") or result.get("keywords") or []
    data["backend"] = result.get("backend")
    return data
