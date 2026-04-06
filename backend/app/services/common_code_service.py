# ===========================================================
# app/services/common_code_service.py
# 공통코드 조회 · 검증 · 캐시 서비스
#
# ● DB 의 복합 PK (group_code, code) 에 맞춰 Raw SQL 사용
# ● Redis 캐시로 조회 성능 최적화
# ● DDL / 시딩은 db_init_service.py + Raw SQL 파일이 담당
# ===========================================================

import json
import logging

from tortoise import Tortoise

from app.core.redis import get_redis

logger = logging.getLogger(__name__)

# 캐시 설정
CACHE_PREFIX = "common_code"
CACHE_TTL = 60 * 60  # 1시간


# ===========================================================
# 조회
# ===========================================================


async def get_codes_by_group(group_code: str) -> list[dict]:
    """
    그룹에 속한 모든 활성 코드를 반환합니다.
    Redis 캐시를 우선 사용합니다.

    Parameters
    ----------
    group_code : str
        그룹 코드 (예: 'GENDER', 'JOB_STATUS')

    Returns
    -------
    list[dict]
        [{'code': 'MALE', 'code_name': '남성', 'sort_order': 1}, ...]

    Usage
    -----
        genders = await get_codes_by_group('GENDER')
    """
    redis = get_redis()
    cache_key = f"{CACHE_PREFIX}:group:{group_code}"

    # 1) 캐시 확인
    if redis:
        try:
            cached = await redis.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as e:
            logger.warning("[CommonCode] 캐시 조회 실패: %s", e)

    # 2) DB 조회 (Raw SQL)
    conn = Tortoise.get_connection("default")
    rows = await conn.execute_query_dict(
        "SELECT group_code, code, code_name, sort_order "
        "FROM common_code "
        "WHERE group_code = $1 AND is_used = TRUE "
        "ORDER BY sort_order",
        [group_code],
    )

    # 3) 캐시 저장
    if redis and rows:
        try:
            await redis.set(
                cache_key,
                json.dumps(rows, ensure_ascii=False),
                ex=CACHE_TTL,
            )
        except Exception as e:
            logger.warning("[CommonCode] 캐시 저장 실패: %s", e)

    return rows


async def get_code_name(group_code: str, code: str) -> str | None:
    """
    특정 코드의 한글 이름을 반환합니다.

    Usage
    -----
        name = await get_code_name('GENDER', 'MALE')  # '남성'
    """
    redis = get_redis()
    cache_key = f"{CACHE_PREFIX}:name:{group_code}:{code}"

    # 1) 캐시 확인
    if redis:
        try:
            cached = await redis.get(cache_key)
            if cached:
                return cached
        except Exception:
            pass

    # 2) DB 조회
    conn = Tortoise.get_connection("default")
    rows = await conn.execute_query_dict(
        "SELECT code_name FROM common_code WHERE group_code = $1 AND code = $2 AND is_used = TRUE",
        [group_code, code],
    )

    if not rows:
        return None

    name = rows[0]["code_name"]

    # 3) 캐시 저장
    if redis:
        try:
            await redis.set(cache_key, name, ex=CACHE_TTL)
        except Exception:
            pass

    return name


async def validate_common_code(group_code: str, code: str) -> bool:
    """
    group_code + code 조합이 유효한지 검증합니다.

    Usage
    -----
        if not await validate_common_code('GENDER', user_input):
            raise HTTPException(400, "유효하지 않은 성별 코드")
    """
    conn = Tortoise.get_connection("default")
    rows = await conn.execute_query_dict(
        "SELECT 1 FROM common_code WHERE group_code = $1 AND code = $2 AND is_used = TRUE LIMIT 1",
        [group_code, code],
    )
    return len(rows) > 0


async def get_all_groups() -> list[dict]:
    """
    모든 활성 그룹 코드를 반환합니다.

    Returns
    -------
    list[dict]
        [{'group_code': 'GENDER', 'group_name': '성별', 'description': '...'}, ...]
    """
    conn = Tortoise.get_connection("default")
    return await conn.execute_query_dict(
        "SELECT group_code, group_name, description FROM common_group_code WHERE is_used = TRUE ORDER BY group_code"
    )


# ===========================================================
# 캐시 무효화
# ===========================================================


async def invalidate_group_cache(group_code: str) -> None:
    """
    특정 그룹의 캐시를 무효화합니다.
    관리자가 공통코드를 수정했을 때 호출하세요.
    """
    redis = get_redis()
    if not redis:
        return

    # 그룹 리스트 캐시
    await redis.delete(f"{CACHE_PREFIX}:group:{group_code}")

    # 개별 이름 캐시 패턴 삭제
    pattern = f"{CACHE_PREFIX}:name:{group_code}:*"
    cursor = 0
    while True:
        cursor, keys = await redis.scan(cursor, match=pattern, count=100)
        if keys:
            await redis.delete(*keys)
        if cursor == 0:
            break

    logger.info("[CommonCode] 캐시 무효화 완료: %s", group_code)
