import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session


def new_id() -> str:
    return uuid.uuid4().hex


def _snake_to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def model_to_dict(obj: Any, extra: Optional[Dict] = None) -> Dict[str, Any]:
    data = {}
    for col in obj.__table__.columns:
        val = getattr(obj, col.name)
        if isinstance(val, datetime):
            val = val.strftime("%Y-%m-%d %H:%M:%S")
        data[_snake_to_camel(col.name)] = val
    if extra:
        data.update(extra)
    return data


def paginate_query(query, page_no: int, page_size: int):
    total = query.count()
    items = query.offset((page_no - 1) * page_size).limit(page_size).all()
    return items, total
