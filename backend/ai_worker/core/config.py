# ai_worker/core/config.py
# ──────────────────────────────────────────────
# AI Worker 설정
# API 서버와 동일한 환경 변수를 사용하되,
# Worker 전용 설정이 추가됩니다.
# ──────────────────────────────────────────────

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    """
    AI Worker 전역 설정.
    API 서버의 Settings와 동일한 환경 변수 파일을 공유합니다.
    """

    # ── 앱 환경 ──
    APP_ENV: str = "local"

    # ── Redis (작업 큐) ──
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0

    @property
    def redis_url(self) -> str:
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # ── DB (Worker가 직접 결과를 DB에 쓸 때 사용) ──
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "healthguide"
    DB_PASSWORD: str = "healthguide_local_pw"
    DB_NAME: str = "healthguide_db"

    @property
    def database_url(self) -> str:
        return f"asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # ── AWS S3 (모델/이미지 다운로드) ──
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_S3_REGION: str = "ap-northeast-2"
    AWS_S3_BUCKET_NAME: str = "healthguide-local"

    # ── vLLM ──
    VLLM_HOST: str = "localhost"
    VLLM_PORT: int = 8001

    @property
    def vllm_base_url(self) -> str:
        return f"http://{self.VLLM_HOST}:{self.VLLM_PORT}/v1"

    # ── OpenAI (Worker에서도 GPT 호출이 필요할 수 있음) ──
    OPENAI_API_KEY: str = ""

    # ── Worker Queue 설정 ──
    WORKER_QUEUE_NAME: str = "ai_task_queue"
    WORKER_RESULT_PREFIX: str = "ai_result:"
    WORKER_PROCESSING_PREFIX: str = "ai_processing:"
    WORKER_MAX_RETRIES: int = 3
    WORKER_TASK_TIMEOUT: int = 300  # 초

    # ── Worker 동작 설정 ──
    WORKER_POLL_INTERVAL: int = 1  # 큐 폴링 간격 (초)
    WORKER_HEARTBEAT_INTERVAL: int = 10  # 하트비트 간격 (초)
    WORKER_HEARTBEAT_TTL: int = 30  # 하트비트 만료 시간 (초)
    WORKER_RECOVERY_INTERVAL: int = 60  # 고아 작업 복구 체크 간격 (초)

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[2] / "envs" / ".local.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_worker_settings() -> WorkerSettings:
    """Worker 설정 싱글턴 반환."""
    return WorkerSettings()
