"""商品类目树 CRUD。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.entities import SysUser
from app.schemas.biz.category import CategoryBody
from app.schemas.response import Result
from app.services import category_service
from app.utils.common import model_to_dict

router = APIRouter(prefix="/category", tags=["商品类目"])


@router.get("/list")
def category_list(
    name: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    items = category_service.list_categories(db, name=name)
    # 名称搜索时仍返回完整树中匹配节点所在分支较复杂，这里：有关键字则返回扁平匹配列表转树
    return Result.ok(category_service.build_tree(items))


@router.get("/tree")
def category_tree(
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    items = category_service.list_categories(db)
    return Result.ok(category_service.build_tree(items))


@router.post("/add")
def add_category(
    body: CategoryBody,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    if not body.name or not body.name.strip():
        return Result.error("类目名称不能为空")
    try:
        row = category_service.create_category(
            db,
            name=body.name,
            parent_id=body.parentId,
            code=body.code,
            sort_no=body.sortNo or 0,
            icon=body.icon,
            description=body.description,
            status=1 if body.status is None else int(body.status),
            username=user.username,
        )
    except ValueError as exc:
        return Result.error(str(exc))
    return Result.ok(model_to_dict(row), "添加成功！")


@router.put("/edit")
@router.post("/edit")
def edit_category(
    body: CategoryBody,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    if not body.id:
        return Result.error("缺少类目ID")
    try:
        row = category_service.update_category(
            db,
            category_id=body.id,
            name=body.name,
            parent_id=body.parentId,
            code=body.code,
            sort_no=body.sortNo,
            icon=body.icon,
            description=body.description,
            status=body.status,
            username=user.username,
        )
    except ValueError as exc:
        return Result.error(str(exc))
    return Result.ok(model_to_dict(row), "修改成功！")


@router.delete("/delete")
def delete_category(
    id: str = Query(...),
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    count = category_service.soft_delete_categories(db, [id])
    if not count:
        return Result.error("类目不存在或已删除")
    return Result.ok(None, "删除成功!")


@router.delete("/deleteBatch")
def delete_batch(
    ids: str = Query(...),
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    id_list = [i.strip() for i in ids.split(",") if i.strip()]
    count = category_service.soft_delete_categories(db, id_list)
    if not count:
        return Result.error("未删除任何数据")
    return Result.ok(None, "删除成功!")
