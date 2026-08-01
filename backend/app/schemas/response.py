from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Result(BaseModel, Generic[T]):
    success: bool = True
    message: str = ""
    code: int = 200
    result: Optional[T] = None
    timestamp: Optional[int] = None

    @staticmethod
    def ok(data: Any = None, message: str = "操作成功") -> "Result":
        return Result(success=True, code=200, message=message, result=data)

    @staticmethod
    def error(message: str = "操作失败", code: int = 500) -> "Result":
        return Result(success=False, code=code, message=message, result=None)


class PageResult(BaseModel):
    records: list[Any]
    total: int
    size: int
    current: int
    pages: int = 0

    @staticmethod
    def build(records: list, total: int, page_no: int, page_size: int) -> "PageResult":
        pages = (total + page_size - 1) // page_size if page_size else 0
        return PageResult(
            records=records,
            total=total,
            size=page_size,
            current=page_no,
            pages=pages,
        )
