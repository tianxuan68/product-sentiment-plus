"""本地文件上传与访问（兼容 JeecgBoot JImageUpload 路径约定）。"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.core.config import settings
from app.utils.common import new_id

_SAFE_BIZ = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
_SAFE_NAME = re.compile(r"^[a-zA-Z0-9._-]{1,200}$")
_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp"}


def upload_root() -> Path:
    root = Path(settings.upload_dir)
    if not root.is_absolute():
        root = settings.base_dir / root
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_biz(biz: str) -> str:
    text = (biz or "temp").strip()
    if not _SAFE_BIZ.match(text):
        raise HTTPException(status_code=400, detail="biz 参数无效")
    return text


def _build_filename(original: str) -> str:
    suffix = Path(original or "file.bin").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}:
        suffix = ".jpg"
    return f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{new_id()[:8]}{suffix}"


async def save_upload_file(file: UploadFile, *, biz: str = "temp") -> str:
    """保存上传文件，返回相对路径（如 qc_sampling/xxx.jpg）。"""
    biz_dir = _safe_biz(biz)
    content_type = (file.content_type or "").lower()
    if biz_dir in ("qc_sampling", "qc_task") and content_type and content_type not in _IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="请上传图片文件（jpg/png/gif/webp）")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="文件为空")
    max_bytes = settings.upload_max_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(status_code=400, detail=f"文件不能超过 {settings.upload_max_mb}MB")

    filename = _build_filename(file.filename or "upload.jpg")
    target_dir = upload_root() / biz_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / filename
    target.write_bytes(content)
    return f"{biz_dir}/{filename}"


def resolve_static_file(relative_path: str) -> Path:
    text = (relative_path or "").strip().replace("\\", "/").lstrip("/")
    if not text or ".." in text.split("/"):
        raise HTTPException(status_code=400, detail="非法文件路径")
    root = upload_root().resolve()
    full = (root / text).resolve()
    if not str(full).startswith(str(root)):
        raise HTTPException(status_code=403, detail="禁止访问")
    if not full.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")
    return full
