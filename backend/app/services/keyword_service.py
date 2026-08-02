"""方面关键词词典 CRUD（按类目 / 通用）。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.biz import BizCategory, BizKeyword
from app.schemas.response import PageResult
from app.utils.common import model_to_dict, new_id, paginate_query

_POLARITY_TEXT = {
    "positive": "正向",
    "negative": "负向",
    "neutral": "中性",
    "any": "不限",
}

# 表单约定：__general__ 表示通用关键词
GENERAL_CATEGORY_ID = "__general__"


def _now() -> datetime:
    return datetime.now()


def _resolve_category(db: Session, data: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """解析类目：空 / __general__ → 通用；否则按 id 或 name 查库。"""
    raw_id = data.get("categoryId")
    raw_name = data.get("categoryName")
    cid = str(raw_id).strip() if raw_id is not None else ""
    cname = str(raw_name).strip() if raw_name is not None else ""

    if not cid or cid == GENERAL_CATEGORY_ID or cname in ("通用", "不限", "*"):
        return None, None

    row = db.query(BizCategory).filter(BizCategory.id == cid, BizCategory.del_flag == 0).first()
    if row:
        return row.id, row.name

    if cname:
        row = (
            db.query(BizCategory)
            .filter(BizCategory.name == cname, BizCategory.del_flag == 0)
            .first()
        )
        if row:
            return row.id, row.name
        return None, cname

    raise ValueError("类目不存在")


def keyword_to_dict(row: BizKeyword) -> Dict[str, Any]:
    data = model_to_dict(row)
    data["polarity_dictText"] = _POLARITY_TEXT.get(str(row.polarity or "any").lower(), row.polarity or "")
    data["status_dictText"] = "启用" if row.status == 1 else "停用"
    is_general = not (row.category_id and str(row.category_id).strip())
    data["categoryScope"] = "general" if is_general else "category"
    data["categoryLabel"] = "通用" if is_general else (row.category_name or row.category_id or "-")
    # 表单回填：通用用哨兵值，便于 Select
    data["categoryId"] = GENERAL_CATEGORY_ID if is_general else (row.category_id or GENERAL_CATEGORY_ID)
    return data


def list_keywords(
    db: Session,
    *,
    page_no: int = 1,
    page_size: int = 10,
    word: Optional[str] = None,
    aspect: Optional[str] = None,
    category_id: Optional[str] = None,
    category_name: Optional[str] = None,
    include_general: bool = False,
    polarity: Optional[str] = None,
    status: Optional[int] = None,
) -> Dict[str, Any]:
    q = db.query(BizKeyword).filter(BizKeyword.del_flag == 0)
    if word and word.strip():
        q = q.filter(BizKeyword.word.contains(word.strip()))
    if aspect and aspect.strip():
        q = q.filter(BizKeyword.aspect.contains(aspect.strip()))

    cid = (category_id or "").strip()
    cname = (category_name or "").strip()
    if cid == GENERAL_CATEGORY_ID or cname in ("通用", "*"):
        q = q.filter(or_(BizKeyword.category_id.is_(None), BizKeyword.category_id == ""))
    elif cid:
        if include_general:
            q = q.filter(
                or_(
                    BizKeyword.category_id == cid,
                    BizKeyword.category_id.is_(None),
                    BizKeyword.category_id == "",
                )
            )
        else:
            q = q.filter(BizKeyword.category_id == cid)
    elif cname:
        if include_general:
            q = q.filter(
                or_(
                    BizKeyword.category_name == cname,
                    BizKeyword.category_id.is_(None),
                    BizKeyword.category_id == "",
                )
            )
        else:
            q = q.filter(BizKeyword.category_name == cname)

    if polarity and polarity.strip():
        q = q.filter(BizKeyword.polarity == polarity.strip())
    if status is not None and str(status) != "":
        q = q.filter(BizKeyword.status == int(status))
    q = q.order_by(BizKeyword.sort_no.asc(), BizKeyword.create_time.desc())
    items, total = paginate_query(q, page_no, page_size)
    return PageResult.build([keyword_to_dict(i) for i in items], total, page_no, page_size).model_dump()


def _exists_same_scope(db: Session, word: str, category_id: Optional[str], exclude_id: Optional[str] = None) -> bool:
    q = db.query(BizKeyword).filter(BizKeyword.word == word, BizKeyword.del_flag == 0)
    if category_id:
        q = q.filter(BizKeyword.category_id == category_id)
    else:
        q = q.filter(or_(BizKeyword.category_id.is_(None), BizKeyword.category_id == ""))
    if exclude_id:
        q = q.filter(BizKeyword.id != exclude_id)
    return q.first() is not None


def create_keyword(db: Session, data: Dict[str, Any], username: Optional[str] = None) -> BizKeyword:
    word = str(data.get("word") or "").strip()
    if not word:
        raise ValueError("关键词不能为空")
    category_id, category_name = _resolve_category(db, data)
    if _exists_same_scope(db, word, category_id):
        scope = "通用" if not category_id else category_name
        raise ValueError(f"该关键词在「{scope}」下已存在")
    row = BizKeyword(
        id=new_id(),
        word=word,
        aspect=(str(data.get("aspect") or "").strip() or None),
        category_id=category_id,
        category_name=category_name,
        polarity=(str(data.get("polarity") or "any").strip() or "any"),
        alias=(str(data.get("alias") or "").strip() or None),
        weight=int(data.get("weight") or 1),
        status=1 if data.get("status") is None else int(data.get("status")),
        sort_no=int(data.get("sortNo") or 0),
        remark=(str(data.get("remark") or "").strip() or None),
        del_flag=0,
        create_by=username,
        create_time=_now(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_keyword(db: Session, kid: str, data: Dict[str, Any], username: Optional[str] = None) -> BizKeyword:
    row = db.query(BizKeyword).filter(BizKeyword.id == kid, BizKeyword.del_flag == 0).first()
    if not row:
        raise ValueError("关键词不存在")

    word = row.word
    if "word" in data and data.get("word") is not None:
        word = str(data.get("word") or "").strip()
        if not word:
            raise ValueError("关键词不能为空")

    category_id, category_name = row.category_id, row.category_name
    if "categoryId" in data or "categoryName" in data:
        category_id, category_name = _resolve_category(db, data)

    if _exists_same_scope(db, word, category_id, exclude_id=kid):
        scope = "通用" if not category_id else category_name
        raise ValueError(f"该关键词在「{scope}」下已存在")

    row.word = word
    row.category_id = category_id
    row.category_name = category_name
    if "aspect" in data:
        row.aspect = (str(data.get("aspect") or "").strip() or None)
    if "polarity" in data:
        row.polarity = (str(data.get("polarity") or "any").strip() or "any")
    if "alias" in data:
        row.alias = (str(data.get("alias") or "").strip() or None)
    if "weight" in data and data.get("weight") is not None:
        row.weight = int(data.get("weight") or 1)
    if "status" in data and data.get("status") is not None:
        row.status = int(data.get("status"))
    if "sortNo" in data and data.get("sortNo") is not None:
        row.sort_no = int(data.get("sortNo") or 0)
    if "remark" in data:
        row.remark = (str(data.get("remark") or "").strip() or None)
    row.update_by = username
    row.update_time = _now()
    db.commit()
    db.refresh(row)
    return row


def soft_delete_keywords(db: Session, ids: List[str]) -> int:
    id_list = [i for i in ids if i]
    if not id_list:
        return 0
    count = (
        db.query(BizKeyword)
        .filter(BizKeyword.id.in_(id_list), BizKeyword.del_flag == 0)
        .update({BizKeyword.del_flag: 1, BizKeyword.update_time: _now()}, synchronize_session=False)
    )
    db.commit()
    return int(count or 0)
