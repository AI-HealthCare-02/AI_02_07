# ai_worker/core/redis_client.py
# ──────────────────────────────────────────────
# Worker 전용 Redis 클라이언트
# 동기(sync) + 비동기(async) 모두 지원
# ──────────────────────────────────────────────

import redis.asyncio as aioredis

from ai_worker.core.config import get_worker_settings

_redis_client: aioredis.Redis | None = None


async def get_worker_redis() -> aioredis.Redis:
    """
    Worker용 Redis 클라이언트를 반환합니다.
    최초 호출 시 연결을 생성하고, 이후에는 기존 연결을 재사용합니다.
    """
    global _redis_client
    if _redis_client is None:
        settings = get_worker_settings()
        _redis_client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=10,
        )
        await _redis_client.ping()
    return _redis_client


async def close_worker_redis() -> None:
    """Worker Redis 연결 종료."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
