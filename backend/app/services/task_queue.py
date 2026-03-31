# app/services/task_queue.py
# ──────────────────────────────────────────────
# Redis 기반 작업 큐 (API 서버 → AI Worker)
# Worker가 추론 중 죽더라도 작업이 유실되지 않도록
# 안정적인 큐 메커니즘을 구현합니다.
#
# 구조:
#   1. API 서버가 작업을 Redis 큐에 PUSH
#   2. Worker가 큐에서 POP (BRPOPLPUSH로 processing 리스트로 이동)
#   3. Worker가 작업 완료 후 processing에서 제거 + 결과 저장
#   4. Worker가 죽으면 processing에 남은 작업을 재처리
# ──────────────────────────────────────────────

import json
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum

from app.core.config import get_settings
from app.core.redis import get_redis

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """작업 상태 열거형"""

    PENDING = "pending"  # 큐에 대기 중
    PROCESSING = "processing"  # Worker가 처리 중
    COMPLETED = "completed"  # 완료
    FAILED = "failed"  # 실패
    RETRYING = "retrying"  # 재시도 중


class TaskType(str, Enum):
    """
    작업 유형 열거형.
    팀원이 새로운 AI 작업을 추가할 때 여기에 타입을 등록하세요.
    """

    MEDICAL_DOC_ANALYSIS = "medical_doc_analysis"  # 의료 문서 분석 (이승원)
    PILL_ANALYSIS = "pill_analysis"  # 알약 분석 (안은지)
    CHAT_FILTER = "chat_filter"  # 3단계 질문 필터링 (황보수호)


async def enqueue_task(
    task_type: TaskType,
    payload: dict,
    user_id: int | None = None,
    priority: int = 0,
) -> str:
    """
    AI 작업을 Redis 큐에 추가합니다.

    Args:
        task_type: 작업 유형 (TaskType enum)
        payload: 작업 데이터 (JSON 직렬화 가능해야 함)
                 예: {"file_s3_key": "medical-docs/...", "options": {...}}
        user_id: 요청한 사용자 ID (선택)
        priority: 우선순위 (0=일반, 값이 높을수록 높은 우선순위) — 향후 확장용

    Returns:
        task_id: 생성된 작업 고유 ID (결과 조회 시 사용)

    사용 예시:
        task_id = await enqueue_task(
            task_type=TaskType.MEDICAL_DOC_ANALYSIS,
            payload={"file_s3_key": "medical-docs/2026/03/30/report.pdf"},
            user_id=42,
        )
        # 이후 get_task_result(task_id)로 결과 조회
    """
    settings = get_settings()
    redis = get_redis()

    # 고유 작업 ID 생성
    task_id = f"{task_type.value}:{uuid.uuid4().hex}"

    # 작업 데이터 구성
    task_data = {
        "task_id": task_id,
        "task_type": task_type.value,
        "payload": payload,
        "user_id": user_id,
        "status": TaskStatus.PENDING.value,
        "retry_count": 0,
        "max_retries": settings.WORKER_MAX_RETRIES,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    task_json = json.dumps(task_data, ensure_ascii=False)

    # 작업 메타데이터를 별도 키에 저장 (상태 조회용)
    meta_key = f"{settings.WORKER_RESULT_PREFIX}{task_id}:meta"
    await redis.set(meta_key, task_json, ex=settings.WORKER_TASK_TIMEOUT * 2)

    # 큐에 작업 PUSH (왼쪽에 넣고 Worker는 오른쪽에서 꺼냄 = FIFO)
    await redis.lpush(settings.WORKER_QUEUE_NAME, task_json)

    logger.info(f"작업 큐에 추가: {task_id} (type={task_type.value})")
    return task_id


async def get_task_status(task_id: str) -> dict | None:
    """
    작업의 현재 상태를 조회합니다.

    Returns:
        작업 메타데이터 딕셔너리 또는 None (없으면)
    """
    settings = get_settings()
    redis = get_redis()

    meta_key = f"{settings.WORKER_RESULT_PREFIX}{task_id}:meta"
    data = await redis.get(meta_key)

    if data is None:
        return None
    return json.loads(data)


async def get_task_result(task_id: str) -> dict | None:
    """
    완료된 작업의 결과를 조회합니다.

    Returns:
        결과 딕셔너리 또는 None (아직 완료되지 않았거나 없으면)

    사용 예시:
        result = await get_task_result(task_id)
        if result and result["status"] == "completed":
            analysis = result["result"]
    """
    settings = get_settings()
    redis = get_redis()

    result_key = f"{settings.WORKER_RESULT_PREFIX}{task_id}"
    data = await redis.get(result_key)

    if data is None:
        return None
    return json.loads(data)


async def wait_for_task_result(
    task_id: str,
    timeout: int = 60,
    poll_interval: float = 0.5,
) -> dict | None:
    """
    작업 결과가 나올 때까지 대기합니다 (폴링 방식).
    SSE가 아닌 일반 HTTP 요청에서 동기적 결과가 필요할 때 사용.

    Args:
        task_id: 작업 ID
        timeout: 최대 대기 시간 (초)
        poll_interval: 폴링 간격 (초)

    Returns:
        결과 딕셔너리 또는 None (타임아웃)
    """
    import asyncio

    elapsed = 0.0
    while elapsed < timeout:
        result = await get_task_result(task_id)
        if result is not None:
            return result
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

    return None
