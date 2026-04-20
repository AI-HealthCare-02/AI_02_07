# app/core/langfuse_client.py
# Langfuse 4.x — 앱 시작 시 1회 초기화만 담당
# 실제 tracing은 langfuse.openai drop-in이 자동 처리

import logging
import os

logger = logging.getLogger(__name__)


def init_langfuse() -> None:
    """
    앱 시작 시 1회 호출.
    환경변수를 세팅하면 langfuse.openai drop-in이 자동으로 인식한다.
    """
    try:
        from app.core.config import get_settings

        s = get_settings()
        if not (s.LANGFUSE_TRACING and s.LANGFUSE_PUBLIC_KEY and s.LANGFUSE_SECRET_KEY):
            logger.info("[Langfuse] tracing disabled")
            return

        os.environ.setdefault("LANGFUSE_PUBLIC_KEY", s.LANGFUSE_PUBLIC_KEY)
        os.environ.setdefault("LANGFUSE_SECRET_KEY", s.LANGFUSE_SECRET_KEY)
        os.environ.setdefault("LANGFUSE_HOST", s.LANGFUSE_BASE_URL)

        # get_client()를 한 번 호출해 내부 싱글턴 초기화
        from langfuse import get_client

        get_client()
        logger.info("[Langfuse] tracing enabled, host=%s", s.LANGFUSE_BASE_URL)
    except Exception as e:
        logger.warning("[Langfuse] init failed: %s", e)
