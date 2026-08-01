"""第三方登录业务逻辑。"""
from __future__ import annotations

import random
import secrets
import string
import urllib.parse
from datetime import datetime
from typing import Any, Dict, Optional, Tuple, Union

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_token, encrypt_password, parse_client_password, verify_password
from app.core.third_login_cache import get_value, new_operate_code, pop_value, set_value
from app.models.entities import SysDepart, SysUser, SysUserDepart, SysUserRole
from app.models.third import SysThirdAccount, SysThirdAppConfig
from app.services.dict_service import query_all_dict_items
from app.services.third_oauth_providers import ThirdOAuthProfile, exchange_code
from app.services.user_service import get_user_roles, user_to_dict
from app.utils.common import new_id

THIRD_LOGIN_CODE_KEY = "third_login_operate_code"

from app.services.phone_captcha_service import (  # noqa: E402
    PHONE_CAPTCHA_PREFIX,
    pop_phone_captcha,
    store_phone_captcha,
    validate_phone_captcha,
)


def _now() -> datetime:
    return datetime.now()


def issue_login_token(user: SysUser) -> str:
    return create_token(user.username or "", user.password or "")


def _issue_token(user: SysUser) -> str:
    return issue_login_token(user)


def _login_payload(db: Session, user: SysUser, token: str) -> Dict[str, Any]:
    roles = get_user_roles(db, user.id)
    departs = (
        db.query(SysDepart)
        .join(SysUserDepart, SysUserDepart.dep_id == SysDepart.id)
        .filter(SysUserDepart.user_id == user.id, SysDepart.del_flag == "0")
        .all()
    )
    depart_list = [
        {
            "id": d.id,
            "departName": d.depart_name,
            "orgCode": d.org_code,
            "orgCategory": d.org_category,
        }
        for d in departs
    ]
    return {
        "token": token,
        "userInfo": user_to_dict(user, roles),
        "departs": depart_list,
        "multi_depart": 0 if not departs else (1 if len(departs) == 1 else 2),
        "sysAllDictItems": query_all_dict_items(db),
    }


def _find_third_account(
    db: Session,
    source: str,
    uuid: str,
    tenant_id: int = 0,
) -> Optional[SysThirdAccount]:
    return (
        db.query(SysThirdAccount)
        .filter(
            SysThirdAccount.third_type == source,
            SysThirdAccount.tenant_id == tenant_id,
            SysThirdAccount.del_flag == 0,
            or_(
                SysThirdAccount.third_user_uuid == uuid,
                SysThirdAccount.third_user_id == uuid,
            ),
        )
        .first()
    )


def _save_third_account(
    db: Session,
    profile: ThirdOAuthProfile,
    tenant_id: int = 0,
    sys_user_id: Optional[str] = None,
) -> SysThirdAccount:
    account = _find_third_account(db, profile.source, profile.uuid, tenant_id)
    if account:
        account.realname = profile.username
        account.avatar = profile.avatar
        account.third_user_uuid = profile.uuid
        account.third_user_id = profile.uuid
        account.update_time = _now()
        if sys_user_id:
            account.sys_user_id = sys_user_id
        db.commit()
        db.refresh(account)
        return account

    account = SysThirdAccount(
        id=new_id(),
        sys_user_id=sys_user_id,
        third_type=profile.source,
        third_user_uuid=profile.uuid,
        third_user_id=profile.uuid,
        realname=profile.username,
        avatar=profile.avatar,
        tenant_id=tenant_id,
        del_flag=0,
        create_time=_now(),
        update_time=_now(),
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def _store_operate_session(info: Dict[str, Any]) -> str:
    operate_code = new_operate_code()
    set_value(THIRD_LOGIN_CODE_KEY, operate_code)
    set_value(f"third_session:{operate_code}", info)
    info["operateCode"] = operate_code
    return operate_code


def _validate_operate_code(operate_code: Optional[str]) -> bool:
    if not operate_code:
        return False
    cached = get_value(THIRD_LOGIN_CODE_KEY)
    return cached == operate_code


def _resolve_third_info(data: Dict[str, Any]) -> Dict[str, Any]:
    if "thirdLoginInfo" in data and isinstance(data["thirdLoginInfo"], dict):
        return data["thirdLoginInfo"]
    return data


async def handle_oauth_callback(
    db: Session,
    source: str,
    code: str,
    *,
    tenant_id: int = 0,
) -> Union[str, Dict[str, Any]]:
    profile = await exchange_code(source, code, tenant_id=tenant_id)
    account = _find_third_account(db, source, profile.uuid, tenant_id)
    if not account:
        account = _save_third_account(db, profile, tenant_id)

    if account.sys_user_id:
        user = db.query(SysUser).filter(SysUser.id == account.sys_user_id, SysUser.del_flag == 0).first()
        if user and user.status == 1:
            return _issue_token(user)

    existing_user = db.query(SysUser).filter(SysUser.username == profile.username, SysUser.del_flag == 0).first()
    session_info = {
        "source": source,
        "uuid": profile.uuid,
        "thirdUserUuid": profile.uuid,
        "username": profile.username,
        "avatar": profile.avatar,
        "tenantId": tenant_id,
        "isObj": True,
    }
    _store_operate_session(session_info)

    if existing_user:
        bind_info = dict(session_info)
        bind_info["uuid"] = existing_user.username
        return bind_info

    return f"绑定手机号,{profile.uuid}"


def get_login_user(
    db: Session,
    token: str,
    third_type: str,
    tenant_id: int = 0,
) -> Dict[str, Any]:
    from app.core.security import decode_username, verify_token

    username = decode_username(token)
    if not username:
        raise ValueError("token无效")
    user = db.query(SysUser).filter(SysUser.username == username, SysUser.del_flag == 0).first()
    if not user:
        raise ValueError("用户不存在")
    if not verify_token(token, username, user.password or ""):
        raise ValueError("token验证失败")
    if user.status != 1:
        raise ValueError("用户已冻结")

    account = (
        db.query(SysThirdAccount)
        .filter(
            SysThirdAccount.sys_user_id == user.id,
            SysThirdAccount.third_type == third_type,
            SysThirdAccount.tenant_id == tenant_id,
            SysThirdAccount.del_flag == 0,
        )
        .first()
    )
    if account:
        if not user.realname and account.realname:
            user.realname = account.realname
        if not user.avatar and account.avatar:
            user.avatar = account.avatar

    return _login_payload(db, user, token)


def create_third_user(db: Session, raw: Dict[str, Any]) -> str:
    info = _resolve_third_info(raw)
    if not _validate_operate_code(info.get("operateCode")):
        raise ValueError("校验失败")

    source = info.get("source") or info.get("thirdType")
    uuid = info.get("uuid")
    username = info.get("username") or f"{source}_{uuid}"
    suffix = info.get("suffix")
    if suffix:
        username = f"{username}{suffix}"
    avatar = info.get("avatar") or ""
    tenant_id = int(info.get("tenantId") or 0)

    if db.query(SysUser).filter(SysUser.username == username, SysUser.del_flag == 0).first():
        raise ValueError("用户名已存在")

    salt = "".join(random.choices(string.ascii_letters + string.digits, k=8))
    password_plain = secrets.token_urlsafe(8)
    user = SysUser(
        id=new_id(),
        username=username,
        realname=info.get("username") or username,
        password=encrypt_password(password_plain, username, salt),
        salt=salt,
        avatar=avatar,
        status=1,
        del_flag=0,
        login_tenant_id=tenant_id,
        create_time=_now(),
        update_time=_now(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    _save_third_account(db, ThirdOAuthProfile(source=source, uuid=uuid, username=username, avatar=avatar), tenant_id, user.id)
    pop_value(THIRD_LOGIN_CODE_KEY)
    return _issue_token(user)


def check_password_and_bind(db: Session, raw: Dict[str, Any]) -> str:
    info = _resolve_third_info(raw)
    if not _validate_operate_code(info.get("operateCode")):
        raise ValueError("校验失败")

    bind_username = info.get("uuid")
    password = parse_client_password(info.get("password") or "")
    source = info.get("source") or info.get("thirdType")
    profile_uuid = info.get("thirdUserUuid") or info.get("third_user_uuid")
    tenant_id = int(info.get("tenantId") or 0)

    user = db.query(SysUser).filter(SysUser.username == bind_username, SysUser.del_flag == 0).first()
    if not user:
        raise ValueError("用户未找到")
    if not verify_password(password, user.username or "", user.salt or "", user.password or ""):
        raise ValueError("密码不正确")

    if profile_uuid and source:
        _save_third_account(
            db,
            ThirdOAuthProfile(source=source, uuid=profile_uuid, username=user.username or "", avatar=user.avatar or ""),
            tenant_id,
            user.id,
        )

    pop_value(THIRD_LOGIN_CODE_KEY)
    return _issue_token(user)


def bind_third_phone(db: Session, mobile: str, captcha: str, third_user_uuid: str, tenant_id: int = 0) -> str:
    if not validate_phone_captcha(mobile, captcha):
        raise ValueError("验证码错误")

    account = (
        db.query(SysThirdAccount)
        .filter(
            SysThirdAccount.del_flag == 0,
            or_(
                SysThirdAccount.third_user_uuid == third_user_uuid,
                SysThirdAccount.third_user_id == third_user_uuid,
            ),
        )
        .first()
    )

    user = db.query(SysUser).filter(SysUser.phone == mobile, SysUser.del_flag == 0).first()
    if user:
        if account:
            account.sys_user_id = user.id
            account.update_time = _now()
            db.commit()
    else:
        salt = "".join(random.choices(string.ascii_letters + string.digits, k=8))
        password_plain = secrets.token_urlsafe(8)
        username = mobile
        user = SysUser(
            id=new_id(),
            username=username,
            realname=account.realname if account else username,
            password=encrypt_password(password_plain, username, salt),
            salt=salt,
            avatar=account.avatar if account else "",
            phone=mobile,
            status=1,
            del_flag=0,
            login_tenant_id=tenant_id,
            create_time=_now(),
            update_time=_now(),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        if account:
            account.sys_user_id = user.id
            account.update_time = _now()
            db.commit()

    pop_phone_captcha(mobile)
    return _issue_token(user)


async def oauth2_complete_login(
    db: Session,
    source: str,
    code: str,
    *,
    tenant_id: int = 0,
) -> SysUser:
    profile = await exchange_code(source, code, tenant_id=tenant_id)
    account = _find_third_account(db, source, profile.uuid, tenant_id)
    if account and account.sys_user_id:
        user = db.query(SysUser).filter(SysUser.id == account.sys_user_id, SysUser.del_flag == 0).first()
        if user:
            return user

    user = db.query(SysUser).filter(SysUser.username == profile.username, SysUser.del_flag == 0).first()
    if not user:
        salt = "".join(random.choices(string.ascii_letters + string.digits, k=8))
        password_plain = secrets.token_urlsafe(8)
        username = profile.username or f"{source}_{profile.uuid[-8:]}"
        user = SysUser(
            id=new_id(),
            username=username,
            realname=profile.username or username,
            password=encrypt_password(password_plain, username, salt),
            salt=salt,
            avatar=profile.avatar,
            status=1,
            del_flag=0,
            login_tenant_id=tenant_id,
            create_time=_now(),
            update_time=_now(),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    _save_third_account(db, profile, tenant_id, user.id)
    return user


def safe_redirect_state(state: str) -> str:
    allowed = {settings.frontend_url.rstrip("/"), "http://localhost:3100", "http://127.0.0.1:3100"}
    base = state.split("?", 1)[0].rstrip("/")
    if base not in allowed and not base.startswith(settings.frontend_url.rstrip("/")):
        return settings.frontend_url.rstrip("/")
    return state.split("?", 1)[0]


def build_oauth2_redirect_url(state: str, token: str, tenant_id: str, third_type: str) -> str:
    safe_state = safe_redirect_state(state)
    query = urllib.parse.urlencode(
        {
            "oauth2LoginToken": token,
            "tenantId": tenant_id,
            "thirdType": third_type,
        }
    )
    return f"{safe_state}/oauth2-app/login?{query}"


def get_corp_id_client_id(db: Session, tenant_id: int = 0) -> Optional[Dict[str, str]]:
    config = (
        db.query(SysThirdAppConfig)
        .filter(
            SysThirdAppConfig.tenant_id == tenant_id,
            SysThirdAppConfig.third_type == "dingtalk",
            SysThirdAppConfig.status == 1,
        )
        .first()
    )
    if config and config.client_id:
        return {"corpId": config.corp_id or settings.dingtalk_client_id, "clientId": config.client_id}
    if settings.dingtalk_client_id:
        return {"corpId": settings.dingtalk_client_id, "clientId": settings.dingtalk_client_id}
    return None


def get_third_config_from_db(db: Session, tenant_id: int, third_type: str) -> Optional[SysThirdAppConfig]:
    return (
        db.query(SysThirdAppConfig)
        .filter(
            SysThirdAppConfig.tenant_id == tenant_id,
            SysThirdAppConfig.third_type == third_type,
            SysThirdAppConfig.status == 1,
        )
        .first()
    )
