"""用唯一部署 SQL（sql/jeecgboot-slim.sql）初始化数据库并验证登录链路。

请在 backend 目录下运行:
    python -m scripts.init_slim_db
    python -m scripts.init_slim_db --host 127.0.0.1 --user root --password xxx

重新从评论数据集生成 SQL:
    python -m scripts.build_deploy_sql
"""

# 导包
import argparse

import pymysql
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.core.security import encrypt_password, verify_password, verify_token, create_token
from app.services.dict_service import query_all_dict_items
from app.services.permission_service import build_menu_tree, query_permissions_by_user
from app.services.user_service import get_user_roles


def load_env_defaults() -> dict:
    from app.core.config import settings

    url = settings.database_url
    # mysql+pymysql://user:pass@host:port/db
    body = url.split("://", 1)[1]
    auth, hostpart = body.rsplit("@", 1)
    user, password = auth.split(":", 1)
    host_port, database = hostpart.split("/", 1)
    if "?" in database:
        database = database.split("?", 1)[0]
    host, port = host_port.split(":")
    return {
        "host": host,
        "port": int(port),
        "user": user,
        "password": password.replace("%40", "@"),
        "database": database,
    }


def run_sql_file(conn, sql_path):
    """流式按分号切语句执行，支持大体积全量数据集 SQL。"""
    with conn.cursor() as cur:
        try:
            cur.execute("SET GLOBAL max_allowed_packet=536870912")
        except Exception:
            # 无 SUPER 权限时忽略；分批 INSERT 一般不需要改包大小
            pass
        cur.execute("SET NAMES utf8mb4")
        cur.execute("SET FOREIGN_KEY_CHECKS=0")

        buf: list[str] = []
        executed = 0
        with open(sql_path, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped or stripped.startswith("--"):
                    continue
                buf.append(line.rstrip("\n"))
                if stripped.endswith(";"):
                    stmt = "\n".join(buf)
                    buf = []
                    cur.execute(stmt)
                    executed += 1
                    if executed % 50 == 0:
                        conn.commit()
                        print(f"  executed statements: {executed}")
        if buf:
            cur.execute("\n".join(buf))
            executed += 1
        cur.execute("SET FOREIGN_KEY_CHECKS=1")
    conn.commit()
    print(f"  total statements: {executed}")


def verify_backend(db_url: str) -> None:
    engine = create_engine(db_url, pool_pre_ping=True)
    with Session(engine) as db:
        user = db.execute(
            text("SELECT id, username, password, salt, status, del_flag FROM sys_user WHERE username='admin'")
        ).mappings().first()
        assert user, "admin 用户不存在"
        assert user["status"] == 1 and user["del_flag"] == 0, "admin 用户状态异常"
        assert verify_password("123456", user["username"], user["salt"], user["password"]), "admin 密码校验失败"

        roles = get_user_roles(db, user["id"])
        assert roles, "admin 未分配角色"

        perms = query_permissions_by_user(db, user["id"])
        assert len(perms) >= 5, f"admin 菜单权限不足: {len(perms)}"
        menu = build_menu_tree(perms)
        assert menu, "菜单树为空"

        dict_items = query_all_dict_items(db)
        assert dict_items, "字典数据为空"

        token = create_token(user["username"], user["password"])
        assert verify_token(token, user["username"], user["password"]), "Token 校验失败"

    tables = [
        "sys_user",
        "sys_role",
        "sys_user_role",
        "sys_permission",
        "sys_role_permission",
        "sys_depart",
        "sys_user_depart",
        "sys_dict",
        "sys_dict_item",
    ]
    with engine.connect() as conn:
        for table in tables:
            count = conn.execute(text(f"SELECT COUNT(*) FROM `{table}`")).scalar()
            assert count and count > 0, f"{table} 无数据"
            print(f"  OK {table}: {count} rows")


def main() -> None:
    parser = argparse.ArgumentParser(description="Init JeecgBoot slim database")
    defaults = load_env_defaults()
    parser.add_argument("--host", default=defaults["host"])
    parser.add_argument("--port", type=int, default=defaults["port"])
    parser.add_argument("--user", default=defaults["user"])
    parser.add_argument("--password", default=defaults["password"])
    parser.add_argument("--database", default=defaults["database"])
    args = parser.parse_args()

    print(f"Connecting {args.user}@{args.host}:{args.port}/{args.database}")
    conn = pymysql.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        charset="utf8mb4",
        autocommit=False,
        connect_timeout=15,
    )
    try:
        sql_file = "./sql/jeecgboot-slim.sql"
        print(f"Applying {sql_file} ...")
        run_sql_file(conn, sql_file)
        print("SQL applied.")
    finally:
        conn.close()

    db_url = (
        f"mysql+pymysql://{args.user}:{args.password.replace('@', '%40')}"
        f"@{args.host}:{args.port}/{args.database}?charset=utf8mb4"
    )
    print("Verifying backend logic ...")
    verify_backend(db_url)
    print("All checks passed. Login with admin / 123456")


if __name__ == "__main__":
    main()
