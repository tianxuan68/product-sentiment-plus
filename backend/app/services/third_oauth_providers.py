"""第三方 OAuth 提供商封装。"""
from __future__ import annotations

import secrets
import urllib.parse
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings

SUPPORTED_RENDER_SOURCES = {"wechat_open", "github", "dingtalk", "wechat_enterprise"}


@dataclass
class ThirdOAuthProfile:
    source: str
    uuid: str
    username: str
    avatar: str = ""
    raw: Optional[Dict[str, Any]] = None


def create_oauth_state() -> str:
    return secrets.token_urlsafe(24)


def callback_url(source: str) -> str:
    base = settings.third_login_base_url.rstrip("/")
    return f"{base}/sys/thirdLogin/{source}/callback"


def build_authorize_url(source: str, state: str) -> str:
    redirect_uri = urllib.parse.quote(callback_url(source), safe="")
    if source == "wechat_open":
        if not settings.wechat_open_client_id:
            raise ValueError("未配置 WECHAT_OPEN_CLIENT_ID")
        return (
            "https://open.weixin.qq.com/connect/qrconnect"
            f"?appid={settings.wechat_open_client_id}"
            f"&redirect_uri={redirect_uri}"
            "&response_type=code&scope=snsapi_login"
            f"&state={state}#wechat_redirect"
        )
    if source == "github":
        if not settings.github_client_id:
            raise ValueError("未配置 GITHUB_CLIENT_ID")
        return (
            "https://github.com/login/oauth/authorize"
            f"?client_id={settings.github_client_id}"
            f"&redirect_uri={redirect_uri}"
            "&scope=read:user user:email"
            f"&state={state}"
        )
    if source == "dingtalk":
        if not settings.dingtalk_client_id:
            raise ValueError("未配置 DINGTALK_CLIENT_ID")
        return (
            "https://login.dingtalk.com/oauth2/auth"
            f"?redirect_uri={redirect_uri}"
            "&response_type=code"
            f"&client_id={settings.dingtalk_client_id}"
            "&scope=openid&prompt=consent"
            f"&state={state}"
        )
    if source == "wechat_enterprise":
        if not settings.wechat_enterprise_corp_id:
            raise ValueError("未配置 WECHAT_ENTERPRISE_CORP_ID")
        return (
            "https://open.weixin.qq.com/connect/oauth2/authorize"
            f"?appid={settings.wechat_enterprise_corp_id}"
            f"&redirect_uri={redirect_uri}"
            "&response_type=code&scope=snsapi_base"
            f"&state={state}#wechat_redirect"
        )
    raise ValueError(f"不支持的第三方登录: {source}")


async def exchange_code(source: str, code: str, *, tenant_id: int = 0) -> ThirdOAuthProfile:
    if source == "wechat_open":
        return await _wechat_open_profile(code)
    if source == "github":
        return await _github_profile(code)
    if source == "dingtalk":
        return await _dingtalk_profile(code)
    if source == "wechat_enterprise":
        return await _wechat_enterprise_profile(code, tenant_id=tenant_id)
    raise ValueError(f"不支持的第三方登录: {source}")


async def _wechat_open_profile(code: str) -> ThirdOAuthProfile:
    async with httpx.AsyncClient(timeout=20) as client:
        token_resp = await client.get(
            "https://api.weixin.qq.com/sns/oauth2/access_token",
            params={
                "appid": settings.wechat_open_client_id,
                "secret": settings.wechat_open_client_secret,
                "code": code,
                "grant_type": "authorization_code",
            },
        )
        token_data = token_resp.json()
        if token_data.get("errcode"):
            raise ValueError(token_data.get("errmsg", "微信授权失败"))
        access_token = token_data["access_token"]
        openid = token_data["openid"]
        user_resp = await client.get(
            "https://api.weixin.qq.com/sns/userinfo",
            params={"access_token": access_token, "openid": openid, "lang": "zh_CN"},
        )
        user_data = user_resp.json()
        if user_data.get("errcode"):
            raise ValueError(user_data.get("errmsg", "获取微信用户信息失败"))
        nickname = user_data.get("nickname") or f"wx_{openid[-8:]}"
        return ThirdOAuthProfile(
            source="wechat_open",
            uuid=openid,
            username=nickname,
            avatar=user_data.get("headimgurl") or "",
            raw=user_data,
        )


async def _github_profile(code: str) -> ThirdOAuthProfile:
    async with httpx.AsyncClient(timeout=20) as client:
        token_resp = await client.post(
            "https://github.com/login/oauth/access_token",
            headers={"Accept": "application/json"},
            data={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
                "redirect_uri": callback_url("github"),
            },
        )
        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise ValueError(token_data.get("error_description", "GitHub 授权失败"))
        user_resp = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        )
        user_data = user_resp.json()
        login = user_data.get("login") or f"github_{user_data.get('id')}"
        return ThirdOAuthProfile(
            source="github",
            uuid=str(user_data.get("id")),
            username=login,
            avatar=user_data.get("avatar_url") or "",
            raw=user_data,
        )


async def _dingtalk_profile(code: str) -> ThirdOAuthProfile:
    async with httpx.AsyncClient(timeout=20) as client:
        token_resp = await client.post(
            "https://api.dingtalk.com/v1.0/oauth2/userAccessToken",
            json={
                "clientId": settings.dingtalk_client_id,
                "clientSecret": settings.dingtalk_client_secret,
                "code": code,
                "grantType": "authorization_code",
            },
        )
        token_data = token_resp.json()
        access_token = token_data.get("accessToken")
        if not access_token:
            raise ValueError(token_data.get("message", "钉钉授权失败"))
        user_resp = await client.post(
            "https://api.dingtalk.com/v1.0/contact/users/me",
            headers={"x-acs-dingtalk-access-token": access_token},
            json={},
        )
        user_data = user_resp.json()
        union_id = user_data.get("unionId") or user_data.get("openId") or code
        nick = user_data.get("nick") or user_data.get("name") or f"dd_{union_id[-8:]}"
        return ThirdOAuthProfile(
            source="dingtalk",
            uuid=str(union_id),
            username=nick,
            avatar=user_data.get("avatarUrl") or "",
            raw=user_data,
        )


async def _wechat_enterprise_profile(code: str, *, tenant_id: int = 0) -> ThirdOAuthProfile:
    corp_id = settings.wechat_enterprise_corp_id
    secret = settings.wechat_enterprise_secret
    if not corp_id or not secret:
        raise ValueError("未配置 WECHAT_ENTERPRISE_CORP_ID / WECHAT_ENTERPRISE_SECRET")
    async with httpx.AsyncClient(timeout=20) as client:
        token_resp = await client.get(
            "https://qyapi.weixin.qq.com/cgi-bin/gettoken",
            params={"corpid": corp_id, "corpsecret": secret},
        )
        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise ValueError(token_data.get("errmsg", "获取企业微信 token 失败"))
        user_resp = await client.get(
            "https://qyapi.weixin.qq.com/cgi-bin/user/getuserinfo",
            params={"access_token": access_token, "code": code},
        )
        user_data = user_resp.json()
        if user_data.get("errcode") not in (0, None):
            raise ValueError(user_data.get("errmsg", "企业微信授权失败"))
        userid = user_data.get("UserId") or user_data.get("userid") or user_data.get("OpenId")
        if not userid:
            raise ValueError("企业微信未返回用户标识")
        return ThirdOAuthProfile(
            source="wechat_enterprise",
            uuid=str(userid),
            username=str(userid),
            avatar="",
            raw=user_data,
        )


def build_oauth2_login_url(source: str, state: str, request_base: str, tenant_id: int = 0) -> str:
    redirect_base = request_base.rstrip("/")
    if source == "wechat_enterprise":
        redirect_uri = urllib.parse.quote(
            f"{redirect_base}/sys/thirdLogin/oauth2/wechat_enterprise/callback?tenantId={tenant_id}",
            safe="",
        )
        return (
            "https://open.weixin.qq.com/connect/oauth2/authorize"
            f"?appid={settings.wechat_enterprise_corp_id}"
            f"&redirect_uri={redirect_uri}"
            "&response_type=code&scope=snsapi_base"
            f"&state={urllib.parse.quote(state, safe='')}#wechat_redirect"
        )
    if source == "dingtalk":
        redirect_uri = urllib.parse.quote(
            f"{redirect_base}/sys/thirdLogin/oauth2/dingtalk/callback?tenantId={tenant_id}",
            safe="",
        )
        return (
            "https://login.dingtalk.com/oauth2/auth"
            f"?redirect_uri={redirect_uri}"
            "&response_type=code"
            f"&client_id={settings.dingtalk_client_id}"
            "&scope=openid&prompt=consent"
            f"&state={urllib.parse.quote(state, safe='')}"
        )
    raise ValueError(f"不支持的 oauth2 source: {source}")
