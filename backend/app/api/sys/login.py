from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.captcha import create_captcha, validate_captcha
from app.core.deps import get_current_user
from app.core.third_login_cache import pop_value
from app.db.session import get_db
from app.models.entities import SysUser
from app.schemas.response import Result
from app.schemas.sys.login import LoginModel
from app.services.dict_service import query_all_dict_items
from app.services.login_service import (
    apply_login_org_code,
    authenticate_account,
    authenticate_phone,
    build_login_response,
    build_user_departs_result,
)
from app.services.qrcode_login_service import create_login_qrcode, get_qrcode_login_token, scan_login_qrcode
from app.services.phone_captcha_service import pop_phone_captcha
from app.services.user_service import get_user_roles, user_to_dict

router = APIRouter(tags=["登录"])


@router.post("/login")
def login(body: LoginModel, db: Session = Depends(get_db)):
    if not validate_captcha(body.checkKey or "", body.captcha or ""):
        return Result.error("验证码错误", 500)

    try:
        user = authenticate_account(db, body.username, body.password)
    except ValueError as exc:
        return Result.error(str(exc), 500)

    apply_login_org_code(db, user, body.loginOrgCode)
    return Result.ok(build_login_response(db, user), "登录成功")


@router.post("/loginGetUserDeparts")
def login_get_user_departs(body: dict, db: Session = Depends(get_db)):
    login_type = (body.get("loginType") or "account").strip()
    try:
        if login_type == "phone":
            mobile = (body.get("mobile") or "").strip()
            captcha = (body.get("smscode") or body.get("captcha") or "").strip()
            if not mobile or not captcha:
                return Result.error("手机号或验证码不能为空")
            user = authenticate_phone(db, mobile, captcha)
        else:
            username = (body.get("username") or "").strip()
            password = body.get("password") or ""
            if not username or not password:
                return Result.error("用户名或密码不能为空")
            user = authenticate_account(db, username, password)
    except ValueError as exc:
        return Result.error(str(exc))

    return Result.ok(build_user_departs_result(db, user))


@router.post("/phoneLogin")
def phone_login(body: dict, db: Session = Depends(get_db)):
    mobile = (body.get("mobile") or body.get("phone") or "").strip()
    captcha = (body.get("captcha") or body.get("smscode") or "").strip()
    login_org_code = body.get("loginOrgCode")

    if not mobile:
        return Result.error("手机号不能为空")
    if not captcha:
        return Result.error("验证码不能为空")

    try:
        user = authenticate_phone(db, mobile, captcha)
    except ValueError as exc:
        return Result.error(str(exc), 500)

    apply_login_org_code(db, user, login_org_code)
    pop_phone_captcha(mobile)
    return Result.ok(build_login_response(db, user), "登录成功")


@router.get("/logout")
def logout():
    return Result.ok(None, "退出登录成功")


@router.get("/randomImage/{key}")
def random_image(key: str):
    code, image = create_captcha(key)
    return Result.ok(image)


@router.get("/getLoginQrcode")
def get_login_qrcode():
    return Result.ok(create_login_qrcode())


@router.get("/getQrcodeToken")
def get_qrcode_token(qrcodeId: str = Query(...)):
    return Result.ok(get_qrcode_login_token(qrcodeId))


@router.post("/scanLoginQrcode")
def scan_login_qrcode_api(qrcodeId: str = Query(...), token: str = Query(...)):
    try:
        scan_login_qrcode(qrcodeId, token)
    except ValueError as exc:
        return Result.error(str(exc))
    return Result.ok(None, "扫码成功")


@router.get("/user/getUserInfo")
def get_user_info(user: SysUser = Depends(get_current_user), db: Session = Depends(get_db)):
    roles = get_user_roles(db, user.id)
    return Result.ok(
        {
            "userInfo": user_to_dict(user, roles),
            "sysAllDictItems": query_all_dict_items(db),
        }
    )
