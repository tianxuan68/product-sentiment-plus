"""系统日志（精简版占位）。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.entities import SysUser
from app.schemas.response import PageResult, Result

router = APIRouter(prefix="/log", tags=["系统日志"])


@router.get("/list")
def log_list(
    pageNo: int = Query(1),
    pageSize: int = Query(10),
    logType: Optional[str] = None,
    keyWord: Optional[str] = None,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    """精简版暂无 sys_log 表，返回空列表保证页面可正常打开。"""
    return Result.ok(PageResult.build([], 0, pageNo, pageSize).model_dump())
