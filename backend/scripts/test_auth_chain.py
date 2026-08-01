"""端到端验证：注册/改密/登录 密码链路。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from Crypto.Cipher import AES
import base64

from app.core.security import (
    AES_IV,
    AES_KEY,
    encrypt_password,
    parse_client_password,
    verify_password,
)


def aes_encrypt_frontend(plain: str) -> str:
    data = plain.encode("utf-8")
    pad_len = 16 - (len(data) % 16)
    data = data + bytes([pad_len] * pad_len)
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    return base64.b64encode(cipher.encrypt(data)).decode()


def simulate_register(username: str, password: str, salt: str) -> str:
    enc = aes_encrypt_frontend(password)
    plain = parse_client_password(enc)
    return encrypt_password(plain, username, salt)


def simulate_login(username: str, password: str, salt: str, stored: str) -> bool:
    enc = aes_encrypt_frontend(password)
    plain = parse_client_password(enc)
    return verify_password(plain, username, salt, stored)


def simulate_password_change(username: str, new_password: str, old_salt: str, new_salt: str) -> tuple[str, str]:
    enc = aes_encrypt_frontend(new_password)
    plain = parse_client_password(enc)
    stored = encrypt_password(plain, username, new_salt)
    return new_salt, stored


def main() -> None:
    username = "demo_user"
    salt = "abcd1234"
    pwd = "Test@123456"

    stored = simulate_register(username, pwd, salt)
    assert simulate_login(username, pwd, salt, stored), "register -> login failed"

    new_salt = "xyz98765"
    new_pwd = "NewPass@789"
    _, new_stored = simulate_password_change(username, new_pwd, salt, new_salt)
    assert not simulate_login(username, pwd, new_salt, new_stored), "old password should fail"
    assert simulate_login(username, new_pwd, new_salt, new_stored), "change -> login failed"

    print("Auth chain OK: register / change-password / login")

    try:
        from sqlalchemy import create_engine, text
        from app.core.config import settings

        engine = create_engine(settings.database_url, pool_pre_ping=True)
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    "SELECT username, password, salt, status FROM sys_user "
                    "WHERE del_flag=0 ORDER BY create_time DESC LIMIT 5"
                )
            ).mappings().all()
            print("\nRecent DB users:")
            for r in rows:
                ok = verify_password("123456", r["username"], r["salt"] or "", r["password"] or "")
                print(f"  {r['username']}: salt={r['salt']} default123456={ok}")
    except Exception as exc:
        print(f"\nDB skip: {exc}")


if __name__ == "__main__":
    main()
