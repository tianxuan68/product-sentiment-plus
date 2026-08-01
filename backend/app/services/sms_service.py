"""短信验证码发送（Spug Push）。"""
from __future__ import annotations

import logging
import random
import re
from typing import Any, Dict

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_MOBILE_RE = re.compile(r"^1[3-9]\d{9}$")


def generate_sms_code(length: int = 6) -> str:
    return "".join(str(random.randint(0, 9)) for _ in range(length))


def validate_mobile(mobile: str) -> bool:
    return bool(mobile and _MOBILE_RE.match(mobile.strip()))


def is_spug_configured() -> bool:
    return bool((settings.spug_sms_api_url or "").strip())


def _parse_spug_response(resp: httpx.Response) -> Dict[str, Any]:
    try:
        data = resp.json()
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {"code": resp.status_code, "msg": resp.text[:200]}


def _ensure_spug_success(data: Dict[str, Any]) -> None:
    code = data.get("code")
    if code in (None, 200, 0, "200", "0"):
        return
    msg = data.get("msg") or data.get("message") or str(data)
    raise ValueError(f"短信发送失败: {msg}")


def _normalize_spug_api_url(api_url: str) -> str:
    """去掉控制台复制的占位 query（?to=&code=...），只保留基础 URL。"""
    return api_url.split("?", 1)[0].rstrip("/")


def _format_spug_validity_number(validity_minutes: int) -> str:
    """Spug number 变量：验证码有效分钟数，须为 2 位数字（如 05 表示 5 分钟）。"""
    minutes = max(1, min(99, validity_minutes))
    return f"{minutes:02d}"


def send_spug_sms(mobile: str, code: str, *, validity_minutes: int = 5) -> None:
    api_url = _normalize_spug_api_url((settings.spug_sms_api_url or "").strip())
    if not api_url:
        raise ValueError("未配置 SPUG_SMS_API_URL")

    name = settings.spug_sms_name or "推送助手"
    phone = mobile.strip()
    logger.info("Spug SMS -> %s to=%s****%s", api_url, phone[:3], phone[-4:])

    try:
        with httpx.Client(timeout=15, trust_env=False) as client:
            if "/sms/" in api_url:
                # Spug 短信模板：code=验证码，number=有效分钟数（2 位数字，如 05=5分钟）
                params = {
                    "to": phone,
                    "code": code,
                    "number": _format_spug_validity_number(validity_minutes),
                }
                resp = client.get(api_url, params=params)
            else:
                # 通用模板：POST form，字段 name / code / targets
                payload = {
                    "name": name,
                    "code": code,
                    "targets": phone,
                }
                resp = client.post(api_url, data=payload)

            data = _parse_spug_response(resp)
            if resp.status_code >= 400:
                _ensure_spug_success(data)
            _ensure_spug_success(data)
            logger.info("Spug SMS response: %s", data)
    except ValueError:
        raise
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:200] if exc.response is not None else str(exc)
        raise ValueError(f"短信发送失败: {detail}") from exc
    except httpx.RequestError as exc:
        raise ValueError(f"短信服务不可用: {exc}") from exc
