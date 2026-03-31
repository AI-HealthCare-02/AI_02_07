# app/apis/v1/__init__.py
# ──────────────────────────────────────────────
# API v1 라우터 통합 등록
# ──────────────────────────────────────────────

from fastapi import APIRouter

# ── 공통 라우터 ──
from app.apis.v1.auth import router as auth_router
from app.apis.v1.user import router as user_router
from app.apis.v1.common_code import router as common_code_router

# v1 API 라우터
api_v1_router = APIRouter(prefix="/api/v1")

# ── 공통 ──
api_v1_router.include_router(auth_router, prefix="/auth", tags=["인증"])
api_v1_router.include_router(user_router, prefix="/users", tags=["사용자"])
api_v1_router.include_router(common_code_router, prefix="/codes", tags=["공통코드"])
