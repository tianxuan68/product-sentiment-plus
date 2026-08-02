"""关键词管理 CRUD。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.entities import SysUser
from app.schemas.biz.keyword import KeywordBody
from app.schemas.response import Result
from app.services import keyword_service

router = APIRouter(prefix="/keyword", tags=["关键词管理"])


@router.get("/list")
def keyword_list(
    pageNo: int = Query(1),
    pageSize: int = Query(10),
    word: Optional[str] = None,
    aspect: Optional[str] = None,
    categoryId: Optional[str] = None,
    categoryName: Optional[str] = None,
    includeGeneral: bool = Query(False, description="按类目筛选时是否附带通用词"),
    polarity: Optional[str] = None,
    status: Optional[int] = None,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    data = keyword_service.list_keywords(
        db,
        page_no=pageNo,
        page_size=pageSize,
        word=word,
        aspect=aspect,
        category_id=categoryId,
        category_name=categoryName,
        include_general=includeGeneral,
        polarity=polarity,
        status=status,
    )
    return Result.ok(data)


@router.get("/options")
def keyword_options(
    categoryId: Optional[str] = None,
    categoryName: Optional[str] = None,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    """下拉选项：启用中的关键词（指定类目时含通用）。"""
    data = keyword_service.list_keywords(
        db,
        page_no=1,
        page_size=500,
        category_id=categoryId,
        category_name=categoryName,
        include_general=bool(categoryId or categoryName),
        status=1,
    )
    records = data.get("records") or []
    options = []
    seen = set()
    for r in records:
        word = str(r.get("word") or "").strip()
        if not word or word in seen:
            continue
        seen.add(word)
        label = word
        cat = r.get("categoryLabel") or "通用"
        if cat and cat != "通用":
            label = f"{word}（{cat}）"
        options.append({"label": label, "value": word, "categoryLabel": cat})
    return Result.ok(options)


@router.post("/add")
def add_keyword(
    body: KeywordBody,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    try:
        row = keyword_service.create_keyword(db, body.model_dump(exclude_none=False), user.username)
    except ValueError as exc:
        return Result.error(str(exc))
    return Result.ok(keyword_service.keyword_to_dict(row), "添加成功！")


@router.put("/edit")
@router.post("/edit")
def edit_keyword(
    body: KeywordBody,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    if not body.id:
        return Result.error("缺少关键词ID")
    try:
        row = keyword_service.update_keyword(db, body.id, body.model_dump(exclude_unset=True), user.username)
    except ValueError as exc:
        return Result.error(str(exc))
    return Result.ok(keyword_service.keyword_to_dict(row), "修改成功！")


@router.delete("/delete")
def delete_keyword(
    id: str = Query(...),
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    count = keyword_service.soft_delete_keywords(db, [id])
    if not count:
        return Result.error("关键词不存在或已删除")
    return Result.ok(None, "删除成功!")


@router.delete("/deleteBatch")
def delete_batch(
    ids: str = Query(...),
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    id_list = [i.strip() for i in ids.split(",") if i.strip()]
    count = keyword_service.soft_delete_keywords(db, id_list)
    if not count:
        return Result.error("未删除任何数据")
    return Result.ok(None, "删除成功!")
