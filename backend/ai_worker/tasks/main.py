# ai_worker/main.py
# ──────────────────────────────────────────────
# AI Worker 진입점
#
# Redis 큐에서 작업을 가져와 처리하는 메인 루프.
# Worker가 죽어도 작업이 유실되지 않는 안정적인 큐 메커니즘:
#
# 1. BRPOPLPUSH: 큐에서 꺼내면서 동시에 processing 리스트로 이동
#    → Worker가 여기서 죽어도 작업이 processing 리스트에 남아있음
# 2. Heartbeat: Worker가 살아있음을 주기적으로 Redis에 기록
# 3. Recovery: 주기적으로 processing 리스트를 확인하여
#    하트비트가 만료된 (= Worker가 죽은) 작업을 큐에 다시 넣음
# 4. Retry: 실패한 작업은 retry_count를 증가시키고 재시도
#    max_retries 초과 시 실패 처리
# ──────────────────────────────────────────────

import asyncio
import json
import signal
import uuid
from datetime import UTC, datetime

import ai_worker.tasks.chat_filter  # noqa: F401 — 황보수호

# ── 중요: 작업 핸들러 모듈을 import하여 @register_task 데코레이터가 실행되도록 함 ──
# 팀원이 새 tasks 모듈을 추가하면 여기에 import를 추가하세요!
import ai_worker.tasks.medical_doc  # noqa: F401 — 이승원
import ai_worker.tasks.pill_analysis  # noqa: F401 — 안은지
from ai_worker.core.config import get_worker_settings
from ai_worker.core.logger import setup_logger
from ai_worker.core.redis_client import close_worker_redis, get_worker_redis
from ai_worker.tasks import TASK_HANDLERS

logger = setup_logger("ai_worker")

# Worker 고유 ID (여러 Worker 인스턴스 구분용)
WORKER_ID = f"worker:{uuid.uuid4().hex[:8]}"

# 종료 신호 플래그
_shutdown_event = asyncio.Event()


def _handle_signal(sig, frame):
    """SIGINT/SIGTERM 시 그레이스풀 종료."""
    logger.info(f"종료 신호 수신: {sig}. 현재 작업 완료 후 종료합니다...")
    _shutdown_event.set()


async def _update_heartbeat(redis, processing_key: str, task_id: str) -> None:
    """
    하트비트를 업데이트합니다.
    Worker가 살아있는 동안 이 키의 TTL이 갱신됩니다.
    TTL이 만료되면 다른 Worker가 이 작업을 고아 작업으로 판단하고 복구합니다.
    """
    settings = get_worker_settings()
    heartbeat_key = f"{settings.WORKER_PROCESSING_PREFIX}{task_id}:heartbeat"
    await redis.set(heartbeat_key, WORKER_ID, ex=settings.WORKER_HEARTBEAT_TTL)


async def _heartbeat_loop(redis, task_id: str) -> None:
    """
    백그라운드에서 주기적으로 하트비트를 갱신하는 코루틴.
    작업 처리 중 이 코루틴이 함께 실행됩니다.
    """
    settings = get_worker_settings()
    try:
        while not _shutdown_event.is_set():
            await _update_heartbeat(redis, "", task_id)
            await asyncio.sleep(settings.WORKER_HEARTBEAT_INTERVAL)
    except asyncio.CancelledError:
        pass  # 정상 취소


async def _process_task(redis, task_data: dict) -> None:
    """
    단일 작업을 처리합니다.

    흐름:
    1. 작업 상태를 "processing"으로 변경
    2. 하트비트 코루틴 시작
    3. 해당 작업 유형의 핸들러 호출
    4. 결과를 Redis에 저장
    5. processing 리스트에서 제거
    6. 실패 시 재시도 또는 실패 처리
    """
    settings = get_worker_settings()
    task_id = task_data["task_id"]
    task_type = task_data["task_type"]
    payload = task_data["payload"]
    retry_count = task_data.get("retry_count", 0)
    max_retries = task_data.get("max_retries", settings.WORKER_MAX_RETRIES)

    meta_key = f"{settings.WORKER_RESULT_PREFIX}{task_id}:meta"
    result_key = f"{settings.WORKER_RESULT_PREFIX}{task_id}"
    processing_key = f"{settings.WORKER_PROCESSING_PREFIX}{task_id}"

    logger.info(f"작업 처리 시작: {task_id} (type={task_type}, retry={retry_count}/{max_retries})")

    # 상태를 "processing"으로 변경
    task_data["status"] = "processing"
    task_data["updated_at"] = datetime.now(UTC).isoformat()
    task_data["worker_id"] = WORKER_ID
    await redis.set(
        meta_key,
        json.dumps(task_data, ensure_ascii=False),
        ex=settings.WORKER_TASK_TIMEOUT * 2,
    )

    # processing 리스트에 기록 (복구용)
    await redis.set(
        processing_key,
        json.dumps(task_data, ensure_ascii=False),
        ex=settings.WORKER_TASK_TIMEOUT * 2,
    )

    # 하트비트 시작
    heartbeat_task = asyncio.create_task(_heartbeat_loop(redis, task_id))

    try:
        # 핸들러 조회
        handler = TASK_HANDLERS.get(task_type)
        if handler is None:
            raise ValueError(f"알 수 없는 작업 유형: {task_type}")

        # 핸들러 실행 (타임아웃 적용)
        result = await asyncio.wait_for(
            handler(payload),
            timeout=settings.WORKER_TASK_TIMEOUT,
        )

        # 성공: 결과 저장
        result_data = {
            "task_id": task_id,
            "task_type": task_type,
            "status": "completed",
            "result": result,
            "completed_at": datetime.now(UTC).isoformat(),
        }
        await redis.set(result_key, json.dumps(result_data, ensure_ascii=False), ex=86400)  # 24시간 보관

        # 메타 상태 업데이트
        task_data["status"] = "completed"
        task_data["updated_at"] = datetime.now(UTC).isoformat()
        await redis.set(meta_key, json.dumps(task_data, ensure_ascii=False), ex=86400)

        logger.info(f"✅ 작업 완료: {task_id}")

    except TimeoutError:
        logger.error(f"⏰ 작업 타임아웃: {task_id} ({settings.WORKER_TASK_TIMEOUT}초 초과)")
        await _handle_failure(redis, task_data, "작업 처리 시간 초과")

    except Exception as e:
        logger.error(f"❌ 작업 실패: {task_id} — {e}", exc_info=True)
        await _handle_failure(redis, task_data, str(e))

    finally:
        # 하트비트 중지
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass

        # processing 키 제거
        await redis.delete(processing_key)

        # 하트비트 키 제거
        heartbeat_key = f"{settings.WORKER_PROCESSING_PREFIX}{task_id}:heartbeat"
        await redis.delete(heartbeat_key)


async def _handle_failure(redis, task_data: dict, error_message: str) -> None:
    """
    작업 실패 처리.
    재시도 횟수가 남아있으면 큐에 다시 넣고,
    초과하면 최종 실패로 기록합니다.
    """
    settings = get_worker_settings()
    task_id = task_data["task_id"]
    retry_count = task_data.get("retry_count", 0)
    max_retries = task_data.get("max_retries", settings.WORKER_MAX_RETRIES)

    meta_key = f"{settings.WORKER_RESULT_PREFIX}{task_id}:meta"
    result_key = f"{settings.WORKER_RESULT_PREFIX}{task_id}"

    if retry_count < max_retries:
        # 재시도: retry_count 증가 후 큐에 다시 넣기
        task_data["retry_count"] = retry_count + 1
        task_data["status"] = "retrying"
        task_data["updated_at"] = datetime.now(UTC).isoformat()
        task_data["last_error"] = error_message

        await redis.set(
            meta_key,
            json.dumps(task_data, ensure_ascii=False),
            ex=settings.WORKER_TASK_TIMEOUT * 2,
        )

        # 큐에 다시 넣기 (약간의 딜레이 후)
        await asyncio.sleep(min(2**retry_count, 30))  # 지수 백오프: 1s, 2s, 4s, ... 최대 30s
        await redis.lpush(settings.WORKER_QUEUE_NAME, json.dumps(task_data, ensure_ascii=False))

        logger.warning(f"🔄 작업 재시도 예정: {task_id} ({retry_count + 1}/{max_retries})")

    else:
        # 최종 실패
        task_data["status"] = "failed"
        task_data["updated_at"] = datetime.now(UTC).isoformat()
        task_data["last_error"] = error_message

        await redis.set(meta_key, json.dumps(task_data, ensure_ascii=False), ex=86400)

        result_data = {
            "task_id": task_id,
            "task_type": task_data.get("task_type"),
            "status": "failed",
            "error": error_message,
            "failed_at": datetime.now(UTC).isoformat(),
        }
        await redis.set(result_key, json.dumps(result_data, ensure_ascii=False), ex=86400)

        logger.error(f"💀 작업 최종 실패: {task_id} (재시도 {max_retries}회 초과)")


async def _recover_orphan_tasks(redis) -> None:
    """
    고아 작업(Worker가 죽어서 처리 중 상태로 남은 작업)을 복구합니다.

    processing 리스트의 각 작업에 대해:
    - 하트비트가 살아있으면 → 다른 Worker가 처리 중이므로 건드리지 않음
    - 하트비트가 만료되었으면 → Worker가 죽은 것으로 판단, 큐에 재등록
    """
    settings = get_worker_settings()

    # processing: 접두어를 가진 모든 키 스캔
    pattern = f"{settings.WORKER_PROCESSING_PREFIX}*"
    recovered_count = 0

    async for key in redis.scan_iter(match=pattern):
        # heartbeat 키는 건너뜀
        if ":heartbeat" in key:
            continue

        # task_id 추출
        # 키 형태: "ai_processing:medical_doc_analysis:abcdef12"
        task_id = key.replace(settings.WORKER_PROCESSING_PREFIX, "")

        # 하트비트 확인
        heartbeat_key = f"{settings.WORKER_PROCESSING_PREFIX}{task_id}:heartbeat"
        heartbeat = await redis.get(heartbeat_key)

        if heartbeat is not None:
            # 하트비트가 살아있으면 다른 Worker가 처리 중
            continue

        # 하트비트 만료 → 고아 작업 복구
        task_json = await redis.get(key)
        if task_json is None:
            continue

        task_data = json.loads(task_json)
        logger.warning(f"🔧 고아 작업 발견, 복구 중: {task_id}")

        # 재시도로 처리
        await _handle_failure(redis, task_data, "Worker 장애로 인한 작업 복구")

        # processing 키 제거
        await redis.delete(key)
        recovered_count += 1

    if recovered_count > 0:
        logger.info(f"🔧 고아 작업 {recovered_count}건 복구 완료")


async def _recovery_loop(redis) -> None:
    """주기적으로 고아 작업을 복구하는 백그라운드 루프."""
    settings = get_worker_settings()
    while not _shutdown_event.is_set():
        try:
            await _recover_orphan_tasks(redis)
        except Exception as e:
            logger.error(f"고아 작업 복구 실패: {e}", exc_info=True)

        # 다음 복구 체크까지 대기
        try:
            await asyncio.wait_for(
                _shutdown_event.wait(),
                timeout=settings.WORKER_RECOVERY_INTERVAL,
            )
            break  # shutdown 이벤트가 set되면 종료
        except TimeoutError:
            continue  # 타임아웃 → 다시 복구 체크


async def _main_loop() -> None:
    """
    Worker 메인 루프.

    BRPOPLPUSH를 사용하여 큐에서 작업을 꺼내고,
    동시에 processing 리스트로 이동시킵니다.
    이렇게 하면 작업을 꺼낸 직후 Worker가 죽어도
    processing 리스트에 작업이 남아있어 복구 가능합니다.

    Note:
        Redis 7에서는 BRPOPLPUSH가 deprecated되고 BLMOVE를 사용합니다.
        호환성을 위해 BLMOVE를 사용합니다.
    """
    settings = get_worker_settings()
    redis = await get_worker_redis()

    logger.info(f"🏭 AI Worker 시작 (ID: {WORKER_ID})")
    logger.info(f"   큐 이름: {settings.WORKER_QUEUE_NAME}")
    logger.info(f"   등록된 핸들러: {list(TASK_HANDLERS.keys())}")

    # processing 리스트 이름 (큐 이름 + :processing)
    processing_list = f"{settings.WORKER_QUEUE_NAME}:processing:{WORKER_ID}"

    # 백그라운드 고아 작업 복구 루프 시작
    recovery_task = asyncio.create_task(_recovery_loop(redis))

    try:
        while not _shutdown_event.is_set():
            try:
                # 큐에서 작업 가져오기 (블로킹, 타임아웃으로 종료 체크 가능)
                # BLMOVE: source → destination (RIGHT → LEFT)
                # 큐(RIGHT에서 꺼냄) → processing 리스트(LEFT에 넣음)
                raw_task = await redis.blmove(
                    settings.WORKER_QUEUE_NAME,  # source
                    processing_list,  # destination
                    timeout=settings.WORKER_POLL_INTERVAL,
                    wherefrom="RIGHT",
                    whereto="LEFT",
                )

                if raw_task is None:
                    # 타임아웃 (큐가 비어있음) → 다시 루프
                    continue

                # 작업 데이터 파싱
                task_data = json.loads(raw_task)

                # 작업 처리
                await _process_task(redis, task_data)

                # processing 리스트에서 제거
                await redis.lrem(processing_list, 1, raw_task)

            except json.JSONDecodeError as e:
                logger.error(f"작업 데이터 파싱 실패: {e}")
                continue
            except Exception as e:
                logger.error(f"작업 처리 중 예외 발생: {e}", exc_info=True)
                await asyncio.sleep(1)  # 연속 에러 방지 대기

    finally:
        # 고아 복구 루프 종료
        recovery_task.cancel()
        try:
            await recovery_task
        except asyncio.CancelledError:
            pass

        logger.info(f"🛑 AI Worker 종료 (ID: {WORKER_ID})")


async def main() -> None:
    """Worker 엔트리포인트."""
    # 시그널 핸들러 등록 (그레이스풀 종료)
    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    try:
        await _main_loop()
    finally:
        await close_worker_redis()


if __name__ == "__main__":
    asyncio.run(main())
