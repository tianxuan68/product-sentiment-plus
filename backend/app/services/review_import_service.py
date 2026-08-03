"""评价导入：模板下载 + CSV 校验解析入库。"""
from __future__ import annotations

import csv
import io
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.services import review_service

# 模板表头（顺序固定，导入时必须完全一致）
TEMPLATE_HEADERS = [
    "商品名称",
    "类目",
    "评价内容",
    "情绪",
    "置信分",
    "关键词",
    "用户",
    "评价时间",
]

TEMPLATE_SAMPLES = [
    ["Demo Phone X1", "手机", "物流很快，客服态度好，推荐购买。", "正向", "88", "物流,客服", "user01", "2026-10-01 10:00:00"],
    ["DemoBook Pro 14", "笔记本", "散热一般，配送延迟两天，体验一般。", "负向", "68", "散热,配送", "user02", "2026-10-02 09:00:00"],
    ["Python入门", "图书", "内容扎实，包装完好。", "正向", "92", "内容,包装", "user03", "2026-10-03 11:20:00"],
]

_SENTIMENT_MAP = {
    "正向": "positive",
    "好评": "positive",
    "正面": "positive",
    "positive": "positive",
    "pos": "positive",
    "中性": "neutral",
    "neutral": "neutral",
    "负向": "negative",
    "差评": "negative",
    "负面": "negative",
    "negative": "negative",
    "neg": "negative",
}

_ALLOWED_EXT = {".csv", ".txt"}


def build_template_csv() -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(TEMPLATE_HEADERS)
    writer.writerows(TEMPLATE_SAMPLES)
    # Excel 友好：UTF-8 BOM
    return ("\ufeff" + buf.getvalue()).encode("utf-8")


def _normalize_header(cell: Any) -> str:
    return str(cell or "").replace("\ufeff", "").strip()


def _parse_dt(raw: str) -> Optional[datetime]:
    text = str(raw or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:19], fmt)
        except ValueError:
            continue
    return None


def _clean_content(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


async def import_reviews_file(
    db: Session,
    file: UploadFile,
    *,
    user_id: Optional[str] = None,
    username: Optional[str] = None,
) -> Dict[str, Any]:
    filename = (file.filename or "").strip()
    if not filename:
        raise ValueError("未选择文件，请先下载模板并填写后上传")

    lower = filename.lower()
    ext = "." + lower.rsplit(".", 1)[-1] if "." in lower else ""
    if ext not in _ALLOWED_EXT:
        raise ValueError(f"文件格式不正确，仅支持 {', '.join(sorted(_ALLOWED_EXT))}（请下载模板后按 CSV 上传）")

    raw = await file.read()
    if not raw:
        raise ValueError("文件内容为空")

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = raw.decode("gbk")
        except UnicodeDecodeError as exc:
            raise ValueError("文件编码无法识别，请使用模板另存为 UTF-8 CSV") from exc

    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        raise ValueError("文件无内容，请使用模板填写后再上传")

    headers = [_normalize_header(h) for h in rows[0]]
    if headers != TEMPLATE_HEADERS:
        raise ValueError(
            "表头与模板不一致。请下载最新模板，勿增删/改名列。"
            f"期望：{' | '.join(TEMPLATE_HEADERS)}；实际：{' | '.join(headers) if headers else '(空)'}"
        )

    data_rows = rows[1:]
    if not data_rows:
        raise ValueError("模板中没有数据行，请至少填写一条评价")

    success = 0
    errors: List[str] = []
    for idx, cols in enumerate(data_rows, start=2):
        # 跳过全空行
        if not any(str(c or "").strip() for c in cols):
            continue
        # 补齐列
        while len(cols) < len(TEMPLATE_HEADERS):
            cols.append("")
        mapped = {TEMPLATE_HEADERS[i]: str(cols[i] if i < len(cols) else "").strip() for i in range(len(TEMPLATE_HEADERS))}
        content = _clean_content(mapped["评价内容"])
        if not content:
            errors.append(f"第{idx}行：评价内容不能为空")
            continue
        if len(content) < 2:
            errors.append(f"第{idx}行：评价内容过短")
            continue

        sentiment_raw = mapped["情绪"].strip().lower() if mapped["情绪"] else ""
        # 中文键也要匹配
        sentiment = _SENTIMENT_MAP.get(mapped["情绪"].strip()) or _SENTIMENT_MAP.get(sentiment_raw)
        if mapped["情绪"] and not sentiment:
            errors.append(f"第{idx}行：情绪取值无效（可用 正向/中性/负向）")
            continue

        score_raw = mapped["置信分"].strip()
        score = None
        if score_raw:
            try:
                score = int(float(score_raw))
                if score < 0 or score > 100:
                    raise ValueError("out of range")
            except ValueError:
                errors.append(f"第{idx}行：置信分须为 0-100 整数")
                continue

        create_time = _parse_dt(mapped["评价时间"])
        payload = {
            "productName": mapped["商品名称"] or None,
            "categoryName": mapped["类目"] or None,
            "content": content,
            "sentiment": sentiment,
            "score": score,
            "keywords": mapped["关键词"] or None,
            "username": mapped["用户"] or username,
        }
        try:
            row = review_service.create_review(db, payload, user_id=user_id, username=username)
            if create_time:
                row.create_time = create_time
                db.commit()
            success += 1
        except ValueError as exc:
            errors.append(f"第{idx}行：{exc}")
        except Exception as exc:
            errors.append(f"第{idx}行：保存失败 {exc}")

    if success == 0:
        detail = "；".join(errors[:5]) if errors else "没有可导入的数据"
        raise ValueError(f"导入失败：{detail}")

    return {
        "successCount": success,
        "failCount": len(errors),
        "errors": errors[:20],
        "templateHeaders": TEMPLATE_HEADERS,
    }
