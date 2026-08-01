from typing import Any, Dict, List, Optional, Tuple

import re

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.ttl_cache import TTLCache
from app.models.entities import SysDict, SysDictItem

_IDENT_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_TENANT_FALLBACK = [{"value": "0", "text": "默认租户", "label": "默认租户"}]

_dict_items_cache: TTLCache[str, Dict[str, List[Dict[str, Any]]]] = TTLCache(
    maxsize=1,
    ttl_seconds=settings.dict_cache_ttl_seconds,
)
_DICT_CACHE_KEY = "all"


def invalidate_dict_cache() -> None:
    _dict_items_cache.clear()


def query_all_dict_items(db: Session) -> Dict[str, List[Dict[str, Any]]]:
    cached = _dict_items_cache.get(_DICT_CACHE_KEY)
    if cached is not None:
        return cached

    rows = (
        db.query(
            SysDict.dict_code,
            SysDictItem.item_value,
            SysDictItem.item_text,
            SysDictItem.sort_order,
        )
        .join(SysDictItem, SysDictItem.dict_id == SysDict.id)
        .filter(SysDict.del_flag == 0, SysDictItem.status == 1)
        .order_by(SysDict.dict_code, SysDictItem.sort_order)
        .all()
    )

    result: Dict[str, List[Dict[str, Any]]] = {}
    for dict_code, item_value, item_text, _sort_order in rows:
        if not dict_code:
            continue
        result.setdefault(dict_code, []).append(
            {
                "value": item_value,
                "text": item_text,
                "label": item_text,
                "title": item_text,
            }
        )

    _dict_items_cache.set(_DICT_CACHE_KEY, result)
    return result


def _parse_dict_code(code: str) -> Dict[str, Any]:
    parts = [p.strip() for p in code.split(",")]
    if len(parts) >= 3:
        return {
            "type": "table",
            "table": parts[0],
            "text": parts[1],
            "value": parts[2],
            "where": parts[3] if len(parts) > 3 else "",
        }
    return {"type": "dict", "code": code}


def _validate_ident(name: str) -> bool:
    return bool(name and _IDENT_RE.match(name))


def _table_exists(db: Session, table: str) -> bool:
    try:
        return table in inspect(db.get_bind()).get_table_names()
    except Exception:
        return False


def _parse_where_clause(raw: str) -> Tuple[str, str]:
    if not raw:
        return "1=1", ""
    lower = raw.lower()
    order_idx = lower.find(" order by ")
    if order_idx >= 0:
        order_part = raw[order_idx:].strip()
        if re.match(r"^order by [a-zA-Z_][a-zA-Z0-9_]*( asc| desc)?$", order_part, re.I):
            return "1=1", order_part
    if re.fullmatch(r"\d+\s*=\s*\d+", raw.strip()):
        return raw.strip(), ""
    return "1=1", ""


def _load_table_dict(
    db: Session,
    table: str,
    text_col: str,
    value_col: str,
    *,
    keyword: str = "",
    page_no: int = 1,
    page_size: int = 10,
    where_raw: str = "",
) -> List[Dict[str, Any]]:
    if not all(_validate_ident(x) for x in (table, text_col, value_col)):
        return []

    if not _table_exists(db, table):
        if table == "sys_tenant":
            return _TENANT_FALLBACK.copy()
        return []

    where_sql, order_sql = _parse_where_clause(where_raw)
    params: Dict[str, Any] = {
        "limit": max(page_size, 1),
        "offset": max(page_no - 1, 0) * max(page_size, 1),
    }
    keyword_sql = ""
    if keyword:
        params["keyword"] = f"%{keyword}%"
        keyword_sql = f" AND ({text_col} LIKE :keyword OR CAST({value_col} AS CHAR) LIKE :keyword)"

    sql = (
        f"SELECT {value_col} AS value, {text_col} AS text "
        f"FROM {table} WHERE {where_sql}{keyword_sql} "
        f"{order_sql} LIMIT :limit OFFSET :offset"
    )
    rows = db.execute(text(sql), params).mappings().all()
    return [
        {"value": str(row["value"]), "text": str(row["text"]), "label": str(row["text"])}
        for row in rows
        if row["value"] is not None
    ]


def _load_table_dict_items(
    db: Session,
    table: str,
    text_col: str,
    value_col: str,
    keys: List[str],
    where_raw: str = "",
) -> List[str]:
    if not keys:
        return []
    if not all(_validate_ident(x) for x in (table, text_col, value_col)):
        return []

    if not _table_exists(db, table):
        if table == "sys_tenant":
            fallback = {item["value"]: item["text"] for item in _TENANT_FALLBACK}
            return [fallback.get(k, k) for k in keys]
        return keys

    where_sql, order_sql = _parse_where_clause(where_raw)
    placeholders = ", ".join(f":k{i}" for i in range(len(keys)))
    params = {f"k{i}": k for i, k in enumerate(keys)}
    sql = (
        f"SELECT {value_col} AS value, {text_col} AS text "
        f"FROM {table} WHERE {where_sql} AND CAST({value_col} AS CHAR) IN ({placeholders}) "
        f"{order_sql}"
    )
    rows = db.execute(text(sql), params).mappings().all()
    mapping = {str(row["value"]): str(row["text"]) for row in rows}
    return [mapping.get(k, k) for k in keys]


def _load_sys_dict(db: Session, code: str, keyword: str = "") -> List[Dict[str, Any]]:
    d = db.query(SysDict).filter(SysDict.dict_code == code, SysDict.del_flag == 0).first()
    if not d:
        return []
    q = db.query(SysDictItem).filter(SysDictItem.dict_id == d.id, SysDictItem.status == 1)
    if keyword:
        q = q.filter(SysDictItem.item_text.like(f"%{keyword}%"))
    items = q.order_by(SysDictItem.sort_order).all()
    return [
        {"value": i.item_value, "text": i.item_text, "label": i.item_text}
        for i in items
        if i.item_value is not None
    ]


def _load_sys_dict_items(db: Session, code: str, keys: List[str]) -> List[str]:
    d = db.query(SysDict).filter(SysDict.dict_code == code, SysDict.del_flag == 0).first()
    if not d:
        return keys
    items = (
        db.query(SysDictItem)
        .filter(SysDictItem.dict_id == d.id, SysDictItem.item_value.in_(keys))
        .all()
    )
    mapping = {str(i.item_value): i.item_text or str(i.item_value) for i in items}
    return [mapping.get(k, k) for k in keys]


def load_dict(
    db: Session,
    code: str,
    *,
    keyword: str = "",
    page_no: int = 1,
    page_size: int = 10,
) -> List[Dict[str, Any]]:
    parsed = _parse_dict_code(code)
    if parsed["type"] == "table":
        return _load_table_dict(
            db,
            parsed["table"],
            parsed["text"],
            parsed["value"],
            keyword=keyword,
            page_no=page_no,
            page_size=page_size,
            where_raw=parsed.get("where") or "",
        )
    items = _load_sys_dict(db, parsed["code"], keyword)
    if page_no > 1:
        return []
    return items[: max(page_size, 1)]


def load_dict_item(db: Session, code: str, key: str) -> List[str]:
    keys = [k.strip() for k in (key or "").split(",") if k.strip()]
    parsed = _parse_dict_code(code)
    if parsed["type"] == "table":
        return _load_table_dict_items(
            db,
            parsed["table"],
            parsed["text"],
            parsed["value"],
            keys,
            where_raw=parsed.get("where") or "",
        )
    return _load_sys_dict_items(db, parsed["code"], keys)
