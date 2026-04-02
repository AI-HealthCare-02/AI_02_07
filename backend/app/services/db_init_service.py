# ===========================================================
# app/services/db_init_service.py
# 서버 시작 시 DDL 생성 및 공통코드 시딩을 Raw SQL로 실행
#
# ● Tortoise ORM의 generate_schemas 대신 Raw SQL을 직접 실행하여
#   복합 FK, CHECK 제약, 트리거 등 PostgreSQL 고유 기능을 보장합니다.
# ● IF NOT EXISTS / ON CONFLICT 덕분에 몇 번이든 재실행해도 안전합니다.
# ===========================================================

import logging
from pathlib import Path

from tortoise import Tortoise

logger = logging.getLogger(__name__)

# SQL 파일 경로 후보
# - 로컬: backend/scripts/sql/  (Path(__file__)에서 3단계 위 = backend/)
# - Docker: /code/scripts/sql/  (WORKDIR /code 기준)
_BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _resolve_sql_path(filename: str) -> Path:
    """
    로컬/Docker 환경 모두에서 SQL 파일 경로를 찾습니다.
    """
    candidates = [
        _BASE_DIR / "scripts" / "sql" / filename,     # 로컬 (backend/)
        Path("/code") / "scripts" / "sql" / filename, # Docker (/code/)
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
    raw_conn = conn._pool or conn._connection

    try:
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
