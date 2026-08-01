#!/usr/bin/env python3
"""重置/创建默认用户。用法: python scripts/reset_users.py"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.security import encrypt_password, verify_password
from app.db.session import SessionLocal
from app.models.entities import SysUser, SysUserDepart, SysUserRole
from app.utils.common import new_id

ADMIN_ROLE = "f6817f48af4fb3af11b9e8bf182f618b"
TEST_ROLE = "ee8626f80f7c2619917b6236f3a7f02b"
DEPART_ID = "4f1765520d6346f9bd9c79e2479e5b12"
ORG_CODE = "A01A03"
DEFAULT_PWD = "123456"

USERS = [
    {"username": "admin", "realname": "管理员", "role_id": ADMIN_ROLE, "salt": "RCGTeGiH"},
    {"username": "gouda", "realname": "gouda", "role_id": ADMIN_ROLE},
    {"username": "gouer", "realname": "gouer", "role_id": TEST_ROLE},
]


def _ensure_depart(db, user_id: str) -> None:
    if not db.query(SysUserDepart).filter(SysUserDepart.user_id == user_id).first():
        db.add(SysUserDepart(id=new_id(), user_id=user_id, dep_id=DEPART_ID))


def _set_role(db, user_id: str, role_id: str) -> None:
    db.query(SysUserRole).filter(SysUserRole.user_id == user_id).delete()
    db.add(SysUserRole(id=new_id(), user_id=user_id, role_id=role_id))


def upsert_user(db, spec: dict) -> SysUser:
    username = spec["username"]
    user = db.query(SysUser).filter(SysUser.username == username).first()
    salt = (user.salt if user and user.salt else None) or spec.get("salt") or new_id()[:8]
    password = encrypt_password(DEFAULT_PWD, username, salt)
    now = datetime.now()

    if user:
        user.realname = spec.get("realname") or username
        user.password = password
        user.salt = salt
        user.status = 1
        user.del_flag = 0
        user.org_code = ORG_CODE
        user.update_time = now
    else:
        user = SysUser(
            id=new_id(),
            username=username,
            realname=spec.get("realname") or username,
            password=password,
            salt=salt,
            status=1,
            del_flag=0,
            org_code=ORG_CODE,
            create_by="system",
            create_time=now,
        )
        db.add(user)
        db.flush()

    _set_role(db, user.id, spec["role_id"])
    _ensure_depart(db, user.id)
    assert verify_password(DEFAULT_PWD, username, salt, password), f"{username} 密码校验失败"
    return user


def main() -> int:
    db = SessionLocal()
    try:
        for spec in USERS:
            user = upsert_user(db, spec)
            print(f"OK  {user.username}/{DEFAULT_PWD}  role={spec['role_id'][-8:]}  hash={user.password}")
        db.commit()
        print("\n全部用户已重置，请重启后端: python run.py")
        return 0
    except Exception as exc:
        db.rollback()
        print("FAIL:", exc, file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
