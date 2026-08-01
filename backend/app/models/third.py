from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SysThirdAccount(Base):
    __tablename__ = "sys_third_account"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    sys_user_id: Mapped[Optional[str]] = mapped_column(String(32))
    avatar: Mapped[Optional[str]] = mapped_column(String(255))
    status: Mapped[Optional[int]] = mapped_column(Integer, default=1)
    del_flag: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    realname: Mapped[Optional[str]] = mapped_column(String(100))
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    third_user_uuid: Mapped[Optional[str]] = mapped_column(String(100))
    third_user_id: Mapped[Optional[str]] = mapped_column(String(100))
    third_type: Mapped[Optional[str]] = mapped_column(String(50))
    create_by: Mapped[Optional[str]] = mapped_column(String(32))
    create_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    update_by: Mapped[Optional[str]] = mapped_column(String(32))
    update_time: Mapped[Optional[datetime]] = mapped_column(DateTime)


class SysThirdAppConfig(Base):
    __tablename__ = "sys_third_app_config"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    agent_id: Mapped[Optional[str]] = mapped_column(String(20))
    client_id: Mapped[Optional[str]] = mapped_column(String(50))
    client_secret: Mapped[Optional[str]] = mapped_column(String(100))
    corp_id: Mapped[Optional[str]] = mapped_column(String(100))
    third_type: Mapped[Optional[str]] = mapped_column(String(50))
    status: Mapped[Optional[int]] = mapped_column(Integer, default=1)
    create_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    update_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
