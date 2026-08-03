"""评价看板统计接口。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.entities import SysUser
from app.schemas.response import Result
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["评价看板"])


@router.get("/overview")
def overview(
    productId: Optional[str] = None,
    days: Optional[int] = Query(None, ge=1, le=3650),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    data = dashboard_service.overview(db, product_id=productId, days=days, tag_limit=limit)
    return Result.ok(data)


@router.get("/tagTop")
def tag_top(
    limit: int = Query(10, ge=1, le=50),
    productId: Optional[str] = None,
    days: Optional[int] = Query(None, ge=1, le=3650),
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    data = dashboard_service.tag_top(db, limit=limit, product_id=productId, days=days)
    return Result.ok(data)


@router.get("/summary")
def summary(
    productId: Optional[str] = None,
    days: Optional[int] = Query(None, ge=1, le=3650),
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    data = dashboard_service.summary(db, product_id=productId, days=days)
    return Result.ok(data)
