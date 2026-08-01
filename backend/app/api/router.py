from fastapi import APIRouter

from app.api.sys.announcement import router as announcement_router
from app.api.sys.common import router as common_router
from app.api.sys.dashboard import router as dashboard_router
from app.api.sys.depart import router as depart_router
from app.api.sys.dict import dict_item_router, router as dict_router
from app.api.sys.log import router as log_router
from app.api.sys.login import router as login_router
from app.api.sys.permission import router as permission_router
from app.api.sys.role import router as role_router
from app.api.sys.role_index import router as role_index_router
from app.api.sys.sms import router as sms_router
from app.api.sys.third_login import router as third_login_router
from app.api.sys.third_user import router as third_user_router
from app.api.sys.user import router as user_router

sys_router = APIRouter()
sys_router.include_router(login_router)
sys_router.include_router(dashboard_router)
sys_router.include_router(announcement_router)
sys_router.include_router(user_router)
sys_router.include_router(role_router)
sys_router.include_router(role_index_router)
sys_router.include_router(permission_router)
sys_router.include_router(depart_router)
sys_router.include_router(dict_router)
sys_router.include_router(dict_item_router)
sys_router.include_router(common_router)
sys_router.include_router(third_login_router)
sys_router.include_router(third_user_router)
sys_router.include_router(sms_router)
sys_router.include_router(log_router)
