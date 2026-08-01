from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.entities import SysUser
from app.schemas.response import Result
from app.services.file_storage import resolve_static_file, save_upload_file

router = APIRouter(tags=["通用"])


@router.get("/duplicate/check")
def duplicate_check(
    tableName: str = Query(...),
    fieldName: str = Query(...),
    fieldVal: str = Query(...),
    dataId: str = Query(None),
    db: Session = Depends(get_db),
):
    # 简化：常用表字段唯一性校验
    from app.models.entities import SysUser

    mapping = {
        "sys_user": SysUser,
    }
    model = mapping.get(tableName)
    if not model:
        return Result.ok(True)
    q = db.query(model).filter(getattr(model, _camel_to_snake(fieldName)) == fieldVal)
    if dataId and hasattr(model, "id"):
        q = q.filter(model.id != dataId)
    exists = q.first() is not None
    return Result.ok(not exists)


@router.post("/common/upload")
async def common_upload(
    file: UploadFile = File(...),
    biz: str = Form("temp"),
    user: SysUser = Depends(get_current_user),
):
    """JeecgBoot 兼容上传：message/result 均为相对路径。"""
    try:
        relative = await save_upload_file(file, biz=biz)
        return Result(success=True, code=200, message=relative, result=relative)
    except Exception as exc:
        return Result.error(str(exc))


@router.get("/common/static/{file_path:path}")
def common_static(file_path: str):
    """访问已上传文件（JImageUpload 预览用）。"""
    full = resolve_static_file(file_path)
    return FileResponse(full)


def _camel_to_snake(name: str) -> str:
    import re

    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()
