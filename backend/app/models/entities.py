from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Integer, SmallInteger, String, Text, Float
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SysUser(Base):
    __tablename__ = "sys_user"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    username: Mapped[Optional[str]] = mapped_column(String(100))
    realname: Mapped[Optional[str]] = mapped_column(String(100))
    password: Mapped[Optional[str]] = mapped_column(String(255))
    salt: Mapped[Optional[str]] = mapped_column(String(45))
    avatar: Mapped[Optional[str]] = mapped_column(String(255))
    birthday: Mapped[Optional[date]] = mapped_column(Date)
    sex: Mapped[Optional[int]] = mapped_column(SmallInteger)
    email: Mapped[Optional[str]] = mapped_column(String(45))
    phone: Mapped[Optional[str]] = mapped_column(String(45))
    org_code: Mapped[Optional[str]] = mapped_column(String(64))
    status: Mapped[Optional[int]] = mapped_column(SmallInteger)
    del_flag: Mapped[Optional[int]] = mapped_column(SmallInteger)
    work_no: Mapped[Optional[str]] = mapped_column(String(100))
    login_tenant_id: Mapped[Optional[int]] = mapped_column(Integer)
    create_by: Mapped[Optional[str]] = mapped_column(String(32))
    create_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    update_by: Mapped[Optional[str]] = mapped_column(String(32))
    update_time: Mapped[Optional[datetime]] = mapped_column(DateTime)


class SysRole(Base):
    __tablename__ = "sys_role"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    role_name: Mapped[Optional[str]] = mapped_column(String(200))
    role_code: Mapped[Optional[str]] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(String(255))
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer)
    create_by: Mapped[Optional[str]] = mapped_column(String(32))
    create_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    update_by: Mapped[Optional[str]] = mapped_column(String(32))
    update_time: Mapped[Optional[datetime]] = mapped_column(DateTime)


class SysUserRole(Base):
    __tablename__ = "sys_user_role"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(32))
    role_id: Mapped[Optional[str]] = mapped_column(String(32))


class SysPermission(Base):
    __tablename__ = "sys_permission"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    parent_id: Mapped[Optional[str]] = mapped_column(String(32))
    name: Mapped[Optional[str]] = mapped_column(String(255))
    url: Mapped[Optional[str]] = mapped_column(String(255))
    component: Mapped[Optional[str]] = mapped_column(String(255))
    is_route: Mapped[Optional[int]] = mapped_column(SmallInteger)
    component_name: Mapped[Optional[str]] = mapped_column(String(255))
    redirect: Mapped[Optional[str]] = mapped_column(String(255))
    menu_type: Mapped[Optional[int]] = mapped_column(Integer)
    perms: Mapped[Optional[str]] = mapped_column(String(255))
    perms_type: Mapped[Optional[str]] = mapped_column(String(10))
    sort_no: Mapped[Optional[float]] = mapped_column(Float)
    always_show: Mapped[Optional[int]] = mapped_column(SmallInteger)
    icon: Mapped[Optional[str]] = mapped_column(String(255))
    is_leaf: Mapped[Optional[int]] = mapped_column(SmallInteger)
    keep_alive: Mapped[Optional[int]] = mapped_column(SmallInteger)
    hidden: Mapped[Optional[int]] = mapped_column(Integer)
    hide_tab: Mapped[Optional[int]] = mapped_column(Integer)
    del_flag: Mapped[Optional[int]] = mapped_column(Integer)
    rule_flag: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[Optional[str]] = mapped_column(String(2))
    internal_or_external: Mapped[Optional[int]] = mapped_column(SmallInteger)


class SysRolePermission(Base):
    __tablename__ = "sys_role_permission"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    role_id: Mapped[Optional[str]] = mapped_column(String(32))
    permission_id: Mapped[Optional[str]] = mapped_column(String(32))


class SysDepart(Base):
    __tablename__ = "sys_depart"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    parent_id: Mapped[Optional[str]] = mapped_column(String(32))
    depart_name: Mapped[str] = mapped_column(String(100))
    depart_order: Mapped[Optional[int]] = mapped_column(Integer)
    org_category: Mapped[Optional[str]] = mapped_column(String(10))
    org_type: Mapped[Optional[str]] = mapped_column(String(10))
    org_code: Mapped[str] = mapped_column(String(64))
    status: Mapped[Optional[str]] = mapped_column(String(1))
    del_flag: Mapped[Optional[str]] = mapped_column(String(1))
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer)
    iz_leaf: Mapped[Optional[int]] = mapped_column(SmallInteger)
    create_by: Mapped[Optional[str]] = mapped_column(String(32))
    create_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    update_by: Mapped[Optional[str]] = mapped_column(String(32))
    update_time: Mapped[Optional[datetime]] = mapped_column(DateTime)


class SysUserDepart(Base):
    __tablename__ = "sys_user_depart"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[Optional[str]] = mapped_column(String(32))
    dep_id: Mapped[Optional[str]] = mapped_column(String(32))


class SysDict(Base):
    __tablename__ = "sys_dict"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    dict_name: Mapped[Optional[str]] = mapped_column(String(100))
    dict_code: Mapped[Optional[str]] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(String(255))
    del_flag: Mapped[Optional[int]] = mapped_column(Integer)
    type: Mapped[Optional[int]] = mapped_column(SmallInteger)
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer)
    create_by: Mapped[Optional[str]] = mapped_column(String(32))
    create_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    update_by: Mapped[Optional[str]] = mapped_column(String(32))
    update_time: Mapped[Optional[datetime]] = mapped_column(DateTime)


class SysDictItem(Base):
    __tablename__ = "sys_dict_item"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    dict_id: Mapped[Optional[str]] = mapped_column(String(32))
    item_text: Mapped[Optional[str]] = mapped_column(String(100))
    item_value: Mapped[Optional[str]] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(String(255))
    sort_order: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[Optional[int]] = mapped_column(Integer)
    create_by: Mapped[Optional[str]] = mapped_column(String(32))
    create_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
    update_by: Mapped[Optional[str]] = mapped_column(String(32))
    update_time: Mapped[Optional[datetime]] = mapped_column(DateTime)
