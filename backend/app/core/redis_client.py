"""
Worker용 Redis 클라이언트
동기 방식 (Worker는 asyncio 없이도 동작 가능하도록)
"""

import json
from datetime import datetime

import redis

from ai_worker.core.config import settings

# Redis 키 규칙 (FastAPI 측과 동일)
QUEUE_KEY = "hg:queue:{task_type}"
TASK_KEY = "hg:task:{task_id}"
RESULT_KEY = "hg:result:{task_id}"
CHANNEL_KEY = "hg:channel:{task_id}"


class WorkerRedisClient:
    """Worker에서 사용하는 Redis 클라이언트"""

    def __init__(self):
        self.redis = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD or None,
            decode_responses=True,
        )

    # ─────────── 작업 꺼내기 ───────────

    def dequeue_task(self, task_type: str, timeout: int = 5) -> str | None:
        """
        큐에서 작업 ID를 꺼냄 (BRPOP — blocking).
        timeout 동안 작업이 없으면 None 반환.
        """
        queue_key = QUEUE_KEY.format(task_type=task_type)
        result = self.redis.brpop(queue_key, timeout=timeout)
        if result:
            _, task_id = result
            return task_id
        return None

    # ─────────── 작업 정보 조회 ───────────

    def get_task(self, task_id: str) -> dict | None:
        """작업 메타데이터 조회"""
        task_key = TASK_KEY.format(task_id=task_id)
        data = self.redis.hgetall(task_key)
        return data if data else None

    # ─────────── 상태 업데이트 ───────────

    def update_status(self, task_id: str, status: str):
        """작업 상태 업데이트"""
        task_key = TASK_KEY.format(task_id=task_id)
        self.redis.hset(
            task_key,
            mapping={
                "status": status,
                "updated_at": datetime.now().isoformat(),
            },
        )

    # ─────────── 결과 저장 ───────────

    def save_result(self, task_id: str, result: dict, ttl: int = 3600):
        """작업 결과를 Redis에 저장"""
        result_key = RESULT_KEY.format(task_id=task_id)
        self.redis.set(result_key, json.dumps(result, ensure_ascii=False), ex=ttl)

    # ─────────── SSE 토큰 전송 (Pub/Sub) ───────────

    def publish_event(self, task_id: str, event: str, data):
        """
        FastAPI SSE로 전달할 이벤트를 Pub/Sub으로 발행.

        Args:
            task_id: 작업 ID
            event: 이벤트 타입 (token, filter_blocked, error, done)
            data: 이벤트 데이터
        """
        channel = CHANNEL_KEY.format(task_id=task_id)
        message = json.dumps({"event": event, "data": data}, ensure_ascii=False)
        self.redis.publish(channel, message)

    # ─────────── 취소 여부 확인 ───────────

    def is_cancelled(self, task_id: str) -> bool:
        """작업이 취소되었는지 확인"""
        task_key = TASK_KEY.format(task_id=task_id)
        status = self.redis.hget(task_key, "status")
        return status == "cancelled"

    # ─────────── 재시도 카운트 ───────────

    def increment_retry(self, task_id: str) -> int:
        """재시도 횟수 증가 후 현재 값 반환"""
        task_key = TASK_KEY.format(task_id=task_id)
        return self.redis.hincrby(task_key, "retry_count", 1)

    def get_max_retries(self, task_id: str) -> int:
        task_key = TASK_KEY.format(task_id=task_id)
        val = self.redis.hget(task_key, "max_retries")
        return int(val) if val else 3

    # ─────────── 재등록 (재시도) ───────────

    def requeue_task(self, task_id: str, task_type: str):
        """실패한 작업을 큐에 다시 등록"""
        queue_key = QUEUE_KEY.format(task_type=task_type)
        self.redis.rpush(queue_key, task_id)
        self.update_status(task_id, "pending")
