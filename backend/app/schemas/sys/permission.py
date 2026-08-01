from typing import Optional

from pydantic import BaseModel


class PermissionBody(BaseModel):
    id: Optional[str] = None
    parentId: Optional[str] = None
    name: Optional[str] = None
    url: Optional[str] = None
    component: Optional[str] = None
    menuType: Optional[int] = None
    perms: Optional[str] = None
    sortNo: Optional[float] = None
    icon: Optional[str] = None
    status: Optional[str] = "1"
    isRoute: Optional[int] = 1
    hidden: Optional[int] = 0
    keepAlive: Optional[int] = 0
