# ===========================================================
# app/services/db_init_service.py
# ===========================================================

import logging
from pathlib import Path

from tortoise import Tortoise

logger = logging.getLogger(__name__)

_BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _resolve_sql_path(filename: str) -> Path:
    candidates = [
        _BASE_DIR / "scripts" / "sql" / filename,
        Path("/code") / "scripts" / "sql" / filename,
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


async def _execute_sql_file(filepath: Path, label: str) -> None:
    if not filepath.exists():
        logger.warning("[DB Init] %s 파일이 없습니다: %s", label, filepath)
        return

    sql = filepath.read_text(encoding="utf-8")
    if not sql.strip():
        logger.warning("[DB Init] %s 파일이 비어 있습니다: %s", label, filepath)
        return

    conn = Tortoise.get_connection("default")

    try:
        # pool 모드 (Docker, 멀티 워커)
        if hasattr(conn, "_pool") and conn._pool is not None:
            async with conn._pool.acquire() as raw_conn:
                await raw_conn.execute(sql)
        # 단일 커넥션 모드 (로컬 개발)
        elif hasattr(conn, "_connection") and conn._connection is not None:
            await conn._connection.execute(sql)
        else:
            # pool/connection 모두 없을 때 — acquire로 새 커넥션 획득
            async with conn.acquire_connection() as raw_conn:
                await raw_conn.execute(sql)

        logger.info("[DB Init] %s 실행 완료: %s", label, filepath.name)
    except Exception as e:
        logger.error("[DB Init] %s 실행 실패: %s\n%s", label, filepath.name, e)
        raise


async def run_ddl() -> None:
    logger.info("[DB Init] DDL 실행 시작...")
    await _execute_sql_file(_resolve_sql_path("create_tables.sql"), "DDL")


async def run_seed_common_codes() -> None:
    logger.info("[DB Init] 공통코드 시딩 시작...")
    await _execute_sql_file(_resolve_sql_path("seed_common_codes.sql"), "SEED")


async def initialize_database() -> None:
    await run_ddl()
    await run_seed_common_codes()
    logger.info("[DB Init] 데이터베이스 초기화 완료")
