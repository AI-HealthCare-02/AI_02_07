# app/main.py
# ──────────────────────────────────────────────
# FastAPI 애플리케이션 진입점
# 앱 생명주기(startup/shutdown)에서 DB, Redis 초기화/해제
# ──────────────────────────────────────────────
import logging
import traceback

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from tortoise.contrib.fastapi import register_tortoise

from app.apis.v1 import api_v1_router
from app.apis.admin_router import admin_router
from app.core.config import get_settings
from app.core.redis import close_redis, init_redis
from app.db.databases import MODELS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """FastAPI 앱 팩토리."""
    settings = get_settings()

    app = FastAPI(
        title="AH_02_07 HealthGuide API",
        description=(
            "AI 기반 헬스케어 상담 웹 서비스\n\n"
            "## 🧪 개발 환경 안내\n"
            "OAuth 설정 없이 빠르게 테스트하려면:\n"
            "1. `POST /api/v1/auth/dev/login` 으로 테스터 토큰 발급\n"
            "2. 상단 **Authorize** 버튼 → `Bearer {access_token}` 입력\n"
            "3. 인증 필요한 API 자유롭게 테스트!\n\n"
            f"테스터 이메일: `{settings.DEV_TESTER_EMAIL}`"
            if settings.APP_ENV != "production"
            else ""
        ),
        version="1.0.0",
        docs_url="/api/docs" if settings.APP_DEBUG else None,
        redoc_url="/api/redoc" if settings.APP_DEBUG else None,
        openapi_url="/api/openapi.json" if settings.APP_DEBUG else None,
    )

    # ── CORS ──
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://localhost:5173",
            settings.FRONTEND_URL,
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ──────────────────────────────────────────
    # ⭐ Tortoise ORM 등록
    # register_tortoise는 내부적으로 app의 startup/shutdown에
    # Tortoise.init() / Tortoise.close_connections()를 등록합니다.
    # 이렇게 하면 모든 request handler에서 DB 연결이 유효합니다.
    # ──────────────────────────────────────────
    register_tortoise(
        app,
        db_url=settings.database_url,
        modules={"models": MODELS},
        generate_schemas=False,  # Raw SQL DDL이 스키마를 관리합니다
        add_exception_handlers=True,
    )

    # ── API 라우터 등록 ──
    app.include_router(api_v1_router)
    app.include_router(admin_router)

    # ── 전역 예외 핸들러 (500) ──
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        # HTTPException은 FastAPI가 자체 처리하므로 제외
        from fastapi import HTTPException
        if isinstance(exc, HTTPException):
            raise exc

        stack = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        logger.error("[Unhandled] %s %s\n%s", request.method, request.url.path, stack)

        # user_id 추출 시도 (JWT 파싱 실패해도 무시)
        user_id: int | None = None
        try:
            from jose import jwt as _jwt
            auth = request.headers.get("Authorization", "")
            if auth.startswith("Bearer "):
                payload = _jwt.decode(
                    auth[7:],
                    get_settings().JWT_SECRET_KEY,
                    algorithms=[get_settings().JWT_ALGORITHM],
                )
                role = payload.get("role", "user")
                if role == "user":
                    user_id = int(payload.get("sub", 0)) or None
        except Exception:
            pass

        try:
            from app.services.error_log_service import log_error
            await log_error(
                error_type=type(exc).__name__,
                error_message=str(exc),
                user_id=user_id,
                request_url=str(request.url),
                exception=exc,
            )
        except Exception as log_err:
            logger.error("오류 로그 저장 실패: %s", log_err)

        return JSONResponse(
            status_code=500,
            content={"status": 500, "message": "서버 내부 오류가 발생했습니다.", "error": "INTERNAL_SERVER_ERROR"},
        )

    # ──────────────────────────────────────────
    # Startup 이벤트
    # register_tortoise가 Tortoise를 init한 후에 실행됩니다.
    # Redis 초기화 + 시드 데이터 생성
    # ──────────────────────────────────────────
    @app.on_event("startup")
    async def on_startup():
        logger.info(f"🚀 HealthGuide 서버 시작 (env={settings.APP_ENV})")
        logger.info("✅ PostgreSQL 연결 완료 (register_tortoise)")

        # Redis 초기화
        try:
            await init_redis()
            logger.info("✅ Redis 연결 완료")
        except Exception as e:
            logger.warning(f"⚠️ Redis 연결 실패 (서버는 계속 동작): {e}")

        # 시드 데이터 생성
        # await _seed_default_ai_settings()
        # logger.info("✅ AI 기본 설정 확인 완료")

        # DDL + 공통코드 시딩 (Raw SQL)
        db_initialized = False
        try:
            from app.services.db_init_service import initialize_database

            await initialize_database()
            db_initialized = True
        except Exception as e:
            logger.error("[Startup] DB 초기화 실패: %s", e)

        if db_initialized:
            await _seed_tester_account()

    # ──────────────────────────────────────────
    # Shutdown 이벤트
    # Tortoise 종료는 register_tortoise가 자동 처리합니다.
    # ──────────────────────────────────────────
    @app.on_event("shutdown")
    async def on_shutdown():
        logger.info("🛑 HealthGuide 서버 종료 중...")
        try:
            await close_redis()
            logger.info("✅ Redis 연결 해제")
        except Exception:
            pass

    # ── 헬스체크 ──
    @app.get("/health", tags=["시스템"])
    async def health_check():
        return {
            "status": "ok",
            "env": settings.APP_ENV,
            "dev_login_available": settings.APP_ENV != "production",
        }

    return app


# ============================================================
# 시드 함수
# ============================================================


async def _seed_tester_account() -> None:
    """개발용 테스터 계정 시드. 프로덕션에서는 동작하지 않음."""
    settings = get_settings()
    if settings.APP_ENV == "production":
        return

    from app.models.user import User

    existing = await User.get_or_none(email=settings.DEV_TESTER_EMAIL)
    if existing:
        logger.info(f"  ✅ 테스터 계정 이미 존재: user_id={existing.user_id}, email={existing.email}")
        return

    tester = await User.create(
        email=settings.DEV_TESTER_EMAIL,
        password=None,
        nickname=settings.DEV_TESTER_NICKNAME,
        name=settings.DEV_TESTER_NAME,
        provider_code="LOCAL",
        provider_id=None,
    )
    logger.info(f"  🧪 테스터 계정 생성 완료: user_id={tester.user_id}, email={tester.email}")


# async def _seed_default_ai_settings() -> None:
#     """AI 기본 설정 시드."""
#     from app.models.ai_settings import AISettings

#     existing = await AISettings.get_or_none(is_active=True)
#     if existing:
#         logger.info(f"  ✅ 활성 AI 설정 존재: {existing.config_name}")
#         return

#     settings_count = await AISettings.all().count()
#     if settings_count == 0:
#         await AISettings.create(
#             config_name="CHATBOT_v1",
#             api_model="gpt-4",
#             system_prompt=(
#                 "당신은 HealthGuide AI 건강 상담 도우미입니다. "
#                 "사용자의 건강 관련 질문에 친절하고 정확하게 답변하세요. "
#                 "전문 의료 행위를 대체하지 않으며, 심각한 증상은 의사 상담을 권유하세요."
#             ),
#             emergency_keywords="자살,자해,죽고싶,사라지고싶",
#             temperature=0.70,
#             max_tokens=1000,
#             min_threshold=0.50,
#             auto_retry_count=3,
#             is_active=True,
#         )
#         logger.info("  📝 AI 기본 설정 시드 완료: CHATBOT_v1")


# ── 앱 인스턴스 생성 ──
app = create_app()

# ============================================================
# FastAPI 엔드포인트 연동 방법
# ============================================================
# 아래 코드를 프로젝트의 main.py (또는 app/api/router.py)에 추가하세요.
# ============================================================

# app/main.py 예시 ─────────────────────────────────────────────
from contextlib import asynccontextmanager

from fastapi import FastAPI
from tortoise.contrib.fastapi import RegisterTortoise

from app.core.config import settings

# ✅ 완성된 가이드 라우터 import
from app.apis.v1.guide import router as guide_router

# 다른 라우터들도 같은 방식으로 추가
# from app.apis.v1.auth import router as auth_router
# from app.apis.v1.user import router as user_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 시 Tortoise ORM 초기화·해제"""
    async with RegisterTortoise(
        app,
        db_url=settings.database_url,
        modules={"models": ["app.models.guide", "app.models.user"]},
        generate_schemas=False,  # 운영: False, 로컬 최초 실행: True
        add_exception_handlers=True,
    ):
        yield


app = FastAPI(
    title="건강가이드 API",
    version="1.0.0",
    lifespan=lifespan,
)

# ── 라우터 등록 ───────────────────────────────────────────────
API_PREFIX = "/api/v1"

app.include_router(guide_router, prefix=API_PREFIX)
# app.include_router(auth_router,  prefix=API_PREFIX)
# app.include_router(user_router,  prefix=API_PREFIX)

# 최종 엔드포인트 목록:
# GET    /api/v1/guides
# POST   /api/v1/guides
# GET    /api/v1/guides/{guide_id}
# PATCH  /api/v1/guides/{guide_id}
# DELETE /api/v1/guides/{guide_id}
# GET    /api/v1/guides/{guide_id}/conditions
# PUT    /api/v1/guides/{guide_id}/conditions
# POST   /api/v1/guides/{guide_id}/ai-generate
# GET    /api/v1/guides/{guide_id}/ai-results
# GET    /api/v1/guides/{guide_id}/med-check
# POST   /api/v1/guides/{guide_id}/med-check
# DELETE /api/v1/guides/{guide_id}/med-check/{check_id}
# GET    /api/v1/guides/{guide_id}/reminder
# POST   /api/v1/guides/{guide_id}/reminder
# PATCH  /api/v1/guides/{guide_id}/reminder
# DELETE /api/v1/guides/{guide_id}/reminder
