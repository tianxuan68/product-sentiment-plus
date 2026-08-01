from typing import Optional

from pydantic import BaseModel


class DictBody(BaseModel):
    id: Optional[str] = None
    dictName: Optional[str] = None
    dictCode: Optional[str] = None
    description: Optional[str] = None


class DictItemBody(BaseModel):
    id: Optional[str] = None
    dictId: Optional[str] = None
    itemText: Optional[str] = None
    itemValue: Optional[str] = None
    description: Optional[str] = None
    sortOrder: Optional[int] = 0
    status: Optional[int] = 1
