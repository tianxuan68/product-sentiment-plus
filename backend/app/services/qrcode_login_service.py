"""扫码登录（与 JeecgBoot LoginController 行为一致）。"""
from __future__ import annotations

from typing import Any, Dict

from app.core.third_login_cache import get_value, set_value
from app.utils.common import new_id

LOGIN_QRCODE_PREFIX = "login_qrcode:"
LOGIN_QRCODE_TOKEN_PREFIX = "login_qrcode_token:"
QRCODE_TTL = 30
QRCODE_TOKEN_TTL = 60


def create_login_qrcode() -> Dict[str, str]:
    qrcode_id = f"login_{new_id()}"
    set_value(f"{LOGIN_QRCODE_PREFIX}{qrcode_id}", qrcode_id, ttl=QRCODE_TTL)
    return {"qrcodeId": qrcode_id}


def get_qrcode_login_token(qrcode_id: str) -> Dict[str, Any]:
    if not qrcode_id or not get_value(f"{LOGIN_QRCODE_PREFIX}{qrcode_id}"):
        return {"token": "-2"}
    token = get_value(f"{LOGIN_QRCODE_TOKEN_PREFIX}{qrcode_id}")
    if token:
        return {"success": True, "token": token}
    return {"token": "-1"}


def scan_login_qrcode(qrcode_id: str, token: str) -> None:
    if not qrcode_id or not token:
        raise ValueError("参数不完整")
    if not get_value(f"{LOGIN_QRCODE_PREFIX}{qrcode_id}"):
        raise ValueError("二维码已过期,请刷新后重试")
    set_value(f"{LOGIN_QRCODE_TOKEN_PREFIX}{qrcode_id}", token, ttl=QRCODE_TOKEN_TTL)
