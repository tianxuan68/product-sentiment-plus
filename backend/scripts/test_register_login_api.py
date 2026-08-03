"""Live API test: register then login.

请在 backend 目录下运行:
    python -m scripts.test_register_login_api
"""

# 导包
import base64
import time

import requests
from Crypto.Cipher import AES
from sqlalchemy import create_engine, text

from app.core.security import AES_IV, AES_KEY, encrypt_password, verify_password
from app.core.config import settings


def aes_encrypt(plain: str) -> str:
    data = plain.encode("utf-8")
    pad_len = 16 - (len(data) % 16)
    data = data + bytes([pad_len] * pad_len)
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    return base64.b64encode(cipher.encrypt(data)).decode()


def main() -> None:
    base = "http://127.0.0.1:8000/jeecg-boot"
    username = f"autotest_{int(time.time()) % 100000}"
    phone = "13900001234"
    password = "Test@123456"

    sms = requests.post(f"{base}/sys/sms", json={"mobile": phone, "smsmode": "1"}, timeout=15).json()
    print("SMS:", sms)
    code = (sms.get("result") or {}).get("devCode") or ""
    if not code and "开发模式验证码" in (sms.get("message") or ""):
        code = (sms.get("message") or "").split(":")[-1].strip().rstrip("）")
    if not code:
        print("No dev SMS code")
        return

    reg = requests.post(
        f"{base}/sys/user/register",
        json={
            "username": username,
            "phone": phone,
            "smscode": code,
            "password": aes_encrypt(password),
        },
        timeout=15,
    ).json()
    print("Register:", reg)
    if not reg.get("success"):
        return

    engine = create_engine(settings.database_url, pool_pre_ping=True)
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT username, password, salt FROM sys_user WHERE username=:u"),
            {"u": username},
        ).mappings().first()
    print("DB row:", dict(row) if row else None)
    if row:
        ok = verify_password(password, row["username"], row["salt"], row["password"])
        print("Direct verify_password:", ok)
        expected = encrypt_password(password, row["username"], row["salt"])
        print("Hash match expected:", expected == row["password"])

    login = requests.post(
        f"{base}/sys/login",
        json={"username": username, "password": aes_encrypt(password), "captcha": "", "checkKey": "test"},
        timeout=15,
    ).json()
    print("Login:", login)


if __name__ == "__main__":
    main()
