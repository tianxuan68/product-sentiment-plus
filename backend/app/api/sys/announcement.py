"""系统通知（精简版）。"""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.schemas.response import Result

router = APIRouter(prefix="/annountCement", tags=["系统通知"])


@router.get("/getUnreadMessageCount")
def get_unread_message_count():
    """未读消息数（精简版固定为 0，不查库，避免 DB 不可达时请求超时）。"""
    return Result.ok({"count": 0})


@router.get("/listByUser")
def list_by_user(pageSize: int = Query(5, alias="pageSize")):
    return Result.ok(
        {
            "anntMsgList": [],
            "sysMsgList": [],
            "anntMsgTotal": 0,
            "sysMsgTotal": 0,
        }
    )


@router.get("/vue3List")
def vue3_list(
    pageNo: int = Query(1, alias="pageNo"),
    pageSize: int = Query(10, alias="pageSize"),
):
    return Result.ok([])


@router.post("/clearAllUnReadMessage")
def clear_all_unread_message():
    return Result.ok(None, "操作成功")
