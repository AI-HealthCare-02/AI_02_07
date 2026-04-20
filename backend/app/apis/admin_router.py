# app/apis/admin_router.py
# /api/admin 경로 전용 라우터 (명세서 경로 준수)

from fastapi import APIRouter

from app.apis.v1.admin.auth import router as admin_auth_router
from app.apis.v1.admin.chat_stats import router as admin_chat_stats_router
from app.apis.v1.admin.dashboard import router as admin_dashboard_router
from app.apis.v1.admin.errors import router as admin_errors_router
from app.apis.v1.admin.system import router as admin_system_router
from app.apis.v1.admin.users import router as admin_users_router

admin_router = APIRouter(prefix="/api/admin")

admin_router.include_router(admin_auth_router, prefix="/auth", tags=["관리자 인증"])
admin_router.include_router(admin_dashboard_router, prefix="/dashboard", tags=["관리자 대시보드"])
admin_router.include_router(admin_users_router, prefix="/users", tags=["관리자 사용자"])
admin_router.include_router(admin_system_router, prefix="/system", tags=["관리자 시스템"])
admin_router.include_router(admin_errors_router, prefix="/errors", tags=["관리자 오류로그"])
admin_router.include_router(admin_chat_stats_router, prefix="/chat", tags=["관리자 채팅통계"])
