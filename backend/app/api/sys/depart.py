from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.schemas.response import Result
from app.schemas.sys.depart import DepartBody
from app.db.session import get_db
from app.models.entities import SysDepart, SysUser
from app.utils.common import model_to_dict, new_id

router = APIRouter(prefix="/sysDepart", tags=["部门管理"])


def _depart_path_name(db: Session, org_code: Optional[str], dep_id: Optional[str]) -> str:
    depart: Optional[SysDepart] = None
    if org_code:
        depart = (
            db.query(SysDepart)
            .filter(SysDepart.org_code == org_code, SysDepart.del_flag == "0")
            .first()
        )
    elif dep_id:
        depart = (
            db.query(SysDepart)
            .filter(SysDepart.id == dep_id, SysDepart.del_flag == "0")
            .first()
        )
    if not depart:
        return ""

    names: List[str] = []
    current: Optional[SysDepart] = depart
    seen: set[str] = set()
    while current and current.id not in seen:
        seen.add(current.id)
        if current.depart_name:
            names.append(current.depart_name)
        parent_id = (current.parent_id or "").strip()
        if not parent_id:
            break
        current = (
            db.query(SysDepart)
            .filter(SysDepart.id == parent_id, SysDepart.del_flag == "0")
            .first()
        )
    names.reverse()
    return "/".join(names)


def _depart_sync_nodes(db: Session, pid: Optional[str] = None) -> List[Dict[str, Any]]:
    """异步部门树节点（含岗位树接口在精简版中与部门树一致）。"""
    q = db.query(SysDepart).filter(SysDepart.del_flag == "0")
    if pid:
        q = q.filter(SysDepart.parent_id == pid)
    else:
        q = q.filter((SysDepart.parent_id == "") | (SysDepart.parent_id.is_(None)))
    items = q.order_by(SysDepart.depart_order).all()
    nodes: List[Dict[str, Any]] = []
    for d in items:
        has_child_depart = (
            db.query(SysDepart)
            .filter(SysDepart.parent_id == d.id, SysDepart.del_flag == "0")
            .count()
            > 0
        )
        node = model_to_dict(d)
        node["key"] = d.id
        node["value"] = d.id
        node["title"] = d.depart_name
        node["isLeaf"] = not has_child_depart
        nodes.append(node)
    return nodes


def _build_tree(departs: List[SysDepart], parent_id: Optional[str] = None) -> List[Dict[str, Any]]:
    nodes = []
    for d in departs:
        pid = d.parent_id or ""
        if (parent_id or "") == pid:
            node = model_to_dict(d)
            node["children"] = _build_tree(departs, d.id)
            nodes.append(node)
    return sorted(nodes, key=lambda x: x.get("depart_order") or 0)


@router.get("/queryTreeList")
def query_tree_list(db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    departs = db.query(SysDepart).filter(SysDepart.del_flag == "0").order_by(SysDepart.depart_order).all()
    return Result.ok(_build_tree(departs))


@router.get("/queryDepartTreeSync")
def query_depart_tree_sync(
    pid: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    return Result.ok(_depart_sync_nodes(db, pid))


@router.get("/queryDepartAndPostTreeSync")
def query_depart_and_post_tree_sync(
    pid: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    return Result.ok(_depart_sync_nodes(db, pid))


@router.get("/getDepartPathNameByOrgCode")
def get_depart_path_name_by_org_code(
    orgCode: Optional[str] = Query(None),
    depId: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    path = _depart_path_name(db, (orgCode or "").strip() or None, (depId or "").strip() or None)
    return Result.ok(path)


@router.post("/add")
def add_depart(body: DepartBody, db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    d = SysDepart(
        id=new_id(),
        parent_id=body.parentId,
        depart_name=body.departName or "",
        org_category=body.orgCategory,
        org_code=body.orgCode or new_id()[:12],
        depart_order=body.departOrder,
        status=body.status,
        del_flag="0",
        create_by=user.username,
        create_time=datetime.now(),
    )
    db.add(d)
    db.commit()
    return Result.ok(None, "添加成功！")


@router.put("/edit")
def edit_depart(body: DepartBody, db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    d = db.query(SysDepart).filter(SysDepart.id == body.id).first()
    if not d:
        return Result.error("部门不存在")
    if body.departName:
        d.depart_name = body.departName
    if body.orgCode:
        d.org_code = body.orgCode
    if body.departOrder is not None:
        d.depart_order = body.departOrder
    d.update_by = user.username
    d.update_time = datetime.now()
    db.commit()
    return Result.ok(None, "修改成功！")


@router.delete("/delete")
def delete_depart(id: str = Query(...), db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    d = db.query(SysDepart).filter(SysDepart.id == id).first()
    if d:
        d.del_flag = "1"
        db.commit()
    return Result.ok(None, "删除成功!")
