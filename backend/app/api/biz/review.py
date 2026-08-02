"""评价管理（biz_sentiment_query 询问/评价记录）。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.entities import SysUser
from app.schemas.biz.review import ReviewBody
from app.schemas.response import Result
from app.services import review_import_service, review_service

router = APIRouter(prefix="/review", tags=["评价管理"])


@router.get("/list")
def review_list(
    pageNo: int = Query(1),
    pageSize: int = Query(10),
    content: Optional[str] = None,
    productName: Optional[str] = None,
    username: Optional[str] = None,
    sentiment: Optional[str] = None,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    data = review_service.list_reviews(
        db,
        page_no=pageNo,
        page_size=pageSize,
        content=content,
        product_name=productName,
        username=username,
        sentiment=sentiment,
    )
    return Result.ok(data)


@router.post("/add")
def add_review(
    body: ReviewBody,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    try:
        row = review_service.create_review(
            db,
            body.model_dump(exclude_none=False),
            user_id=user.id,
            username=user.username,
        )
    except ValueError as exc:
        return Result.error(str(exc))
    return Result.ok(review_service.review_to_dict(row), "添加成功！")


@router.put("/edit")
@router.post("/edit")
def edit_review(
    body: ReviewBody,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    if not body.id:
        return Result.error("缺少评价ID")
    try:
        row = review_service.update_review(db, body.id, body.model_dump(exclude_unset=True))
    except ValueError as exc:
        return Result.error(str(exc))
    return Result.ok(review_service.review_to_dict(row), "修改成功！")


@router.post("/analyze")
def analyze_review(
    id: str = Query(..., description="评价记录 ID"),
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    """调用 AI BERT 多标签 + 情感分析，回写该条评价。"""
    try:
        data = review_service.analyze_review(db, id)
    except ValueError as exc:
        return Result.error(str(exc))
    except Exception as exc:
        return Result.error(f"评价分析失败：{exc}")
    return Result.ok(data, "分析完成")


@router.delete("/delete")
def delete_review(
    id: str = Query(...),
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    count = review_service.delete_reviews(db, [id])
    if not count:
        return Result.error("记录不存在")
    return Result.ok(None, "删除成功!")


@router.delete("/deleteBatch")
def delete_batch(
    ids: str = Query(...),
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    id_list = [i.strip() for i in ids.split(",") if i.strip()]
    count = review_service.delete_reviews(db, id_list)
    if not count:
        return Result.error("未删除任何数据")
    return Result.ok(None, "删除成功!")


@router.get("/importTemplate")
def download_import_template(user: SysUser = Depends(get_current_user)):
    """下载评价导入 CSV 模板。"""
    content = review_import_service.build_template_csv()
    filename = "evaluation_import_template.csv"
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/importExcel")
async def import_reviews(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    """上传 CSV：先校验扩展名与模板表头，再解析入库。"""
    try:
        data = await review_import_service.import_reviews_file(
            db, file, user_id=user.id, username=user.username
        )
    except ValueError as exc:
        return Result.error(str(exc))
    except Exception as exc:
        return Result.error(f"导入异常：{exc}")
    msg = f"成功导入 {data['successCount']} 条"
    if data.get("failCount"):
        msg += f"，失败 {data['failCount']} 条"
    return Result.ok(data, msg)
