from datetime import datetime
import re
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Query as SqlQuery, Session

from app.core.deps import get_current_user, get_mutable_user, invalidate_auth_cache
from app.schemas.response import PageResult, Result
from app.schemas.sys.user import UserBody
from app.core.security import encrypt_password, parse_client_password, verify_password
from app.db.session import get_db
from app.models.entities import SysRole, SysUser, SysUserRole
from app.services.user_service import (
    admin_change_password,
    check_only_user,
    get_user_roles,
    password_change,
    phone_verification,
    register_user,
    reset_passwords,
    user_to_dict,
)
from app.utils.common import model_to_dict, new_id, paginate_query

router = APIRouter(prefix="/user", tags=["用户管理"])

_USER_STATUS_TEXT = {"1": "正常", "2": "冻结"}


def _parse_like(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    text = value.strip()
    if text.startswith("*"):
        text = text[1:]
    if text.endswith("*"):
        text = text[:-1]
    return text or None


def _camel_to_snake(name: str) -> str:
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name).lower()


def _build_user_query(
    db: Session,
    *,
    username: Optional[str] = None,
    realname: Optional[str] = None,
    phone: Optional[str] = None,
    sex: Optional[int] = None,
    status: Optional[int] = None,
) -> SqlQuery:
    q = db.query(SysUser).filter(SysUser.del_flag == 0)
    if username:
        q = q.filter(SysUser.username.like(f"%{_parse_like(username) or username}%"))
    if realname:
        q = q.filter(SysUser.realname.like(f"%{_parse_like(realname) or realname}%"))
    if phone:
        q = q.filter(SysUser.phone.like(f"%{phone.strip()}%"))
    if sex is not None:
        q = q.filter(SysUser.sex == sex)
    if status is not None:
        q = q.filter(SysUser.status == status)
    return q


def _apply_user_order(q: SqlQuery, column: Optional[str], order: Optional[str]) -> SqlQuery:
    if not column:
        return q.order_by(SysUser.create_time.desc())
    col_name = _camel_to_snake(column)
    col = getattr(SysUser, col_name, None)
    if col is None:
        return q.order_by(SysUser.create_time.desc())
    if order and order.lower() == "asc":
        return q.order_by(col.asc())
    return q.order_by(col.desc())


def _user_page_result(
    db: Session,
    *,
    page_no: int,
    page_size: int,
    username: Optional[str] = None,
    realname: Optional[str] = None,
    phone: Optional[str] = None,
    sex: Optional[int] = None,
    status: Optional[int] = None,
    column: Optional[str] = None,
    order: Optional[str] = None,
) -> Dict[str, Any]:
    q = _build_user_query(
        db,
        username=username,
        realname=realname,
        phone=phone,
        sex=sex,
        status=status,
    )
    q = _apply_user_order(q, column, order)
    items, total = paginate_query(q, page_no, page_size)
    records = [model_to_dict(u) for u in items]
    return PageResult.build(records, total, page_no, page_size).model_dump()


def _user_record(u: SysUser) -> Dict[str, Any]:
    data = model_to_dict(u)
    data["status_dictText"] = _USER_STATUS_TEXT.get(str(u.status), str(u.status) if u.status is not None else "")
    return data


def _user_role_page_result(
    db: Session,
    *,
    role_id: str,
    page_no: int,
    page_size: int,
    username: Optional[str] = None,
    realname: Optional[str] = None,
) -> Dict[str, Any]:
    q = (
        db.query(SysUser)
        .join(SysUserRole, SysUserRole.user_id == SysUser.id)
        .filter(SysUserRole.role_id == role_id, SysUser.del_flag == 0)
    )
    if username:
        q = q.filter(SysUser.username.like(f"%{_parse_like(username) or username}%"))
    if realname:
        q = q.filter(SysUser.realname.like(f"%{_parse_like(realname) or realname}%"))
    items, total = paginate_query(q.order_by(SysUser.create_time.desc()), page_no, page_size)
    records = [_user_record(u) for u in items]
    return PageResult.build(records, total, page_no, page_size).model_dump()


@router.get("/checkOnlyUser")
def check_only_user_api(
    username: Optional[str] = None,
    phone: Optional[str] = None,
    db: Session = Depends(get_db),
):
    ok, message = check_only_user(db, username=username, phone=phone)
    if ok:
        return Result.ok(True)
    return Result.error(message)


@router.post("/register")
def user_register(body: dict, db: Session = Depends(get_db)):
    ok, message = register_user(db, body)
    if ok:
        return Result.ok(None, message)
    return Result.error(message)


@router.post("/phoneVerification")
def user_phone_verification(body: dict, db: Session = Depends(get_db)):
    phone = (body.get("phone") or "").strip()
    smscode = (body.get("smscode") or "").strip()
    ok, message, data = phone_verification(db, phone, smscode)
    if ok:
        return Result.ok(data)
    return Result.error(message)


def _user_password_change_impl(
    db: Session,
    *,
    username: str,
    password: str,
    smscode: str,
    phone: str,
):
    ok, message = password_change(
        db,
        username=username,
        password=password,
        smscode=smscode,
        phone=phone,
    )
    if ok:
        invalidate_auth_cache()
        return Result.ok(None, message)
    return Result.error(message)


@router.get("/passwordChange")
def user_password_change_get(
    username: str = Query(...),
    password: str = Query(...),
    smscode: str = Query(...),
    phone: str = Query(...),
    db: Session = Depends(get_db),
):
    return _user_password_change_impl(
        db, username=username, password=password, smscode=smscode, phone=phone
    )


@router.post("/passwordChange")
def user_password_change_post(body: dict, db: Session = Depends(get_db)):
    return _user_password_change_impl(
        db,
        username=(body.get("username") or "").strip(),
        password=body.get("password") or "",
        smscode=(body.get("smscode") or "").strip(),
        phone=(body.get("phone") or "").strip(),
    )


@router.get("/list")
def user_list(
    pageNo: int = Query(1),
    pageSize: int = Query(10),
    username: Optional[str] = None,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    return Result.ok(_user_page_result(db, page_no=pageNo, page_size=pageSize, username=username))


@router.get("/listAll")
def user_list_all(
    pageNo: int = Query(1),
    pageSize: int = Query(10),
    username: Optional[str] = None,
    realname: Optional[str] = None,
    phone: Optional[str] = None,
    sex: Optional[int] = None,
    status: Optional[int] = None,
    column: Optional[str] = None,
    order: Optional[str] = None,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    """查询全部用户（精简版不做租户隔离，与 /list 行为一致）。"""
    return Result.ok(
        _user_page_result(
            db,
            page_no=pageNo,
            page_size=pageSize,
            username=username,
            realname=realname,
            phone=phone,
            sex=sex,
            status=status,
            column=column,
            order=order,
        )
    )


def _assign_roles(db: Session, user_id: str, role_ids: str):
    db.query(SysUserRole).filter(SysUserRole.user_id == user_id).delete()
    for rid in role_ids.split(",") if role_ids else []:
        if rid.strip():
            db.add(SysUserRole(id=new_id(), user_id=user_id, role_id=rid.strip()))


@router.post("/add")
def add_user(body: UserBody, db: Session = Depends(get_db), current: SysUser = Depends(get_current_user)):
    salt = new_id()[:8]
    pwd = parse_client_password(body.password or "123456")
    hashed = encrypt_password(pwd, body.username or "", salt)
    u = SysUser(
        id=new_id(),
        username=body.username,
        realname=body.realname,
        password=hashed,
        salt=salt,
        phone=body.phone,
        email=body.email,
        sex=body.sex,
        status=body.status,
        del_flag=0,
        create_by=current.username,
        create_time=datetime.now(),
    )
    db.add(u)
    db.flush()
    if body.selectedroles:
        _assign_roles(db, u.id, body.selectedroles)
    db.commit()
    return Result.ok(None, "添加成功！")


@router.post("/edit")
def edit_user(body: UserBody, db: Session = Depends(get_db), current: SysUser = Depends(get_current_user)):
    u = db.query(SysUser).filter(SysUser.id == body.id).first()
    if not u:
        return Result.error("用户不存在")
    if body.realname:
        u.realname = body.realname
    if body.phone:
        u.phone = body.phone
    if body.email:
        u.email = body.email
    if body.sex is not None:
        u.sex = body.sex
    if body.status is not None:
        u.status = body.status
    if body.password:
        plain = parse_client_password(body.password)
        u.password = encrypt_password(plain, u.username or "", u.salt or "")
    u.update_by = current.username
    u.update_time = datetime.now()
    if body.selectedroles:
        _assign_roles(db, u.id, body.selectedroles)
    db.commit()
    return Result.ok(None, "修改成功！")


@router.delete("/delete")
def delete_user(id: str = Query(...), db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    u = db.query(SysUser).filter(SysUser.id == id).first()
    if u:
        u.del_flag = 1
        db.commit()
    return Result.ok(None, "删除成功!")


@router.delete("/deleteBatch")
def delete_batch(ids: str = Query(...), db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    for uid in ids.split(","):
        u = db.query(SysUser).filter(SysUser.id == uid).first()
        if u:
            u.del_flag = 1
    db.commit()
    return Result.ok(None, "删除成功!")


@router.get("/queryUserRole")
def query_user_role(userid: str = Query(...), db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    role_ids = [r.role_id for r in db.query(SysUserRole).filter(SysUserRole.user_id == userid).all()]
    return Result.ok(role_ids)


@router.get("/userRoleList")
def user_role_list(
    roleId: str = Query(...),
    pageNo: int = Query(1),
    pageSize: int = Query(10),
    username: Optional[str] = None,
    realname: Optional[str] = None,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    return Result.ok(
        _user_role_page_result(
            db,
            role_id=roleId,
            page_no=pageNo,
            page_size=pageSize,
            username=username,
            realname=realname,
        )
    )


@router.post("/addSysUserRole")
def add_sys_user_role(
    body: dict,
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    role_id = (body.get("roleId") or "").strip()
    user_ids = body.get("userIdList") or body.get("userIds") or []
    if isinstance(user_ids, str):
        user_ids = [uid.strip() for uid in user_ids.split(",") if uid.strip()]
    if not role_id:
        return Result.error("角色ID不能为空")
    if not user_ids:
        return Result.error("请选择用户")

    added = 0
    for uid in user_ids:
        exists = (
            db.query(SysUserRole)
            .filter(SysUserRole.role_id == role_id, SysUserRole.user_id == uid)
            .first()
        )
        if not exists:
            db.add(SysUserRole(id=new_id(), user_id=uid, role_id=role_id))
            added += 1
    db.commit()
    return Result.ok(None, f"关联成功{added}条！" if added else "用户已关联")


@router.delete("/deleteUserRole")
def delete_user_role(
    userId: str = Query(...),
    roleId: str = Query(...),
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    db.query(SysUserRole).filter(SysUserRole.user_id == userId, SysUserRole.role_id == roleId).delete()
    db.commit()
    return Result.ok(None, "取消关联成功！")


@router.delete("/deleteUserRoleBatch")
def delete_user_role_batch(
    userIds: str = Query(...),
    roleId: str = Query(...),
    db: Session = Depends(get_db),
    user: SysUser = Depends(get_current_user),
):
    for uid in userIds.split(","):
        uid = uid.strip()
        if uid:
            db.query(SysUserRole).filter(SysUserRole.user_id == uid, SysUserRole.role_id == roleId).delete()
    db.commit()
    return Result.ok(None, "批量取消关联成功！")


@router.put("/frozenBatch")
def frozen_batch(ids: str = Query(...), status: int = Query(...), db: Session = Depends(get_db), user: SysUser = Depends(get_current_user)):
    for uid in ids.split(","):
        u = db.query(SysUser).filter(SysUser.id == uid).first()
        if u:
            u.status = status
    db.commit()
    return Result.ok(None, "操作成功")


@router.get("/verifyIzDefaultPwd")
def verify_iz_default_pwd(user: SysUser = Depends(get_current_user)):
    """检测是否仍为默认密码（123456），是则提示前端修改。"""
    if verify_password("123456", user.username or "", user.salt or "", user.password or ""):
        return Result.ok(None, "yes_123456")
    return Result.ok(None, "no")


@router.put("/changePassword")
def admin_change_password_api(
    body: dict,
    db: Session = Depends(get_db),
    current: SysUser = Depends(get_current_user),
):
    username = (body.get("username") or "").strip()
    if username == "admin" and current.username != "admin":
        return Result.error("不能修改管理员密码")
    ok, message = admin_change_password(
        db,
        username=username,
        password=body.get("password") or "",
        confirm_password=body.get("confirmPassword") or body.get("confirmpassword") or "",
    )
    if ok:
        invalidate_auth_cache()
        return Result.ok(None, message)
    return Result.error(message)


@router.put("/resetPassword")
def reset_password_api(
    usernames: str = Query(...),
    db: Session = Depends(get_db),
    current: SysUser = Depends(get_current_user),
):
    ok, message = reset_passwords(db, usernames)
    if ok:
        invalidate_auth_cache()
        return Result.ok(None, message)
    return Result.error(message)


@router.put("/updatePassword")
def update_password(
    body: dict,
    db: Session = Depends(get_db),
    current: SysUser = Depends(get_current_user),
):
    username = (body.get("username") or "").strip()
    old_password = parse_client_password(body.get("oldpassword") or "")
    new_password = parse_client_password(body.get("password") or "")
    confirm_password = parse_client_password(body.get("confirmpassword") or "")

    if not username:
        return Result.error("用户名不能为空")
    if current.username != username:
        return Result.error("只能修改当前登录用户密码")
    if not old_password or not new_password:
        return Result.error("旧密码或新密码不能为空")
    if new_password != confirm_password:
        return Result.error("两次输入的新密码不一致")
    if old_password == new_password:
        return Result.error("新密码不能与旧密码相同")
    user = get_mutable_user(db, current)
    if not verify_password(old_password, username, user.salt or "", user.password or ""):
        return Result.error("旧密码不正确")

    user.password = encrypt_password(new_password, username, user.salt or "")
    user.update_by = user.username
    user.update_time = datetime.now()
    db.commit()
    invalidate_auth_cache()
    return Result.ok(None, "密码修改成功！")


@router.put("/updatePasswordNotBindPhone")
def update_password_not_bind_phone(
    body: dict,
    db: Session = Depends(get_db),
    current: SysUser = Depends(get_current_user),
):
    username = (body.get("username") or current.username or "").strip()
    old_password = parse_client_password(body.get("oldPassword") or body.get("oldpassword") or "")
    new_password = parse_client_password(body.get("password") or "")

    if not username:
        return Result.error("用户名不能为空")
    if current.username != username:
        return Result.error("只能修改当前登录用户密码")
    if not old_password or not new_password:
        return Result.error("旧密码或新密码不能为空")
    if old_password == new_password:
        return Result.error("新密码不能与旧密码相同")
    user = get_mutable_user(db, current)
    if not verify_password(old_password, username, user.salt or "", user.password or ""):
        return Result.error("旧密码不正确")

    user.password = encrypt_password(new_password, username, user.salt or "")
    user.update_by = user.username
    user.update_time = datetime.now()
    db.commit()
    invalidate_auth_cache()
    return Result.ok(None, "密码修改成功！")
