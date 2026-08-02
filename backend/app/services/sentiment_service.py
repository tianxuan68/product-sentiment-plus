"""
评论分析：对接 product-sentiment-ai，组装前端 Insight 所需字段，并落库。
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.biz import BizCategory, BizProduct, BizSentimentQuery
from app.utils.common import new_id

logger = logging.getLogger(__name__)


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


def _parse_decimal(value: Any) -> Optional[Decimal]:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def find_category_by_name(db: Session, name: Optional[str]) -> Optional[BizCategory]:
    name = (name or "").strip()
    if not name:
        return None
    return (
        db.query(BizCategory)
        .filter(BizCategory.name == name, BizCategory.del_flag == 0, BizCategory.status == 1)
        .order_by(BizCategory.level.desc())
        .first()
    )


def save_product_draft(
    db: Session,
    product: dict,
    *,
    user_id: Optional[str] = None,
    username: Optional[str] = None,
    product_id: Optional[str] = None,
) -> dict:
    """保存/更新商品到 biz_product，按 product_id 或「同名+创建人」更新。"""
    payload = product or {}
    name = str(payload.get("name") or "").strip()
    if not name:
        raise ValueError("商品名称不能为空")

    now = datetime.now()
    category_name = str(payload.get("category") or payload.get("categoryName") or "").strip() or None
    category = None
    category_id = payload.get("categoryId") or payload.get("category_id")
    if category_id:
        category = (
            db.query(BizCategory)
            .filter(BizCategory.id == category_id, BizCategory.del_flag == 0)
            .first()
        )
    if not category and category_name:
        category = find_category_by_name(db, category_name)

    row: Optional[BizProduct] = None
    if product_id:
        row = (
            db.query(BizProduct)
            .filter(BizProduct.id == product_id, BizProduct.del_flag == 0)
            .first()
        )
    if not row and user_id:
        row = (
            db.query(BizProduct)
            .filter(
                BizProduct.name == name,
                BizProduct.create_by == user_id,
                BizProduct.del_flag == 0,
            )
            .order_by(BizProduct.create_time.desc())
            .first()
        )

    rating = _parse_decimal(payload.get("rating"))
    price = _parse_decimal(payload.get("price"))
    original_price = _parse_decimal(payload.get("originalPrice") or payload.get("original_price"))
    note = str(payload.get("note") or "").strip() or None
    brand = str(payload.get("brand") or "").strip() or None
    sku = str(payload.get("sku") or "").strip() or None
    description = str(payload.get("description") or "").strip() or None
    cover_url = str(payload.get("coverUrl") or payload.get("cover_url") or "").strip() or None
    unit = str(payload.get("unit") or "").strip() or None
    currency = str(payload.get("currency") or "CNY").strip() or "CNY"
    stock_raw = payload.get("stock")
    try:
        stock = int(stock_raw) if stock_raw is not None and stock_raw != "" else None
    except (TypeError, ValueError):
        stock = None

    if row:
        row.name = name
        if category:
            row.category_id = category.id
        if brand is not None:
            row.brand = brand
        if sku is not None:
            row.sku = sku
        if price is not None:
            row.price = price
        if original_price is not None:
            row.original_price = original_price
        if rating is not None:
            row.rating = rating
        if note is not None:
            row.note = note
        if description is not None:
            row.description = description
        if cover_url is not None:
            row.cover_url = cover_url
        if unit is not None:
            row.unit = unit
        if stock is not None:
            row.stock = stock
        row.currency = currency
        row.update_by = user_id or username
        row.update_time = now
    else:
        row = BizProduct(
            id=new_id(),
            name=name,
            category_id=category.id if category else None,
            brand=brand,
            sku=sku,
            price=price,
            original_price=original_price,
            currency=currency,
            cover_url=cover_url,
            rating=rating,
            stock=stock if stock is not None else 0,
            unit=unit,
            status=1,
            description=description,
            note=note,
            del_flag=0,
            create_by=user_id or username,
            create_time=now,
            update_by=user_id or username,
            update_time=now,
        )
        db.add(row)

    db.commit()
    db.refresh(row)
    logger.info("保存商品 id=%s name=%s category=%s", row.id, row.name, row.category_id)
    return {
        "ok": True,
        "saved": True,
        "id": row.id,
        "name": row.name,
        "categoryId": row.category_id,
        "categoryName": category.name if category else category_name,
        "price": float(row.price) if row.price is not None else None,
        "rating": float(row.rating) if row.rating is not None else None,
    }


def save_sentiment_query(
    db: Session,
    *,
    content: str,
    result: dict,
    product_id: Optional[str] = None,
    product: Optional[dict] = None,
    user_id: Optional[str] = None,
    username: Optional[str] = None,
) -> str:
    product = product or {}
    product_name = str(product.get("name") or "").strip() or None
    category_name = str(product.get("category") or product.get("categoryName") or "").strip() or None
    category_id = product.get("categoryId") or product.get("category_id")

    category = None
    if category_id:
        category = (
            db.query(BizCategory)
            .filter(BizCategory.id == category_id, BizCategory.del_flag == 0)
            .first()
        )
    if not category and category_name:
        category = find_category_by_name(db, category_name)

    if product_id:
        prod = (
            db.query(BizProduct)
            .filter(BizProduct.id == product_id, BizProduct.del_flag == 0)
            .first()
        )
        if prod:
            product_name = product_name or prod.name
            if not category and prod.category_id:
                category = (
                    db.query(BizCategory)
                    .filter(BizCategory.id == prod.category_id, BizCategory.del_flag == 0)
                    .first()
                )

    keywords = result.get("keywords") or []
    row = BizSentimentQuery(
        id=new_id(),
        user_id=user_id,
        username=username,
        product_id=product_id,
        product_name=product_name,
        category_id=category.id if category else None,
        category_name=category.name if category else category_name,
        content=content,
        sentiment=str(result.get("sentiment") or ""),
        score=int(result.get("score") or 0),
        summary=str(result.get("summary") or ""),
        keywords=json.dumps(keywords, ensure_ascii=False),
        create_time=datetime.now(),
    )
    db.add(row)
    db.commit()
    logger.info("保存询问记录 id=%s user=%s sentiment=%s", row.id, username, row.sentiment)
    return row.id


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


def predict_and_save(
    db: Session,
    *,
    content: str,
    product_id: Optional[str] = None,
    product: Optional[dict] = None,
    user_id: Optional[str] = None,
    username: Optional[str] = None,
    persist_product: bool = False,
) -> dict:
    """分析并写入 biz_sentiment_query；可选同步保存商品。"""
    resolved_product_id = product_id
    product_payload = dict(product or {}) if product else {}

    if persist_product and product_payload.get("name"):
        saved = save_product_draft(
            db,
            product_payload,
            user_id=user_id,
            username=username,
            product_id=product_id,
        )
        resolved_product_id = saved.get("id") or resolved_product_id
        if saved.get("categoryId"):
            product_payload["categoryId"] = saved["categoryId"]
        if saved.get("categoryName"):
            product_payload["category"] = saved["categoryName"]

    result = predict(content, product_id=resolved_product_id, product=product_payload or None)
    try:
        query_id = save_sentiment_query(
            db,
            content=content,
            result=result,
            product_id=resolved_product_id,
            product=product_payload or None,
            user_id=user_id,
            username=username,
        )
        result = {**result, "queryId": query_id, "productId": resolved_product_id}
    except Exception as exc:
        # 分析成功不应因落库失败而中断前端
        logger.exception("询问落库失败: %s", exc)
        db.rollback()
    return result
