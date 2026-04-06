# app/services/error_log_service.py
# ──────────────────────────────────────────────
# 시스템 오류 로그 서비스
# API 에러 발생 시 DB에 로그를 기록합니다.
# FastAPI 예외 핸들러에서 호출합니다.
# ──────────────────────────────────────────────

import logging
import traceback

from app.models.system_error_log import SystemErrorLog

logger = logging.getLogger(__name__)


async def log_error(
    error_type: str,
    error_message: str,
    user_id: int | None = None,
    request_url: str | None = None,
    exception: Exception | None = None,
) -> None:
    """
    시스템 오류를 DB에 기록합니다.

    Args:
        error_type: 에러 종류 (예: "API_FAIL", "DB_ERR", "AI_WORKER_ERR")
        error_message: 에러 메시지
        user_id: 에러 발생 당시 사용자 ID (로그인 중인 경우)
        request_url: 에러가 발생한 API URL
        exception: 원본 예외 객체 (스택 트레이스 추출용)
    """
    stack_trace = None
    if exception:
        stack_trace = traceback.format_exception(
            type(exception),
            exception,
            exception.__traceback__,
        )
        stack_trace = "".join(stack_trace)

    try:
        await SystemErrorLog.create(
            user_id=user_id,
            error_type=error_type,
            error_message=error_message,
            stack_trace=stack_trace,
            request_url=request_url,
        )
    except Exception as e:
        # DB 기록 자체가 실패하면 로거로만 기록
        logger.error(f"오류 로그 DB 기록 실패: {e}")
        logger.error(f"원본 오류: [{error_type}] {error_message}")
