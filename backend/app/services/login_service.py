"""登录相关业务逻辑。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.security import create_token, parse_client_password, verify_password
from app.models.entities import SysDepart, SysUser, SysUserDepart
from app.services.dict_service import query_all_dict_items
from app.services.phone_captcha_service import validate_phone_captcha
from app.services.user_service import get_user_roles, user_to_dict


def get_user_departs(db: Session, user_id: str) -> List[SysDepart]:
    return (
        db.query(SysDepart)
        .join(SysUserDepart, SysUserDepart.dep_id == SysDepart.id)
        .filter(SysUserDepart.user_id == user_id, SysDepart.del_flag == "0")
        .all()
    )


def depart_list_for_user(db: Session, user_id: str) -> List[Dict[str, Any]]:
    return [
        {
            "id": d.id,
            "departName": d.depart_name,
            "orgCode": d.org_code,
            "orgCategory": d.org_category,
        }
        for d in get_user_departs(db, user_id)
    ]


def apply_login_org_code(db: Session, user: SysUser, login_org_code: Optional[str]) -> None:
    if not login_org_code:
        return
    valid_codes = {d.org_code for d in get_user_departs(db, user.id)}
    if login_org_code in valid_codes:
        user.org_code = login_org_code
        user.update_time = datetime.now()
        db.commit()
        db.refresh(user)


def build_login_response(db: Session, user: SysUser, token: Optional[str] = None) -> Dict[str, Any]:
    token = token or create_token(user.username or "", user.password or "")
    departs = depart_list_for_user(db, user.id)
    roles = get_user_roles(db, user.id)
    return {
        "token": token,
        "userInfo": user_to_dict(user, roles),
        "departs": departs,
        "multi_depart": 0 if not departs else (1 if len(departs) == 1 else 2),
        "sysAllDictItems": query_all_dict_items(db),
    }


def build_user_departs_result(db: Session, user: SysUser) -> Dict[str, Any]:
    return {
        "departs": depart_list_for_user(db, user.id),
        "currentOrgCode": user.org_code,
    }


def authenticate_account(db: Session, username: str, password: str) -> SysUser:
    plain = parse_client_password(password)
    user = db.query(SysUser).filter(SysUser.username == username).first()
    if not user or user.del_flag == 1:
        raise ValueError("用户名或密码错误（默认账号 admin / 123456）")
    if user.status != 1:
        raise ValueError("用户已冻结")
    if not verify_password(plain, username, user.salt or "", user.password or ""):
        raise ValueError("用户名或密码错误（刷库后默认密码为 123456）")
    return user


def authenticate_phone(db: Session, mobile: str, captcha: str) -> SysUser:
    if not validate_phone_captcha(mobile, captcha):
        raise ValueError("验证码错误")
    user = db.query(SysUser).filter(SysUser.phone == mobile, SysUser.del_flag == 0).first()
    if not user:
        raise ValueError("该手机号未注册")
    if user.status != 1:
        raise ValueError("用户已冻结")
    return user
