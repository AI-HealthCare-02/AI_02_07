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

from app.apis.admin_router import admin_router
from app.apis.v1 import api_v1_router
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
            content={
                "status": 500,
                "message": "서버 내부 오류가 발생했습니다.",
                "error": "INTERNAL_SERVER_ERROR",
            },
        )

    # ──────────────────────────────────────────
    # Startup 이벤트
    # register_tortoise가 Tortoise를 init한 후에 실행됩니다.
    # Redis 초기화 + 시드 데이터 생성 + 스케줄러 시작
    # ──────────────────────────────────────────
    @app.on_event("startup")
    async def on_startup():
        logger.info(f"🚀 HealthGuide 서버 시작 (env={settings.APP_ENV})")
        logger.info("✅ PostgreSQL 연결 완료 (register_tortoise)")

        # Langfuse 초기화 (환경변수 세팅 + 싱글턴 생성)
        try:
            from app.core.langfuse_client import init_langfuse

            init_langfuse()
        except Exception as e:
            logger.warning(f"⚠️ Langfuse 초기화 실패: {e}")

        # Redis 초기화
        try:
            await init_redis()
            logger.info("✅ Redis 연결 완료")
        except Exception as e:
            logger.warning(f"⚠️ Redis 연결 실패 (서버는 계속 동작): {e}")

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

        # ✅ 추가: 복약 알림 스케줄러 시작
        # DB 초기화 완료 후 시작해야 med_reminder 조회가 가능
        try:
            from app.services.alarm_scheduler import start_scheduler

            start_scheduler()
        except Exception as e:
            logger.warning(f"⚠️ 복약 알림 스케줄러 시작 실패 (서버는 계속 동작): {e}")

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

        # ✅ 추가: 복약 알림 스케줄러 종료
        try:
            from app.services.alarm_scheduler import stop_scheduler

            stop_scheduler()
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


# ── 앱 인스턴스 생성 ──
app = create_app()
