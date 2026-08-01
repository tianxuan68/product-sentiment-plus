from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import encrypt_password, parse_client_password
from app.core.ttl_cache import TTLCache
from app.models.entities import SysRole, SysUser, SysUserRole
from app.utils.common import new_id

from app.services.phone_captcha_service import get_phone_captcha, pop_phone_captcha, validate_phone_captcha

DEFAULT_REGISTER_ROLE_ID = "f6817f48af4fb3af11b9e8bf182f618b"
DEFAULT_HOME_PATH = "/system/user"


_user_roles_cache: TTLCache[str, List[SysRole]] = TTLCache(
    maxsize=256,
    ttl_seconds=settings.user_roles_cache_ttl_seconds,
)


def invalidate_user_roles_cache(user_id: Optional[str] = None) -> None:
    if user_id:
        _user_roles_cache.delete(user_id)
    else:
        _user_roles_cache.clear()


def resolve_home_path(roles: Optional[List[SysRole]]) -> str:
    return DEFAULT_HOME_PATH


def user_to_dict(user: SysUser, roles: Optional[List[SysRole]] = None) -> Dict[str, Any]:
    data = {
        "id": user.id,
        "username": user.username,
        "realname": user.realname,
        "avatar": user.avatar,
        "birthday": user.birthday.isoformat() if user.birthday else None,
        "sex": user.sex,
        "email": user.email,
        "phone": user.phone,
        "orgCode": user.org_code,
        "status": user.status,
        "workNo": user.work_no,
        "loginTenantId": user.login_tenant_id or 0,
        "homePath": resolve_home_path(roles),
    }
    if roles:
        data["roles"] = [{"roleName": r.role_name, "value": r.role_code} for r in roles]
    return data


def get_user_roles(db: Session, user_id: str) -> List[SysRole]:
    cached = _user_roles_cache.get(user_id)
    if cached is not None:
        return cached

    roles = (
        db.query(SysRole)
        .join(SysUserRole, SysUserRole.role_id == SysRole.id)
        .filter(SysUserRole.user_id == user_id)
        .all()
    )
    _user_roles_cache.set(user_id, roles)
    return roles


def check_only_user(db: Session, *, username: Optional[str] = None, phone: Optional[str] = None) -> Tuple[bool, str]:
    if username:
        exists = db.query(SysUser).filter(SysUser.username == username, SysUser.del_flag == 0).first()
        if exists:
            return False, "用户账号已存在"
    if phone:
        exists = db.query(SysUser).filter(SysUser.phone == phone, SysUser.del_flag == 0).first()
        if exists:
            return False, "手机号已存在"
    return True, ""


def register_user(db: Session, body: Dict[str, Any]) -> Tuple[bool, str]:
    from datetime import datetime

    phone = (body.get("phone") or "").strip()
    smscode = (body.get("smscode") or "").strip()
    username = (body.get("username") or "").strip() or phone
    password = parse_client_password(body.get("password") or "")
    email = (body.get("email") or "").strip()
    realname = (body.get("realname") or "").strip() or username

    if not phone:
        return False, "手机号不能为空"
    if not smscode:
        return False, "手机验证码不能为空"
    if not validate_phone_captcha(phone, smscode):
        if get_phone_captcha(phone) is None:
            return False, "手机验证码已失效，请重新获取"
        return False, "手机验证码错误"
    if not password:
        password = new_id()[:8]

    ok, msg = check_only_user(db, username=username)
    if not ok:
        return False, "用户名已注册"
    ok, msg = check_only_user(db, phone=phone)
    if not ok:
        return False, "该手机号已注册"
    if email:
        exists = db.query(SysUser).filter(SysUser.email == email, SysUser.del_flag == 0).first()
        if exists:
            return False, "邮箱已被注册"

    salt = new_id()[:8]
    user = SysUser(
        id=new_id(),
        username=username,
        realname=realname,
        password=encrypt_password(password, username, salt),
        salt=salt,
        phone=phone,
        email=email or None,
        status=1,
        del_flag=0,
        create_by=username,
        create_time=datetime.now(),
    )
    db.add(user)
    db.flush()
    db.add(SysUserRole(id=new_id(), user_id=user.id, role_id=DEFAULT_REGISTER_ROLE_ID))
    db.commit()
    pop_phone_captcha(phone)
    return True, "注册成功"


def phone_verification(db: Session, phone: str, smscode: str) -> Tuple[bool, str, Dict[str, str]]:
    phone = (phone or "").strip()
    smscode = (smscode or "").strip()
    if not phone or not smscode:
        return False, "手机号或验证码不能为空", {}
    if not validate_phone_captcha(phone, smscode):
        return False, "手机验证码错误", {}

    user = db.query(SysUser).filter(SysUser.phone == phone, SysUser.del_flag == 0).first()
    if not user:
        return False, "用户信息不存在", {}
    return True, "", {"smscode": smscode, "username": user.username or ""}


def admin_change_password(
    db: Session,
    *,
    username: str,
    password: str,
    confirm_password: str = "",
) -> Tuple[bool, str]:
    from datetime import datetime

    username = (username or "").strip()
    plain = parse_client_password(password or "")
    confirm = parse_client_password(confirm_password or "") if confirm_password else plain
    if not username or not plain:
        return False, "用户名或密码不能为空"
    if plain != confirm:
        return False, "两次输入的密码不一致"

    user = db.query(SysUser).filter(SysUser.username == username, SysUser.del_flag == 0).first()
    if not user:
        return False, "用户不存在"

    salt = new_id()[:8]
    user.salt = salt
    user.password = encrypt_password(plain, username, salt)
    user.update_by = username
    user.update_time = datetime.now()
    db.commit()
    return True, "密码修改成功！"


def reset_passwords(db: Session, usernames: str, *, default_pwd: str = "123456") -> Tuple[bool, str]:
    from datetime import datetime

    names = [name.strip() for name in (usernames or "").split(",") if name.strip()]
    if not names:
        return False, "请选择要重置的用户"
    updated = 0
    for username in names:
        if username == "admin":
            continue
        user = db.query(SysUser).filter(SysUser.username == username, SysUser.del_flag == 0).first()
        if not user:
            continue
        salt = new_id()[:8]
        user.salt = salt
        user.password = encrypt_password(default_pwd, username, salt)
        user.update_by = "system"
        user.update_time = datetime.now()
        updated += 1
    if updated == 0:
        return False, "未找到可重置的用户"
    db.commit()
    return True, "重置密码成功！"


def password_change(
    db: Session,
    *,
    username: str,
    password: str,
    smscode: str,
    phone: str,
) -> Tuple[bool, str]:
    from datetime import datetime

    username = (username or "").strip()
    phone = (phone or "").strip()
    smscode = (smscode or "").strip()
    plain = parse_client_password(password or "")
    if not username or not plain or not smscode or not phone:
        return False, "重置密码失败！"
    if not validate_phone_captcha(phone, smscode):
        return False, "短信验证码不匹配！"

    user = (
        db.query(SysUser)
        .filter(SysUser.username == username, SysUser.phone == phone, SysUser.del_flag == 0)
        .first()
    )
    if not user:
        return False, "当前用户和绑定的手机号不匹配，无法修改密码！"

    salt = new_id()[:8]
    user.salt = salt
    user.password = encrypt_password(plain, username, salt)
    user.update_by = username
    user.update_time = datetime.now()
    db.commit()
    pop_phone_captcha(phone)
    return True, "密码重置完成！"
