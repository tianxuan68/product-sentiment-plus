# -*- coding: utf-8 -*-
"""
api_server.py —— 属性级情感预测 API 服务（FastAPI，供前端调用）

接口：
    GET  /api/health                   健康检查
    GET  /api/meta                     返回支持的 类别 / 属性 等元信息
    POST /api/predict                  单条预测：{"category": "图书音像", "text": "…"}
    POST /api/predict_file             批量预测：上传 CSV/TXT 文件，返回处理后的结果文件（默认下载）
                                       - 可用查询参数：category / category_col / text_col
                                       - ?format=json 时返回逐条预测结果的 JSON（不上传文件下载）

运行方式：
    python scripts/api_server.py                    # 使用 Config 中的 api_host / api_port
    python scripts/api_server.py --port 8011        # 覆盖端口
    uvicorn scripts.api_server:app --host 0.0.0.0 --port 8010

返回格式（与项目后端 JeecgBoot FastAPI 壳保持一致）：
    {"success": true, "message": "操作成功", "code": 200, "result": {...}}

注意：
    模型在第一次请求时惰性加载（首次调用会慢几秒），后续复用，避免重复加载。
"""

import os
import sys
import csv
import argparse

# 把本脚本所在目录加入 sys.path，保证直接运行时也能互相 import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import torch
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from config import Config, get_device
from predict import predict_aspects, predict_file

# 降低 transformers 日志噪音
from transformers import logging as tf_logging
tf_logging.set_verbosity_error()

# ---------------------------------------------------------------------------
# 1. 与后端一致的统一返回结构
# ---------------------------------------------------------------------------
def ok(data=None, message: str = "操作成功"):
    return {"success": True, "message": message, "code": 200, "result": data}


def error(message: str = "操作失败", code: int = 500):
    return {"success": False, "message": message, "code": code, "result": None}


# ---------------------------------------------------------------------------
# 2. FastAPI 应用
# ---------------------------------------------------------------------------
app = FastAPI(
    title="BERT 属性级情感预测 API",
    description="输入商品类别 + 评论，输出 8 个属性的情感（好/坏/未提及）",
    version="1.0.0",
)

# 全局模型缓存（惰性加载）
_model = None
_tokenizer = None
_device = None


def get_model():
    """首次调用时加载模型，之后复用（全局单例）。"""
    global _model, _tokenizer, _device
    if _model is None:
        _device = torch.device(get_device())
        ckpt = Config["best_model_path"]
        from predict import load_model
        _model, _tokenizer, _ = load_model(ckpt, _device)
        print(f"[API] 模型加载完成：{ckpt}（设备 {_device}）")
    return _model, _tokenizer, _device


# ------------------------- 请求体模型 -------------------------
class PredictRequest(BaseModel):
    category: str = "其他"   # 商品类别，如 "图书音像"
    text: str                # 评论文本


# ------------------------- 健康检查 -------------------------
@app.get(f"{Config['api_prefix']}/health")
def health():
    return ok({"status": "ok"})


# ------------------------- 元信息 -------------------------
@app.get(f"{Config['api_prefix']}/meta")
def meta():
    return ok({
        "aspects": Config["aspects"],
        "categories": Config["categories"],
        "labels": [f"{a}{p}" for a in Config["aspects"] for p in ("好", "坏")],
        "model": os.path.basename(Config["best_model_path"]),
    })


# ------------------------- 单条预测 -------------------------
@app.post(f"{Config['api_prefix']}/predict")
def predict(req: PredictRequest, detail: bool = False):
    """
    单条预测：输入 类别 + 评论，输出「属性标签列表」，如 ["物流快", "质量好"]。

    参数：
        req:    {"category": "图书音像", "text": "…"}
        detail: 传 true 时返回每个属性的详细概率（调试用）。
    """
    try:
        model, tokenizer, device = get_model()
        result = predict_aspects(req.category.strip(), req.text.strip(),
                                 model=model, tokenizer=tokenizer, device=device,
                                 return_detail=detail)
        return ok(result)
    except Exception as exc:
        return error(f"预测失败：{exc}")


# ------------------------- 批量预测（上传文件） -------------------------
@app.post(f"{Config['api_prefix']}/predict_file")
async def predict_file_api(
    file: UploadFile = File(...),
    category: str = Form("其他"),
    category_col: str = Form(None),
    text_col: str = Form(None),
    fmt: str = Form("file"),
):
    """
    批量预测：上传 CSV/TXT 文件。

    CSV 要求包含评论文本列（自动识别，或用 text_col 指定），可选类别列。
    TXT 要求每行一条评论，类别统一用参数 category。

    参数：
        file:         上传的文件（CSV / TXT）。
        category:     TXT 格式时使用的统一类别名。
        category_col: CSV 中类别列列名（不传自动识别）。
        text_col:     CSV 中评论列列名（不传自动识别）。
        fmt:          "file"（默认）返回处理后的结果文件供下载；
                      "json" 返回逐条预测结果的 JSON。

    返回：
        fmt=file: 处理后的结果 CSV 文件（附件下载）。
        fmt=json: {"rows": [...], "output_file": "..."}
    """
    # 保存上传文件到临时目录
    upload_dir = os.path.join(Config["result_dir"], "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    safe_name = file.filename.replace("\\", "/").split("/")[-1]
    tmp_path = os.path.join(upload_dir, f"upload_{safe_name}")

    try:
        content = await file.read()
        with open(tmp_path, "wb") as f:
            f.write(content)

        output_path = predict_file(
            tmp_path,
            model=_model, tokenizer=_tokenizer, device=_device,
            checkpoint_path=Config["best_model_path"],
            category=category, category_col=category_col, text_col=text_col,
        )

        if fmt == "json":
            with open(output_path, "r", encoding="utf-8-sig") as f:
                rows = list(csv.DictReader(f))
            return ok({"rows": rows, "output_file": output_path})

        # 默认：返回结果文件供下载
        return FileResponse(
            output_path,
            media_type="text/csv",
            filename=os.path.basename(output_path),
        )
    except Exception as exc:
        return error(f"批量预测失败：{exc}")
    finally:
        # 清理上传的临时文件
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


# ---------------------------------------------------------------------------
# 3. 启动入口
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser(description="属性级情感预测 API 服务")
    parser.add_argument("--host", type=str, default=Config["api_host"])
    parser.add_argument("--port", type=int, default=Config["api_port"])
    args = parser.parse_args()

    print(f"[API] 启动服务：http://{args.host}:{args.port}{Config['api_prefix']}")
    uvicorn.run(app, host=args.host, port=args.port)
