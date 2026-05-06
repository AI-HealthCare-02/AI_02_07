# app/core/config.py
# ──────────────────────────────────────────────
# 전체 앱 설정 관리
# pydantic-settings를 사용하여 환경 변수를 타입 안전하게 로드
# ──────────────────────────────────────────────

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── 앱 기본 ──
    APP_ENV: str = "local"
    APP_DEBUG: bool = True
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    SECRET_KEY: str = "change-me-in-production"
    FRONTEND_URL: str = "http://localhost:3000"

    # ── PostgreSQL ──
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "healthguide"
    DB_PASSWORD: str = "healthguide_local_pw"
    DB_NAME: str = "healthguide_db"

    DB_POOL_MIN_SIZE: int = 2
    DB_POOL_MAX_SIZE: int = 10

    @property
    def database_url(self) -> str:
        base = f"asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        return f"{base}?minsize={self.DB_POOL_MIN_SIZE}&maxsize={self.DB_POOL_MAX_SIZE}"

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

    # ── OAuth ──
    OAUTH_KAKAO_CLIENT_ID: str = ""
    OAUTH_KAKAO_CLIENT_SECRET: str = ""
    OAUTH_KAKAO_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/kakao/callback"
    OAUTH_GOOGLE_CLIENT_ID: str = ""
    OAUTH_GOOGLE_CLIENT_SECRET: str = ""
    OAUTH_GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/google/callback"

    # ── 개발용 테스터 ──
    DEV_TESTER_EMAIL: str = "tester@healthguide.dev"
    DEV_TESTER_NICKNAME: str = "테스터"
    DEV_TESTER_NAME: str = "개발테스터"

    # ── AWS S3 ──
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_S3_REGION: str = "ap-northeast-2"
    AWS_S3_BUCKET_NAME: str = "ah-02-07-healthguide"

    # ── OpenAI ──
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    # ── 공공데이터포털 ──
    PUBLIC_DATA_API_KEY: str = ""

    # ── 카카오 알림톡 (✅ 신규) ──────────────────
    # 솔라피(https://solapi.com) 경유 발송 기준
    # 다른 솔루션사 사용 시 kakao_notification.py 수정
    KAKAO_API_KEY: str = ""  # 솔라피 API Key
    KAKAO_API_SECRET: str = ""  # 솔라피 API Secret
    KAKAO_SENDER_KEY: str = ""  # 카카오 채널 발신 프로필 키
    KAKAO_CHANNEL_ID: str = ""  # 카카오 채널 ID (@ 포함, 예: @healthguide)
    KAKAO_TEMPLATE_ID_REMINDER: str = ""  # 복약 알림 템플릿 ID

    # ── Langfuse ──
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_BASE_URL: str = "https://cloud.langfuse.com"
    LANGFUSE_TRACING: bool = False

    # ── vLLM ──
    VLLM_HOST: str = "localhost"
    VLLM_PORT: int = 8001

    # ── AI Worker 큐 과부하 제어 ──
    WORKER_MAX_QUEUE_SIZE: int = 10

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
    return Settings()


settings = get_settings()
