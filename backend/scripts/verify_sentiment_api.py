"""多次验证 Insight 页所需接口（不改前端）。"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:8005/jeecg-boot"
AI_BASE = "http://127.0.0.1:8001"
OUT = Path(__file__).resolve().parent / "_verify_sentiment_out.json"


def post(url: str, payload: dict, timeout: float = 120.0) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def assert_front_shape(data: dict, label: str) -> None:
    assert isinstance(data, dict), f"{label}: not dict"
    assert data.get("sentiment") in {"positive", "neutral", "negative"}, f"{label}: bad sentiment {data.get('sentiment')}"
    assert isinstance(data.get("score"), int), f"{label}: score not int"
    assert 0 <= int(data["score"]) <= 100, f"{label}: score out of range"
    assert isinstance(data.get("summary"), str) and data["summary"], f"{label}: empty summary"
    assert isinstance(data.get("keywords"), list), f"{label}: keywords not list"


def main() -> int:
    cases = [
        {
            "name": "positive",
            "payload": {
                "content": "质量很好，发货很快，很满意，会回购",
                "product": {
                    "name": "澄见智能水杯",
                    "category": "生活用品",
                    "rating": "4.5",
                    "note": "日常使用",
                },
            },
        },
        {
            "name": "negative",
            "payload": {
                "content": "质量太差了，包装破损，物流很慢，非常后悔，不推荐购买",
                "product": {
                    "name": "某品牌耳机",
                    "category": "电子产品",
                    "rating": "1.0",
                    "note": "",
                },
            },
        },
        {
            "name": "neutralish",
            "payload": {
                "content": "一般般吧，还行，没什么特别的感觉",
            },
        },
    ]

    report: dict = {"ai": [], "backend": [], "products": None}

    # 1) AI 直连
    for case in cases:
        data = post(f"{AI_BASE}/api/front/predict", case["payload"])
        assert_front_shape(data, f"ai/{case['name']}")
        report["ai"].append({"case": case["name"], **data})
        print(f"[AI] {case['name']}: sentiment={data['sentiment']} score={data['score']} keywords={data['keywords'][:5]}")

    # 2) 后端代理（前端走的路径）
    for case in cases:
        wrapped = post(f"{BASE}/sentiment/predict", case["payload"])
        assert wrapped.get("success") is True, f"backend/{case['name']}: success!=True {wrapped}"
        assert wrapped.get("code") == 200, f"backend/{case['name']}: code!=200"
        data = wrapped.get("result") or {}
        assert_front_shape(data, f"backend/{case['name']}")
        report["backend"].append({"case": case["name"], "message": wrapped.get("message"), **data})
        print(
            f"[BE] {case['name']}: sentiment={data['sentiment']} score={data['score']} "
            f"keywords={data['keywords'][:5]} msg={wrapped.get('message')}"
        )

    # 3) 商品草稿
    prod = post(
        f"{BASE}/sentiment/products",
        {"name": "澄见智能水杯", "category": "生活用品", "rating": "4.5", "note": "验证保存"},
    )
    assert prod.get("success") is True, f"products fail: {prod}"
    report["products"] = prod
    print(f"[BE] products: {prod}")

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK wrote {OUT}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except urllib.error.URLError as exc:
        print("URLError:", exc, file=sys.stderr)
        raise SystemExit(2)
    except AssertionError as exc:
        print("ASSERT:", exc, file=sys.stderr)
        raise SystemExit(1)
