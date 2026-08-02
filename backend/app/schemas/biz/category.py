from typing import Optional

from pydantic import BaseModel, Field


class CategoryBody(BaseModel):
    id: Optional[str] = None
    parentId: Optional[str] = None
    name: Optional[str] = None
    code: Optional[str] = None
    sortNo: Optional[int] = 0
    icon: Optional[str] = None
    description: Optional[str] = None
    status: Optional[int] = 1
