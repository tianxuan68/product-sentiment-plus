from typing import Optional

from pydantic import BaseModel


class LoginModel(BaseModel):
    username: str
    password: str
    captcha: Optional[str] = None
    checkKey: Optional[str] = None
    loginOrgCode: Optional[str] = None
