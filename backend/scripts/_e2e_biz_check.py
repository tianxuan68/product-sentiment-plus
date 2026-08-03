"""联调：检查库表/菜单，登录后逐个打 biz 接口。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pymysql
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BASE = "http://127.0.0.1:8005/jeecg-boot"
DB = dict(host="127.0.0.1", user="root", password="Zpg1314521@", database="jeecg-boot", charset="utf8mb4")


def apply_sql(path: Path) -> None:
    conn = pymysql.connect(**DB, autocommit=False)
    content = path.read_text(encoding="utf-8")
    statements, buf = [], []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        buf.append(line)
        if stripped.endswith(";"):
            statements.append("\n".join(buf))
            buf = []
    with conn.cursor() as cur:
        for stmt in statements:
            cur.execute(stmt)
    conn.commit()
    conn.close()
    print("applied", path.name)


def db_snapshot() -> None:
    conn = pymysql.connect(**DB)
    cur = conn.cursor()
    for t in ["biz_category", "biz_product", "biz_sentiment_query", "biz_keyword"]:
        try:
            cur.execute(f"SELECT COUNT(*) FROM `{t}`")
            print(f"table {t}: {cur.fetchone()[0]}")
        except Exception as exc:
            print(f"table {t}: MISSING ({exc})")
    cur.execute(
        "SELECT id, name, url FROM sys_permission WHERE id LIKE 'biz_%' ORDER BY parent_id, sort_no, id"
    )
    for row in cur.fetchall():
        print("menu", row)
    conn.close()


def login() -> str:
    import base64

    from Crypto.Cipher import AES

    from app.core.security import AES_IV, AES_KEY

    data = b"123456"
    pad_len = 16 - (len(data) % 16)
    data = data + bytes([pad_len] * pad_len)
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    password = base64.b64encode(cipher.encrypt(data)).decode()

    resp = requests.post(
        f"{BASE}/sys/login",
        json={"username": "admin", "password": password, "captcha": "", "checkKey": "1"},
        timeout=30,
    )
    data = resp.json()
    if not data.get("success"):
        raise RuntimeError(f"login failed: {data}")
    token = data["result"]["token"]
    print("login ok, token len", len(token))
    return token


def call(method: str, path: str, token: str, **kwargs):
    headers = {"X-Access-Token": token, "Authorization": token}
    url = f"{BASE}{path}"
    resp = requests.request(method, url, headers=headers, timeout=60, **kwargs)
    try:
        body = resp.json()
    except Exception:
        body = {"raw": resp.text[:300]}
    ok = resp.status_code == 200 and (body.get("success") is True or body.get("code") == 200)
    print(f"[{'OK' if ok else 'FAIL'}] {method} {path} status={resp.status_code} msg={body.get('message')}")
    if not ok:
        print("  body:", json.dumps(body, ensure_ascii=False)[:500])
    return ok, body


def main() -> int:
    # 确保关键词补丁 + 演示数据
    for name in ["patch_biz_keyword.sql", "patch_biz_seed_demo.sql", "patch_biz_menus.sql"]:
        p = ROOT / "sql" / name
        if p.exists():
            try:
                apply_sql(p)
            except Exception as exc:
                print("apply warn", name, exc)

    print("--- DB snapshot ---")
    db_snapshot()

    print("--- API e2e ---")
    token = login()
    results = []

    # category
    ok, body = call("GET", "/biz/category/list", token)
    results.append(ok)
    ok, body = call("GET", "/biz/category/tree", token)
    results.append(ok)

    # product
    ok, body = call("GET", "/biz/product/list", token, params={"pageNo": 1, "pageSize": 5})
    results.append(ok)
    total_prod = (body.get("result") or {}).get("total", 0)

    # review
    ok, body = call("GET", "/biz/review/list", token, params={"pageNo": 1, "pageSize": 5})
    results.append(ok)
    total_rev = (body.get("result") or {}).get("total", 0)

    # keyword list/add/edit/delete
    ok, body = call("GET", "/biz/keyword/list", token, params={"pageNo": 1, "pageSize": 5})
    results.append(ok)
    word = "联调词_e2e"
    ok, body = call(
        "POST",
        "/biz/keyword/add",
        token,
        json={
            "word": word,
            "aspect": "质量",
            "categoryId": "",
            "categoryName": "",
            "polarity": "any",
            "weight": 1,
            "status": 1,
            "sortNo": 99,
        },
    )
    results.append(ok)
    kid = (body.get("result") or {}).get("id")
    if kid:
        ok, body = call(
            "POST",
            "/biz/keyword/edit",
            token,
            json={
                "id": kid,
                "word": word,
                "aspect": "体验",
                "categoryId": "cat003",
                "categoryName": "手机/数码",
                "polarity": "positive",
                "weight": 2,
                "status": 1,
                "sortNo": 99,
            },
        )
        results.append(ok)
        ok, body = call("DELETE", "/biz/keyword/delete", token, params={"id": kid})
        results.append(ok)
    else:
        results.append(False)
        results.append(False)

    # product add/edit/delete smoke
    ok, body = call(
        "POST",
        "/biz/product/add",
        token,
        json={"name": "联调商品_e2e", "categoryId": "cat00301", "brand": "E2E", "sku": "E2E-SKU-1", "price": 9.9, "stock": 1, "status": 1},
    )
    results.append(ok)
    pid = (body.get("result") or {}).get("id")
    if pid:
        ok, body = call(
            "POST",
            "/biz/product/edit",
            token,
            json={"id": pid, "name": "联调商品_e2e_edit", "categoryId": "cat00301", "brand": "E2E", "sku": "E2E-SKU-1", "price": 19.9, "stock": 2, "status": 1},
        )
        results.append(ok)
        ok, body = call("DELETE", "/biz/product/delete", token, params={"id": pid})
        results.append(ok)
    else:
        results.extend([False, False])

    # category add/edit/delete under other root
    ok, body = call(
        "POST",
        "/biz/category/add",
        token,
        json={"parentId": "cat007", "name": "联调类目_e2e", "code": "e2e_cat", "sortNo": 99, "status": 1},
    )
    results.append(ok)
    cid = (body.get("result") or {}).get("id")
    if cid:
        ok, body = call(
            "POST",
            "/biz/category/edit",
            token,
            json={"id": cid, "parentId": "cat007", "name": "联调类目_e2e_edit", "code": "e2e_cat", "sortNo": 99, "status": 1},
        )
        results.append(ok)
        ok, body = call("DELETE", "/biz/category/delete", token, params={"id": cid})
        results.append(ok)
    else:
        results.extend([False, False])

    # dashboard + causal
    ok, body = call("GET", "/biz/dashboard/overview", token, params={"limit": 10})
    results.append(ok)
    if ok:
        result = body.get("result") or {}
        print(
            "  overview keys",
            sorted(result.keys()),
            "total",
            (result.get("summary") or {}).get("total"),
        )
    ok, body = call("POST", "/biz/causal/analyze", token, json={})
    results.append(ok)
    if ok:
        print("  causal sampleSize", (body.get("result") or {}).get("sampleSize"), "ate", (body.get("result") or {}).get("ate"))

    print("--- summary ---")
    print(f"passed {sum(1 for x in results if x)}/{len(results)} productRows~{total_prod} reviewRows~{total_rev}")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
