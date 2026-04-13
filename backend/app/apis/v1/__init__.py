# app/apis/v1/__init__.py
# ──────────────────────────────────────────────
# API v1 라우터 통합 등록
# ──────────────────────────────────────────────

from fastapi import APIRouter

# ── 공통 라우터 ──
from app.apis.v1.auth import router as auth_router
from app.apis.v1.chat import router as chat_router
from app.apis.v1.common_code import router as common_code_router
from app.apis.v1.user import router as user_router
from app.core.config import get_settings
from app.apis.v1.medical_doc import router as medical_doc_router

# v1 API 라우터
api_v1_router = APIRouter(prefix="/api/v1")


# ── 공통 ──
api_v1_router.include_router(auth_router, prefix="/auth", tags=["인증"])
api_v1_router.include_router(user_router, prefix="/users", tags=["사용자"])
api_v1_router.include_router(common_code_router, prefix="/codes", tags=["공통코드"])

# ── 챗봇 ──
api_v1_router.include_router(chat_router, prefix="/chat", tags=["AI 챗봇"])


# ── 의료 문서 분석 ──
api_v1_router.include_router(
    medical_doc_router, prefix="/medical-doc", tags=["의료 문서 분석"]
)


# ── 건강 가이드 ──
from app.apis.v1.guide import router as guide_router
api_v1_router.include_router(guide_router, tags=["건강 가이드"])


# ── 개발 환경 전용 라우터 (S3 테스트) ──
settings = get_settings()
if settings.APP_ENV != "production":
    from app.apis.v1.s3_test import router as s3_test_router

    api_v1_router.include_router(s3_test_router)
