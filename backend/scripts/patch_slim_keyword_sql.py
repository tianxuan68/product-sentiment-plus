"""原地更新 jeecgboot-slim.sql 中的 biz_keyword INSERT（不重写评价数据）。"""
from __future__ import annotations

import re
from pathlib import Path

from scripts.build_deploy_sql import keyword_rows, sql_str

SQL_PATH = Path(__file__).resolve().parents[1] / "sql" / "jeecgboot-slim.sql"


def main() -> None:
    text = SQL_PATH.read_text(encoding="utf-8")
    rows = keyword_rows()
    kw_values = [
        f"({sql_str(kid)},{sql_str(word)},{sql_str(aspect)},{sql_str(cid)},{sql_str(cname)},{sql_str(polarity)},NULL,2,1,{sort_no},NULL,0,'admin','2026-08-03 12:00:00')"
        for kid, word, aspect, polarity, sort_no, cid, cname in rows
    ]
    new_insert = (
        "INSERT INTO `biz_keyword` (`id`,`word`,`aspect`,`category_id`,`category_name`,`polarity`,`alias`,`weight`,`status`,`sort_no`,`remark`,`del_flag`,`create_by`,`create_time`) VALUES\n"
        + ",\n".join(kw_values)
        + ";\n"
    )
    pat = re.compile(r"INSERT INTO `biz_keyword`[\s\S]*?;\r?\n", re.M)
    m = pat.search(text)
    if not m:
        # 追加到 FOREIGN_KEY_CHECKS 之前
        marker = "SET FOREIGN_KEY_CHECKS = 1;"
        idx = text.rfind(marker)
        if idx < 0:
            raise SystemExit("neither INSERT nor FOOTER found")
        text = text[:idx] + new_insert + "\n" + text[idx:]
        print(f"appended INSERT keywords={len(rows)}")
    else:
        text = text[: m.start()] + new_insert + text[m.end() :]
        print(f"replaced INSERT keywords={len(rows)}")
    SQL_PATH.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
