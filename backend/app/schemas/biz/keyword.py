from typing import Optional

from pydantic import BaseModel


class KeywordBody(BaseModel):
    id: Optional[str] = None
    word: Optional[str] = None
    aspect: Optional[str] = None
    categoryId: Optional[str] = None
    categoryName: Optional[str] = None
    polarity: Optional[str] = "any"
    alias: Optional[str] = None
    weight: Optional[int] = 1
    status: Optional[int] = 1
    sortNo: Optional[int] = 0
    remark: Optional[str] = None
