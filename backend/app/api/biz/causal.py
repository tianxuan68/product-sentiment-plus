"""因果分析：按类目运行 AI 分析 + 结果列表。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.entities import SysUser
from app.schemas.response import Result
from app.services import causal_service

router = APIRouter(prefix="/causal", tags=["因果分析"])


class CausalRunBody(BaseModel):
    categoryId: Optional[str] = None
    categoryName: Optional[str] = Field(default=None, description="类目名称，空则分析全部类目")


@router.get("/list")
def causal_list(
    pageNo: int = Query(1),
    pageSize: int = Query(10),
    categoryName: Optional[str] = None,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    data = causal_service.list_results(
        db, page_no=pageNo, page_size=pageSize, category_name=categoryName
    )
    return Result.ok(data)


@router.post("/run")
def causal_run(
    body: CausalRunBody,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    try:
        data = causal_service.run_analysis(
            db,
            category_id=body.categoryId,
            category_name=body.categoryName,
            username=user.username,
        )
    except ValueError as exc:
        return Result.error(str(exc))
    except Exception as exc:
        return Result.error(f"分析失败：{exc}")
    return Result.ok(data, f"分析完成，共 {data.get('categoryCount') or 0} 个类目")


@router.get("/analyze")
def analyze_get(
    productId: Optional[str] = None,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    """兼容旧接口：即时粗估计（不落库）。"""
    data = causal_service.analyze(db, product_id=productId)
    return Result.ok(data)


@router.post("/analyze")
def analyze_post(
    body: CausalRunBody,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    """兼容：等同 /run。"""
    try:
        data = causal_service.run_analysis(
            db,
            category_id=body.categoryId,
            category_name=body.categoryName,
            username=user.username,
        )
    except ValueError as exc:
        return Result.error(str(exc))
    return Result.ok(data, f"分析完成（来源: {data.get('source')}）")


@router.delete("/delete")
def delete_one(
    id: str = Query(...),
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    count = causal_service.delete_results(db, [id])
    if not count:
        return Result.error("记录不存在")
    return Result.ok(None, "删除成功!")


@router.delete("/deleteBatch")
def delete_batch(
    ids: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    if not ids:
        return Result.error("请选择要删除的记录")
    id_list = [i.strip() for i in ids.split(",") if i.strip()]
    try:
        count = causal_service.delete_results(db, id_list)
    except Exception as exc:
        return Result.error(f"删除失败：{exc}")
    if not count:
        return Result.error("未删除任何数据")
    return Result.ok(None, "删除成功!")
