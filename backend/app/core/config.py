# app/core/config.py
# ──────────────────────────────────────────────
# 전체 앱 설정 관리
# pydantic-settings를 사용하여 환경 변수를 타입 안전하게 로드
#
# OAuth 설정:
#   - 구글: OAUTH_GOOGLE_CLIENT_ID, OAUTH_GOOGLE_CLIENT_SECRET, OAUTH_GOOGLE_REDIRECT_URI
#   - 카카오: OAUTH_KAKAO_CLIENT_ID, OAUTH_KAKAO_CLIENT_SECRET, OAUTH_KAKAO_REDIRECT_URI
# ──────────────────────────────────────────────

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    애플리케이션 전역 설정.
    .env 파일 또는 환경 변수에서 값을 자동 로드합니다.
    """

    # ── 앱 기본 ──
    APP_ENV: str = "local"  # local | production
    APP_DEBUG: bool = True
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # ── 프론트엔드 URL (OAuth 완료 후 리다이렉트 대상) ──
    FRONTEND_URL: str = "http://localhost:3000"

    # ── PostgreSQL ──
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "healthguide"
    DB_PASSWORD: str = "healthguide_local_pw"
    DB_NAME: str = "healthguide_db"

    @property
    def database_url(self) -> str:
        """Tortoise ORM용 PostgreSQL 접속 URL"""
        return f"asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # ── Redis ──
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0

    @property
    def redis_url(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # ── JWT 인증 ──
    JWT_SECRET_KEY: str = "change-me"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ──────────────────────────────────────────
    # OAuth 2.0 설정
    # ──────────────────────────────────────────

    # ── 카카오 ──
    # https://developers.kakao.com 에서 앱 생성 후 발급
    OAUTH_KAKAO_CLIENT_ID: str = ""
    OAUTH_KAKAO_CLIENT_SECRET: str = ""
    OAUTH_KAKAO_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/kakao/callback"

    # ── 구글 ──
    # https://console.cloud.google.com 에서 OAuth 2.0 클라이언트 생성 후 발급
    OAUTH_GOOGLE_CLIENT_ID: str = ""
    OAUTH_GOOGLE_CLIENT_SECRET: str = ""
    OAUTH_GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"

    # ──────────────────────────────────────────
    # 개발용 테스터 계정 설정
    # APP_ENV가 "production"이 아닐 때만 동작합니다.
    # 팀원들이 OAuth 없이 바로 API 테스트를 할 수 있습니다.
    # ──────────────────────────────────────────
    DEV_TESTER_EMAIL: str = "tester@healthguide.dev"
    DEV_TESTER_NICKNAME: str = "테스터"
    DEV_TESTER_NAME: str = "개발테스터"

    # ── AWS S3 ──
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "ap-northeast-2"
    AWS_S3_BUCKET_NAME: str = "ah-02-07-healthguide"

    # ── OpenAI ──
    OPENAI_API_KEY: str = ""

    # ── vLLM ──
    VLLM_HOST: str = "localhost"
    VLLM_PORT: int = 8001

    # ── Worker Queue ──
    WORKER_QUEUE_NAME: str = "ai_task_queue"
    WORKER_RESULT_PREFIX: str = "ai_result:"
    WORKER_PROCESSING_PREFIX: str = "ai_processing:"
    WORKER_MAX_RETRIES: int = 3
    WORKER_TASK_TIMEOUT: int = 300

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[2] / "envs" / ".local.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Settings 싱글턴 반환."""
    return Settings()
