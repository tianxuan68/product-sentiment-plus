from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException
import logging

from sqlalchemy.exc import OperationalError

from app.api.router import sys_router
from app.api.websocket import router as websocket_router
from app.core.config import settings
from app.schemas.response import Result
from app.services.sms_service import is_spug_configured

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Sentiment-Plus",
    description="Jeecg FastAPI 精简壳：仅系统配置（用户/角色/菜单/部门/字典）",
    version="0.1.0",
)

_cors_origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=r"https?://[\w.-]+(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sys_router, prefix=f"{settings.context_path}/sys")
app.include_router(websocket_router, prefix=settings.context_path)


@app.on_event("startup")
def log_startup_config():
    from app.db.startup import mark_db_ready, start_background_db_connect
    from app.db.session import warmup_db_pool

    if settings.db_warmup_enabled:
        try:
            elapsed = warmup_db_pool()
            mark_db_ready()
            logger.info("数据库连接池已预热，首次连通耗时 %.2fs", elapsed)
            if elapsed > 1.0:
                logger.warning(
                    "数据库响应较慢（>1s）。开发环境建议使用本地 MySQL，见 .env.example 中 DATABASE_URL 注释"
                )
        except Exception as exc:
            logger.warning("启动预热数据库失败，将转入后台重试: %s", exc)
            start_background_db_connect()
    else:
        logger.info("已跳过启动时数据库预热（DB_WARMUP_ENABLED=false），后台自动连接…")
        start_background_db_connect()

    if is_spug_configured():
        logger.info("短信: Spug 已配置，将真实发送")
    else:
        logger.warning("短信: 未配置 SPUG_SMS_API_URL，使用开发模式（验证码仅在接口 message 中返回）")


@app.exception_handler(OperationalError)
async def db_operational_error_handler(request: Request, exc: OperationalError):
    logger.error("数据库操作失败 %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=200,
        content=Result.error(
            "数据库连接异常，请稍后重试。若持续失败，请检查远程 MySQL 或改用本地库。",
            500,
        ).model_dump(),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    code = 401 if exc.status_code == 401 else 500
    return JSONResponse(
        status_code=200,
        content=Result.error(exc.detail, code).model_dump(),
    )


@app.get(f"{settings.context_path}/health")
def health():
    from app.db.session import is_db_healthy

    db_ok, db_latency_ms = is_db_healthy()

    return Result.ok({
        "status": "ok" if db_ok else "degraded",
        "backend": "fastapi",
        "db": "ok" if db_ok else "error",
        "dbLatencyMs": db_latency_ms,
        "smsMode": "spug" if is_spug_configured() else "dev",
    })


@app.get("/")
def root():
    return Result.ok({"message": "JeecgBoot FastAPI", "api": f"{settings.context_path}/sys"})
