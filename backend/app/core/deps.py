from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_username, verify_token
from app.core.ttl_cache import TTLCache
from app.db.session import get_db
from app.models.entities import SysUser

_auth_cache: TTLCache[str, SysUser] = TTLCache(
    maxsize=512,
    ttl_seconds=settings.auth_cache_ttl_seconds,
)


def _extract_token(
    request: Request,
    authorization: Optional[str] = Header(None),
    x_access_token: Optional[str] = Header(None, alias="X-Access-Token"),
) -> Optional[str]:
    if x_access_token:
        return x_access_token
    if authorization:
        return authorization.replace("Bearer ", "").strip()
    return None


def _load_user_from_db(db: Session, username: str) -> Optional[SysUser]:
    return (
        db.query(SysUser)
        .filter(SysUser.username == username, SysUser.del_flag == 0)
        .first()
    )


def _cache_user(db: Session, token: str, user: SysUser) -> SysUser:
    db.expunge(user)
    _auth_cache.set(token, user)
    return user


def invalidate_auth_cache(token: Optional[str] = None) -> None:
    if token:
        _auth_cache.delete(token)
    else:
        _auth_cache.clear()


def get_mutable_user(db: Session, user: SysUser) -> SysUser:
    """从当前 DB 会话重新加载用户，供写操作使用（缓存中的 user 已被 expunge）。"""
    attached = (
        db.query(SysUser)
        .filter(SysUser.id == user.id, SysUser.del_flag == 0)
        .first()
    )
    if not attached:
        raise HTTPException(status_code=401, detail="用户不存在")
    return attached


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
    x_access_token: Optional[str] = Header(None, alias="X-Access-Token"),
) -> SysUser:
    token = _extract_token(request, authorization, x_access_token)
    if not token:
        raise HTTPException(status_code=401, detail="未登录")

    username = decode_username(token)
    if not username:
        raise HTTPException(status_code=401, detail="Token无效")

    cached = _auth_cache.get(token)
    if cached:
        if cached.username != username:
            raise HTTPException(status_code=401, detail="Token无效")
        if not verify_token(token, username, cached.password or ""):
            raise HTTPException(status_code=401, detail="Token已失效")
        if cached.status != 1:
            raise HTTPException(status_code=401, detail="用户已冻结")
        return cached

    user = _load_user_from_db(db, username)
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    if not verify_token(token, username, user.password or ""):
        raise HTTPException(status_code=401, detail="Token已失效")
    if user.status != 1:
        raise HTTPException(status_code=401, detail="用户已冻结")
    return _cache_user(db, token, user)


def get_optional_user(
    request: Request,
    db: Session = Depends(get_db),
    authorization: Optional[str] = Header(None),
    x_access_token: Optional[str] = Header(None, alias="X-Access-Token"),
) -> Optional[SysUser]:
    try:
        return get_current_user(request, db, authorization, x_access_token)
    except HTTPException:
        return None
