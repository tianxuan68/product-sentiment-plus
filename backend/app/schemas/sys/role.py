from typing import Optional

from pydantic import BaseModel


class RoleBody(BaseModel):
    id: Optional[str] = None
    roleName: Optional[str] = None
    roleCode: Optional[str] = None
    description: Optional[str] = None
