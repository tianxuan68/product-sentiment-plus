"""首页统计（精简版占位数据）。"""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter

from app.schemas.response import Result

router = APIRouter(tags=["首页统计"])


@router.get("/loginfo")
def loginfo():
    return Result.ok(
        {
            "todayIp": 0,
            "todayVisitCount": 0,
            "totalVisitCount": 0,
        }
    )


@router.get("/visitInfo")
def visit_info():
    today = datetime.now()
    result = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        result.append(
            {
                "type": day.strftime("%m-%d"),
                "ip": 0,
                "visit": 0,
            }
        )
    return Result.ok(result)
