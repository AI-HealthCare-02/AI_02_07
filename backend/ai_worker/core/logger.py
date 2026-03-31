# ai_worker/core/logger.py
# ──────────────────────────────────────────────
# Worker 전용 로거 설정
# ──────────────────────────────────────────────

import logging
import sys


def setup_logger(name: str = "ai_worker", level: int = logging.INFO) -> logging.Logger:
    """
    Worker용 로거를 설정하고 반환합니다.

    Args:
        name: 로거 이름
        level: 로그 레벨

    Returns:
        설정된 Logger 인스턴스
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # 핸들러가 이미 있으면 중복 추가 방지
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)

        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s (%(filename)s:%(lineno)d): %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
