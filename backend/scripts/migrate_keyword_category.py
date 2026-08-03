"""
为 biz_keyword 增加类目字段，并按词表重灌关键词（通用 / 类目专属）。

用法（backend 目录）:
  python -m scripts.migrate_keyword_category
"""
from __future__ import annotations

import sys
from pathlib import Path

import pymysql

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_deploy_sql import keyword_rows  # noqa: E402
from scripts.init_slim_db import load_env_defaults  # noqa: E402


def main() -> None:
    cfg = load_env_defaults()
    conn = pymysql.connect(
        host=cfg["host"],
        port=int(cfg.get("port") or 3306),
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
        charset="utf8mb4",
        autocommit=False,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SHOW COLUMNS FROM biz_keyword LIKE 'category_id'")
            if not cur.fetchone():
                cur.execute(
                    "ALTER TABLE `biz_keyword` "
                    "ADD COLUMN `category_id` varchar(32) DEFAULT NULL AFTER `aspect`, "
                    "ADD COLUMN `category_name` varchar(100) DEFAULT NULL AFTER `category_id`, "
                    "ADD KEY `idx_biz_kw_category` (`category_id`)"
                )
                print("ALTER TABLE biz_keyword: added category_id/category_name")
            else:
                print("columns already exist")

            rows = keyword_rows()
            cur.execute("DELETE FROM biz_keyword")
            sql = (
                "INSERT INTO `biz_keyword` "
                "(`id`,`word`,`aspect`,`category_id`,`category_name`,`polarity`,`alias`,"
                "`weight`,`status`,`sort_no`,`remark`,`del_flag`,`create_by`,`create_time`) "
                "VALUES (%s,%s,%s,%s,%s,%s,NULL,2,1,%s,NULL,0,'admin','2026-08-03 12:00:00')"
            )
            payload = [
                (kid, word, aspect, cid, cname, polarity, sort_no)
                for kid, word, aspect, polarity, sort_no, cid, cname in rows
            ]
            cur.executemany(sql, payload)
            print(f"reseeded keywords: {len(payload)} "
                  f"(general={sum(1 for r in rows if not r[5])}, "
                  f"category={sum(1 for r in rows if r[5])})")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
