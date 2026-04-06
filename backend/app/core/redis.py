# app/core/redis.py
# ──────────────────────────────────────────────
# Redis 클라이언트 싱글턴 관리
# 앱 시작/종료 시 연결/해제 처리
# ──────────────────────────────────────────────

import redis.asyncio as aioredis

from app.core.config import get_settings

# 모듈 레벨 변수로 Redis 클라이언트를 보관
# init_redis()가 호출되기 전에는 None
_redis_client: aioredis.Redis | None = None


async def init_redis() -> aioredis.Redis:
    """
    Redis 연결을 초기화하고 클라이언트를 반환합니다.
    앱의 lifespan startup 이벤트에서 호출하세요.
    """
    global _redis_client
    settings = get_settings()
    _redis_client = aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,  # bytes 대신 str로 디코딩
        max_connections=20,
    )
    # 연결 테스트
    await _redis_client.ping()
    return _redis_client


async def close_redis() -> None:
    """Redis 연결을 안전하게 종료합니다."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None


def get_redis() -> aioredis.Redis:
    """
    현재 Redis 클라이언트를 반환합니다.
    init_redis()가 호출된 후에만 사용하세요.

    사용 예시:
        from app.core.redis import get_redis
        redis = get_redis()
        await redis.set("key", "value")
    """
    if _redis_client is None:
        raise RuntimeError("Redis가 초기화되지 않았습니다. 앱 startup에서 init_redis()를 먼저 호출하세요.")
    return _redis_client
