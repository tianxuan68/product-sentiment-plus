"""商品信息 CRUD。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.entities import SysUser
from app.schemas.biz.product import ProductBody
from app.schemas.response import Result
from app.services import product_service

router = APIRouter(prefix="/product", tags=["商品信息"])


@router.get("/brands")
def product_brands(
    categoryId: Optional[str] = None,
    status: Optional[int] = 1,
    limit: int = Query(80, ge=1, le=200),
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    """手机选品左侧/品牌面板：去重品牌列表。"""
    data = product_service.list_brands(
        db, category_id=categoryId, status=status, limit=limit
    )
    return Result.ok(data)


@router.get("/list")
def product_list(
    pageNo: int = Query(1),
    pageSize: int = Query(10),
    name: Optional[str] = None,
    brand: Optional[str] = None,
    sku: Optional[str] = None,
    categoryId: Optional[str] = None,
    status: Optional[int] = None,
    keyword: Optional[str] = None,
    column: Optional[str] = None,
    order: Optional[str] = None,
    withStats: Optional[bool] = Query(False),
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    data = product_service.list_products(
        db,
        page_no=pageNo,
        page_size=pageSize,
        name=name,
        brand=brand,
        sku=sku,
        category_id=categoryId,
        status=status,
        keyword=keyword,
        column=column,
        order=order,
        with_stats=bool(withStats),
    )
    return Result.ok(data)


@router.post("/add")
def add_product(
    body: ProductBody,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    try:
        row = product_service.create_product(db, body.model_dump(exclude_none=False), user.username)
    except ValueError as exc:
        return Result.error(str(exc))
    return Result.ok(product_service.product_to_dict(db, row), "添加成功！")


@router.put("/edit")
@router.post("/edit")
def edit_product(
    body: ProductBody,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    if not body.id:
        return Result.error("缺少商品ID")
    try:
        row = product_service.update_product(db, body.id, body.model_dump(exclude_unset=True), user.username)
    except ValueError as exc:
        return Result.error(str(exc))
    return Result.ok(product_service.product_to_dict(db, row), "修改成功！")


@router.delete("/delete")
def delete_product(
    id: str = Query(...),
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    count = product_service.soft_delete_products(db, [id])
    if not count:
        return Result.error("商品不存在或已删除")
    return Result.ok(None, "删除成功!")


@router.delete("/deleteBatch")
def delete_batch(
    ids: str = Query(...),
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    id_list = [i.strip() for i in ids.split(",") if i.strip()]
    count = product_service.soft_delete_products(db, id_list)
    if not count:
        return Result.error("未删除任何数据")
    return Result.ok(None, "删除成功!")
