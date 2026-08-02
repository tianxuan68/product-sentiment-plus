"""商品信息 CRUD。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.biz import BizCategory, BizProduct
from app.utils.common import model_to_dict, new_id, paginate_query


def _now() -> datetime:
    return datetime.now()


def _category_name_map(db: Session, category_ids: List[str]) -> Dict[str, str]:
    ids = [i for i in set(category_ids) if i]
    if not ids:
        return {}
    rows = (
        db.query(BizCategory)
        .filter(BizCategory.id.in_(ids), BizCategory.del_flag == 0)
        .all()
    )
    return {r.id: r.name for r in rows}


def product_to_dict(db: Session, row: BizProduct, cat_map: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    data = model_to_dict(row)
    if cat_map is None and row.category_id:
        cat_map = _category_name_map(db, [row.category_id])
    data["categoryName"] = (cat_map or {}).get(row.category_id or "", "")
    data["status_dictText"] = "上架" if row.status == 1 else "下架"
    return data


def list_products(
    db: Session,
    *,
    page_no: int = 1,
    page_size: int = 10,
    name: Optional[str] = None,
    brand: Optional[str] = None,
    sku: Optional[str] = None,
    category_id: Optional[str] = None,
    status: Optional[int] = None,
) -> Dict[str, Any]:
    q = db.query(BizProduct).filter(BizProduct.del_flag == 0)
    if name and name.strip():
        q = q.filter(BizProduct.name.contains(name.strip()))
    if brand and brand.strip():
        q = q.filter(BizProduct.brand.contains(brand.strip()))
    if sku and sku.strip():
        q = q.filter(BizProduct.sku.contains(sku.strip()))
    if category_id:
        q = q.filter(BizProduct.category_id == category_id)
    if status is not None and str(status) != "":
        q = q.filter(BizProduct.status == int(status))
    q = q.order_by(BizProduct.create_time.desc())
    items, total = paginate_query(q, page_no, page_size)
    cat_map = _category_name_map(db, [i.category_id or "" for i in items])
    records = [product_to_dict(db, i, cat_map) for i in items]
    from app.schemas.response import PageResult

    return PageResult.build(records, total, page_no, page_size).model_dump()


def get_product(db: Session, product_id: str) -> Optional[BizProduct]:
    return (
        db.query(BizProduct)
        .filter(BizProduct.id == product_id, BizProduct.del_flag == 0)
        .first()
    )


def create_product(db: Session, data: Dict[str, Any], username: Optional[str] = None) -> BizProduct:
    name = str(data.get("name") or "").strip()
    if not name:
        raise ValueError("商品名称不能为空")
    row = BizProduct(
        id=new_id(),
        name=name,
        category_id=data.get("categoryId") or None,
        brand=data.get("brand") or None,
        sku=data.get("sku") or None,
        price=data.get("price"),
        original_price=data.get("originalPrice"),
        currency=data.get("currency") or "CNY",
        cover_url=data.get("coverUrl") or None,
        rating=data.get("rating"),
        stock=int(data.get("stock") or 0),
        unit=data.get("unit") or None,
        status=1 if data.get("status") is None else int(data.get("status")),
        description=data.get("description") or None,
        note=data.get("note") or None,
        del_flag=0,
        create_by=username,
        create_time=_now(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_product(db: Session, product_id: str, data: Dict[str, Any], username: Optional[str] = None) -> BizProduct:
    row = get_product(db, product_id)
    if not row:
        raise ValueError("商品不存在")
    if "name" in data and data["name"] is not None:
        name = str(data["name"]).strip()
        if not name:
            raise ValueError("商品名称不能为空")
        row.name = name
    mapping = {
        "categoryId": "category_id",
        "brand": "brand",
        "sku": "sku",
        "price": "price",
        "originalPrice": "original_price",
        "currency": "currency",
        "coverUrl": "cover_url",
        "rating": "rating",
        "stock": "stock",
        "unit": "unit",
        "status": "status",
        "description": "description",
        "note": "note",
    }
    for src, dest in mapping.items():
        if src in data and data[src] is not None:
            val = data[src]
            if dest == "stock":
                val = int(val or 0)
            elif dest == "status":
                val = int(val)
            setattr(row, dest, val)
        elif src in data and data[src] is None and src in ("categoryId", "brand", "sku", "coverUrl", "unit", "description", "note"):
            setattr(row, dest, None)
    row.update_by = username
    row.update_time = _now()
    db.commit()
    db.refresh(row)
    return row


def soft_delete_products(db: Session, ids: List[str]) -> int:
    id_list = [i for i in ids if i]
    if not id_list:
        return 0
    rows = (
        db.query(BizProduct)
        .filter(BizProduct.id.in_(id_list), BizProduct.del_flag == 0)
        .all()
    )
    for row in rows:
        row.del_flag = 1
        row.update_time = _now()
    db.commit()
    return len(rows)
