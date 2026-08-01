from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import is_http_url, md5_hex, url_to_route_name
from app.core.ttl_cache import TTLCache
from app.models.entities import SysPermission

_permission_payload_cache: TTLCache[str, Dict[str, Any]] = TTLCache(
    maxsize=256,
    ttl_seconds=settings.permission_cache_ttl_seconds,
)
_all_auth_cache: TTLCache[str, List[Dict[str, Any]]] = TTLCache(
    maxsize=1,
    ttl_seconds=settings.permission_cache_ttl_seconds,
)
_ALL_AUTH_KEY = "all"


def invalidate_permission_cache(user_id: Optional[str] = None) -> None:
    if user_id:
        _permission_payload_cache.delete(user_id)
    else:
        _permission_payload_cache.clear()
    _all_auth_cache.clear()


def query_permissions_by_user(db: Session, user_id: str) -> List[SysPermission]:
    sql = text(
        """
        SELECT DISTINCT p.* FROM sys_permission p
        INNER JOIN sys_role_permission rp ON rp.permission_id = p.id
        INNER JOIN sys_role r ON rp.role_id = r.id
        INNER JOIN sys_user_role ur ON ur.role_id = r.id AND ur.user_id = :user_id
        WHERE p.del_flag = 0
        ORDER BY p.sort_no
        """
    )
    rows = db.execute(sql, {"user_id": user_id}).mappings().all()
    return [_row_to_permission(r) for r in rows]


def _row_to_permission(row) -> SysPermission:
    p = SysPermission()
    for k, v in row.items():
        if hasattr(p, k):
            setattr(p, k, v)
    return p


def get_all_auth_list(db: Session) -> List[Dict[str, Any]]:
    cached = _all_auth_cache.get(_ALL_AUTH_KEY)
    if cached is not None:
        return cached

    all_buttons = (
        db.query(SysPermission)
        .filter(SysPermission.del_flag == 0, SysPermission.menu_type == 2)
        .all()
    )
    result = build_all_auth_list(all_buttons)
    _all_auth_cache.set(_ALL_AUTH_KEY, result)
    return result


def build_user_permission_payload(db: Session, user_id: str) -> Dict[str, Any]:
    cached = _permission_payload_cache.get(user_id)
    if cached is not None:
        return cached

    meta_list = query_permissions_by_user(db, user_id)
    payload = {
        "menu": build_menu_tree(meta_list),
        "auth": build_auth_list(meta_list),
        "codeList": [p.perms for p in meta_list if p.menu_type == 2 and p.status == "1" and p.perms],
        "allAuth": get_all_auth_list(db),
        "sysSafeMode": False,
    }
    _permission_payload_cache.set(user_id, payload)
    return payload


def build_menu_tree(meta_list: List[SysPermission]) -> List[Dict[str, Any]]:
    menus = [p for p in meta_list if p.menu_type in (0, 1)]
    by_parent: Dict[str, List[SysPermission]] = {}
    for m in menus:
        pid = m.parent_id or ""
        by_parent.setdefault(pid, []).append(m)

    def build_level(parent_id: str) -> List[Dict[str, Any]]:
        nodes: List[Dict[str, Any]] = []
        for perm in sorted(by_parent.get(parent_id, []), key=lambda x: (x.sort_no or 0)):
            node = _permission_to_route_json(perm)
            if not node:
                continue
            if not _is_leaf(perm):
                children = build_level(perm.id)
                if children:
                    node["children"] = children
            nodes.append(node)
        return nodes

    return build_level("")


def _permission_to_route_json(permission: SysPermission) -> Optional[Dict[str, Any]]:
    if permission.menu_type == 2:
        return None
    if permission.menu_type not in (0, 1):
        return None

    json_obj: Dict[str, Any] = {"id": permission.id}
    json_obj["route"] = "1" if permission.is_route == 1 else "0"

    if is_http_url(permission.url or ""):
        json_obj["path"] = md5_hex(permission.url or "")
    else:
        json_obj["path"] = permission.url

    if permission.component_name:
        json_obj["name"] = permission.component_name
    else:
        json_obj["name"] = url_to_route_name(permission.url or "")

    meta: Dict[str, Any] = {}
    if permission.hidden == 1:
        json_obj["hidden"] = True
        meta["hideMenu"] = True
    if permission.always_show == 1:
        json_obj["alwaysShow"] = True

    json_obj["component"] = permission.component
    meta["keepAlive"] = bool(permission.keep_alive == 1)
    meta["internalOrExternal"] = bool(permission.internal_or_external == 1)
    meta["title"] = permission.name

    component = permission.component or ""
    if permission.component_name or component:
        meta["componentName"] = permission.component_name or (
            component.split("/")[-1] if "/" in component else component
        )

    if not permission.parent_id:
        if permission.redirect:
            json_obj["redirect"] = permission.redirect
        if permission.icon:
            meta["icon"] = permission.icon
    else:
        if permission.icon:
            meta["icon"] = permission.icon

    if is_http_url(permission.url or ""):
        meta["url"] = permission.url
    if permission.hide_tab == 1:
        meta["hideTab"] = True

    json_obj["meta"] = meta
    return json_obj


def _is_leaf(permission: SysPermission) -> bool:
    return permission.is_leaf == 1


def build_auth_list(meta_list: List[SysPermission]) -> List[Dict[str, Any]]:
    auth = []
    for p in meta_list:
        if p.menu_type == 2 and p.status == "1":
            auth.append(
                {
                    "action": p.perms,
                    "type": p.perms_type,
                    "describe": p.name,
                }
            )
    return auth


def build_all_auth_list(all_buttons: List[SysPermission]) -> List[Dict[str, Any]]:
    return [
        {
            "action": p.perms,
            "status": p.status,
            "type": p.perms_type,
            "describe": p.name,
        }
        for p in all_buttons
    ]
