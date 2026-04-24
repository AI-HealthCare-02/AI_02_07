# ai_worker/main.py
# AI Worker 진입점 — Redis 큐에서 작업을 꺼내 처리

import asyncio
import json
import logging

from ai_worker.core.config import get_worker_settings
from ai_worker.core.redis_client import close_worker_redis, get_worker_redis
from ai_worker.tasks.chat_filter import process_chat_filter
from ai_worker.tasks.pill_analysis import process_pill_analysis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

TASK_HANDLERS = {
    "chat_filter": process_chat_filter,
    "pill_analysis": process_pill_analysis,
}


async def process_task(task_data: dict) -> None:
    task_id: str = task_data["task_id"]
    task_type: str = task_data["task_type"]

    settings = get_worker_settings()
    redis = await get_worker_redis()

    handler = TASK_HANDLERS.get(task_type)
    if handler is None:
        logger.warning("알 수 없는 태스크 타입: %s", task_type)
        return

    logger.info("태스크 처리 시작: %s", task_id)

    try:
        result = await handler(task_data)
        status = "completed"
    except Exception as e:
        logger.error("태스크 처리 실패 [%s]: %s", task_id, e)
        result = {"error": str(e)}
        status = "failed"

    # 결과 저장
    result_key = f"{settings.WORKER_RESULT_PREFIX}{task_id}"
    await redis.set(
        result_key,
        json.dumps({"task_id": task_id, "status": status, "result": result}, ensure_ascii=False),
        ex=settings.WORKER_TASK_TIMEOUT,
    )
    logger.info("태스크 완료: %s (status=%s)", task_id, status)


async def run_worker() -> None:
    settings = get_worker_settings()
    redis = await get_worker_redis()
    logger.info("🤖 AI Worker 시작 (queue=%s)", settings.WORKER_QUEUE_NAME)

    # Langfuse 환경변수 세팅 (langfuse.openai drop-in이 자동 인식)
    try:
        import os

        if settings.LANGFUSE_TRACING and settings.LANGFUSE_PUBLIC_KEY:
            os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.LANGFUSE_PUBLIC_KEY)
            os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.LANGFUSE_SECRET_KEY)
            os.environ.setdefault("LANGFUSE_HOST", settings.LANGFUSE_BASE_URL)
            logger.info("[Langfuse] worker tracing enabled")
    except Exception as e:
        logger.warning("Langfuse 환경변수 세팅 실패: %s", e)

    try:
        while True:
            # BRPOP: 큐에 작업이 올 때까지 블로킹 대기 (timeout=5초)
            item = await redis.brpop(settings.WORKER_QUEUE_NAME, timeout=5)
            if item is None:
                continue

            _, raw = item
            try:
                task_data = json.loads(raw)
                await process_task(task_data)
            except json.JSONDecodeError as e:
                logger.error("태스크 파싱 실패: %s", e)

    except asyncio.CancelledError:
        logger.info("Worker 종료 중...")
    finally:
        await close_worker_redis()
        logger.info("Worker 종료 완료")


if __name__ == "__main__":
    asyncio.run(run_worker())
