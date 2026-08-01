"""短信验证码接口。"""
from __future__ import annotations

import logging

from fastapi import APIRouter

from app.schemas.response import Result
from app.services.sms_service import generate_sms_code, is_spug_configured, send_spug_sms, validate_mobile
from app.services.phone_captcha_service import captcha_validity_minutes, store_phone_captcha

logger = logging.getLogger(__name__)

router = APIRouter(tags=["短信"])


@router.post("/sendChangePwdSms")
def send_change_pwd_sms(body: dict):
    """用户设置页修改密码时发送短信验证码。"""
    return send_sms(body)


@router.post("/sms")
def send_sms(body: dict):
    mobile = (body.get("mobile") or body.get("phone") or "").strip()
    if not mobile:
        return Result.error("手机号不能为空")
    if not validate_mobile(mobile):
        return Result.error("手机号格式不正确")

    code = generate_sms_code()
    store_phone_captcha(mobile, code)

    if is_spug_configured():
        try:
            send_spug_sms(mobile, code, validity_minutes=captcha_validity_minutes())
        except ValueError as exc:
            return Result.error(str(exc))
        return Result.ok(None, "验证码已发送")

    # 未配置 Spug：开发模式，验证码写在 message 里（前端成功时不弹窗，需看 Network 响应）
    logger.warning("SPUG 未配置，开发模式验证码 mobile=%s code=%s", mobile, code)
    return Result.ok({"devCode": code}, f"验证码已发送（开发模式验证码: {code}）")
