from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.schemas.response import PageResult, Result
from app.schemas.sys.role import RoleBody
from app.db.session import get_db
from app.models.entities import SysRole, SysUser
from app.utils.common import model_to_dict, new_id, paginate_query

router = APIRouter(prefix="/role", tags=["角色管理"])


@router.get("/list")
def role_list(
    pageNo: int = Query(1),
    pageSize: int = Query(10),
    roleName: Optional[str] = None,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    q = db.query(SysRole)
    if roleName:
        q = q.filter(SysRole.role_name.like(f"%{roleName}%"))
    items, total = paginate_query(q.order_by(SysRole.create_time.desc()), pageNo, pageSize)
    return Result.ok(PageResult.build([model_to_dict(r) for r in items], total, pageNo, pageSize).model_dump())


@router.get("/queryall")
def query_all_roles(db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    roles = db.query(SysRole).all()
    return Result.ok([model_to_dict(r) for r in roles])


@router.post("/add")
def add_role(body: RoleBody, db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    r = SysRole(
        id=new_id(),
        role_name=body.roleName,
        role_code=body.roleCode,
        description=body.description,
        create_by=user.username,
        create_time=datetime.now(),
    )
    db.add(r)
    db.commit()
    return Result.ok(None, "添加成功！")


@router.post("/edit")
def edit_role(body: RoleBody, db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    r = db.query(SysRole).filter(SysRole.id == body.id).first()
    if not r:
        return Result.error("角色不存在")
    if body.roleName:
        r.role_name = body.roleName
    if body.roleCode:
        r.role_code = body.roleCode
    if body.description:
        r.description = body.description
    r.update_by = user.username
    r.update_time = datetime.now()
    db.commit()
    return Result.ok(None, "修改成功！")


@router.delete("/delete")
def delete_role(id: str = Query(...), db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    r = db.query(SysRole).filter(SysRole.id == id).first()
    if r:
        db.delete(r)
        db.commit()
    return Result.ok(None, "删除成功!")
