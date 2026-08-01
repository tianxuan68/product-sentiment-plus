from typing import Optional

from pydantic import BaseModel


class UserBody(BaseModel):
    id: Optional[str] = None
    username: Optional[str] = None
    realname: Optional[str] = None
    password: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    sex: Optional[int] = None
    status: Optional[int] = 1
    selectedroles: Optional[str] = None
    selecteddeparts: Optional[str] = None
