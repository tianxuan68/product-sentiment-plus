"""第三方用户绑定/创建 API。"""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.response import Result
from app.services.third_login_service import check_password_and_bind, create_third_user

router = APIRouter(tags=["第三方用户"])


@router.post("/third/user/create")
async def third_user_create(body: Dict[str, Any], db: Session = Depends(get_db)):
    try:
        token = create_third_user(db, body)
        return Result.ok(token)
    except ValueError as exc:
        return Result.error(str(exc))


@router.post("/third/user/checkPassword")
async def third_user_check_password(body: Dict[str, Any], db: Session = Depends(get_db)):
    try:
        token = check_password_and_bind(db, body)
        return Result.ok(token)
    except ValueError as exc:
        return Result.error(str(exc))
