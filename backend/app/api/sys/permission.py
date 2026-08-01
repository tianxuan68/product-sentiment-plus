from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.schemas.response import Result
from app.schemas.sys.permission import PermissionBody
from app.db.session import get_db
from app.models.entities import SysPermission, SysRolePermission, SysUser
from app.services.permission_service import build_user_permission_payload, invalidate_permission_cache
from app.utils.common import model_to_dict, new_id

router = APIRouter(prefix="/permission", tags=["菜单权限"])


@router.get("/getUserPermissionByToken")
def get_user_permission_by_token(
    user: SysUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return Result.ok(build_user_permission_payload(db, user.id))


@router.get("/list")
def permission_list(
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    items = (
        db.query(SysPermission)
        .filter(SysPermission.del_flag == 0)
        .order_by(SysPermission.sort_no)
        .all()
    )
    return Result.ok([model_to_dict(i) for i in items])


@router.post("/add")
def add_permission(body: PermissionBody, db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    perm = SysPermission(
        id=new_id(),
        parent_id=body.parentId,
        name=body.name,
        url=body.url,
        component=body.component,
        menu_type=body.menuType,
        perms=body.perms,
        sort_no=body.sortNo,
        icon=body.icon,
        status=body.status,
        is_route=body.isRoute,
        hidden=body.hidden,
        keep_alive=body.keepAlive,
        del_flag=0,
        is_leaf=1,
    )
    db.add(perm)
    db.commit()
    invalidate_permission_cache()
    return Result.ok(None, "添加成功！")


@router.put("/edit")
@router.post("/edit")
def edit_permission(body: PermissionBody, db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    perm = db.query(SysPermission).filter(SysPermission.id == body.id).first()
    if not perm:
        return Result.error("菜单不存在")
    for field, attr in [
        ("parentId", "parent_id"),
        ("name", "name"),
        ("url", "url"),
        ("component", "component"),
        ("menuType", "menu_type"),
        ("perms", "perms"),
        ("sortNo", "sort_no"),
        ("icon", "icon"),
        ("status", "status"),
        ("isRoute", "is_route"),
        ("hidden", "hidden"),
        ("keepAlive", "keep_alive"),
    ]:
        val = getattr(body, field, None)
        if val is not None:
            setattr(perm, attr, val)
    db.commit()
    invalidate_permission_cache()
    return Result.ok(None, "修改成功！")


@router.delete("/delete")
def delete_permission(id: str = Query(...), db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    perm = db.query(SysPermission).filter(SysPermission.id == id).first()
    if perm:
        perm.del_flag = 1
        db.commit()
    invalidate_permission_cache()
    return Result.ok(None, "删除成功!")


@router.delete("/deleteBatch")
def delete_batch(ids: str = Query(...), db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    for pid in ids.split(","):
        perm = db.query(SysPermission).filter(SysPermission.id == pid).first()
        if perm:
            perm.del_flag = 1
    db.commit()
    invalidate_permission_cache()
    return Result.ok(None, "删除成功!")


@router.get("/queryRolePermission")
def query_role_permission(roleId: str = Query(...), db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    ids = [
        r.permission_id
        for r in db.query(SysRolePermission).filter(SysRolePermission.role_id == roleId).all()
        if r.permission_id
    ]
    return Result.ok(ids)


@router.post("/saveRolePermission")
def save_role_permission(body: Dict[str, Any], db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    role_id = body.get("roleId")
    permission_ids = body.get("permissionIds", "")
    db.query(SysRolePermission).filter(SysRolePermission.role_id == role_id).delete()
    for pid in permission_ids.split(",") if permission_ids else []:
        if pid.strip():
            db.add(SysRolePermission(id=new_id(), role_id=role_id, permission_id=pid.strip()))
    db.commit()
    invalidate_permission_cache()
    return Result.ok(None, "保存成功！")
