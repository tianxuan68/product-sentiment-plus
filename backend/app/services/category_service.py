"""商品类目树：邻接表 + path 物化路径。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.orm import Session

from app.models.biz import BizCategory
from app.utils.common import model_to_dict, new_id


def _now() -> datetime:
    return datetime.now()


def list_categories(db: Session, name: Optional[str] = None) -> List[BizCategory]:
    q = db.query(BizCategory).filter(BizCategory.del_flag == 0)
    if name and name.strip():
        q = q.filter(BizCategory.name.contains(name.strip()))
    return q.order_by(BizCategory.sort_no.asc(), BizCategory.create_time.asc()).all()


def build_tree(items: List[BizCategory]) -> List[Dict[str, Any]]:
    nodes = [{**model_to_dict(i), "children": []} for i in items]
    by_id = {n["id"]: n for n in nodes}
    roots: List[Dict[str, Any]] = []
    for n in nodes:
        pid = n.get("parentId") or ""
        parent = by_id.get(pid) if pid else None
        if parent is not None:
            parent["children"].append(n)
        else:
            roots.append(n)

    def prune(arr: List[Dict[str, Any]]) -> None:
        for node in arr:
            children = node.get("children") or []
            if children:
                prune(children)
            else:
                node.pop("children", None)

    prune(roots)
    return roots


def get_category(db: Session, category_id: str) -> Optional[BizCategory]:
    return (
        db.query(BizCategory)
        .filter(BizCategory.id == category_id, BizCategory.del_flag == 0)
        .first()
    )


def _refresh_parent_leaf(db: Session, parent_id: Optional[str]) -> None:
    if not parent_id:
        return
    parent = get_category(db, parent_id)
    if not parent:
        return
    child_count = (
        db.query(BizCategory)
        .filter(
            BizCategory.parent_id == parent_id,
            BizCategory.del_flag == 0,
        )
        .count()
    )
    parent.is_leaf = 1 if child_count == 0 else 0


def _collect_descendants(db: Session, root_id: str) -> List[BizCategory]:
    all_rows = list_categories(db)
    by_parent: Dict[str, List[BizCategory]] = {}
    for row in all_rows:
        pid = row.parent_id or ""
        by_parent.setdefault(pid, []).append(row)
    result: List[BizCategory] = []

    def walk(pid: str) -> None:
        for child in by_parent.get(pid, []):
            result.append(child)
            walk(child.id)

    walk(root_id)
    return result


def create_category(
    db: Session,
    *,
    name: str,
    parent_id: Optional[str] = None,
    code: Optional[str] = None,
    sort_no: int = 0,
    icon: Optional[str] = None,
    description: Optional[str] = None,
    status: int = 1,
    username: Optional[str] = None,
) -> BizCategory:
    parent_id = (parent_id or "").strip()
    parent = get_category(db, parent_id) if parent_id else None
    if parent_id and not parent:
        raise ValueError("上级类目不存在")

    cid = new_id()
    level = (parent.level or 1) + 1 if parent else 1
    path = f"{parent.path}{cid}/" if parent and parent.path else f"/{cid}/"

    row = BizCategory(
        id=cid,
        parent_id=parent_id,
        name=name.strip(),
        code=(code or "").strip() or None,
        path=path,
        level=level,
        sort_no=sort_no or 0,
        icon=icon,
        description=description,
        is_leaf=1,
        status=1 if status is None else int(status),
        del_flag=0,
        create_by=username,
        create_time=_now(),
    )
    db.add(row)
    if parent:
        parent.is_leaf = 0
        parent.update_time = _now()
    db.commit()
    db.refresh(row)
    return row


def update_category(
    db: Session,
    *,
    category_id: str,
    name: Optional[str] = None,
    parent_id: Optional[str] = None,
    code: Optional[str] = None,
    sort_no: Optional[int] = None,
    icon: Optional[str] = None,
    description: Optional[str] = None,
    status: Optional[int] = None,
    username: Optional[str] = None,
) -> BizCategory:
    row = get_category(db, category_id)
    if not row:
        raise ValueError("类目不存在")

    old_parent_id = row.parent_id or ""
    new_parent_id = old_parent_id if parent_id is None else (parent_id or "").strip()

    if new_parent_id == row.id:
        raise ValueError("上级类目不能是自己")
    if new_parent_id:
        descendants = {d.id for d in _collect_descendants(db, row.id)}
        if new_parent_id in descendants:
            raise ValueError("上级类目不能是自己的下级")

    if name is not None:
        row.name = name.strip()
    if code is not None:
        row.code = code.strip() or None
    if sort_no is not None:
        row.sort_no = sort_no
    if icon is not None:
        row.icon = icon
    if description is not None:
        row.description = description
    if status is not None:
        row.status = int(status)

    parent_changed = new_parent_id != old_parent_id
    descendants = _collect_descendants(db, row.id) if parent_changed else []
    if parent_changed:
        parent = get_category(db, new_parent_id) if new_parent_id else None
        if new_parent_id and not parent:
            raise ValueError("上级类目不存在")
        row.parent_id = new_parent_id
        row.level = (parent.level or 1) + 1 if parent else 1
        row.path = f"{parent.path}{row.id}/" if parent and parent.path else f"/{row.id}/"
        # 按原树序重算子孙 path/level（父节点已更新）
        path_map = {row.id: (row.path or f"/{row.id}/", row.level or 1)}
        for child in descendants:
            p_path, p_level = path_map.get(child.parent_id or "", ("/", 0))
            child.level = p_level + 1
            child.path = f"{p_path}{child.id}/"
            path_map[child.id] = (child.path, child.level)

    row.update_by = username
    row.update_time = _now()
    db.commit()

    if parent_changed:
        _refresh_parent_leaf(db, old_parent_id)
        _refresh_parent_leaf(db, new_parent_id)
        db.commit()

    db.refresh(row)
    return row


def soft_delete_categories(db: Session, ids: List[str]) -> int:
    id_set: Set[str] = {i for i in ids if i}
    if not id_set:
        return 0

    # 连带删除子孙
    all_delete: Set[str] = set(id_set)
    for cid in list(id_set):
        for d in _collect_descendants(db, cid):
            all_delete.add(d.id)

    parents_to_refresh: Set[str] = set()
    rows = (
        db.query(BizCategory)
        .filter(BizCategory.id.in_(all_delete), BizCategory.del_flag == 0)
        .all()
    )
    for row in rows:
        if row.parent_id:
            parents_to_refresh.add(row.parent_id)
        row.del_flag = 1
        row.update_time = _now()

    db.commit()
    for pid in parents_to_refresh:
        if pid not in all_delete:
            _refresh_parent_leaf(db, pid)
    db.commit()
    return len(rows)
