from typing import List, Optional, Union

from pydantic import BaseModel, Field


class ReviewBody(BaseModel):
    id: Optional[str] = None
    content: Optional[str] = None
    productId: Optional[str] = None
    productName: Optional[str] = None
    categoryId: Optional[str] = None
    categoryName: Optional[str] = None
    coverUrl: Optional[str] = None
    sentiment: Optional[str] = None
    score: Optional[int] = Field(default=None, ge=0, le=100)
    summary: Optional[str] = None
    # 支持 JSON 数组或逗号/顿号分隔字符串
    keywords: Optional[Union[List[str], str]] = None
    username: Optional[str] = None
