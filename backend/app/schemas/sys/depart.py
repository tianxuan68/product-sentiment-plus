from typing import Optional

from pydantic import BaseModel


class DepartBody(BaseModel):
    id: Optional[str] = None
    parentId: Optional[str] = None
    departName: Optional[str] = None
    orgCategory: Optional[str] = "2"
    orgCode: Optional[str] = None
    departOrder: Optional[int] = 0
    status: Optional[str] = "1"
