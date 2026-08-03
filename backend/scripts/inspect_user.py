"""Inspect user password hash in DB.

请在 backend 目录下运行:
    python -m scripts.inspect_user
"""

# 导包
import sys

from sqlalchemy import create_engine, text

from app.core.config import settings
from app.core.security import encrypt_password, parse_client_password, verify_password, _legacy_encrypt_password


def main() -> None:
    username = sys.argv[1] if len(sys.argv) > 1 else "gousan"
    engine = create_engine(settings.database_url, pool_pre_ping=True)
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT username, password, salt, phone, status, del_flag, create_time "
                "FROM sys_user WHERE username=:u"
            ),
            {"u": username},
        ).mappings().first()
    if not row:
        print(f"User {username!r} not found")
        return
    print(dict(row))
    u, salt, stored = row["username"], row["salt"] or "", row["password"] or ""
    std = encrypt_password("PLACEHOLDER", u, salt)
    print(f"std hash format sample (wrong pwd): {std[:16]}...")
    print(f"stored hash: {stored}")
    print(f"legacy match 123456: {_legacy_encrypt_password('123456', u, salt) == stored}")
    print(f"verify 123456: {verify_password('123456', u, salt, stored)}")


if __name__ == "__main__":
    main()
