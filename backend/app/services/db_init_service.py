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

# SQL 파일 경로 (프로젝트 루트 기준)
# main.py 에서 호출하므로 CWD = 프로젝트 루트
_BASE_DIR = Path(__file__).resolve().parent.parent.parent  # → AH_02_07/
_DDL_FILE = _BASE_DIR / "scripts" / "sql" / "create_tables.sql"
_SEED_FILE = _BASE_DIR / "scripts" / "sql" / "seed_common_codes.sql"


async def _execute_sql_file(filepath: Path, label: str) -> None:
    """
    SQL 파일 하나를 읽어서 PostgreSQL 커넥션으로 실행합니다.

    Parameters
    ----------
    filepath : Path
        실행할 .sql 파일의 절대 경로
    label : str
        로그에 표시할 작업 이름 (예: 'DDL', 'SEED')
    """
    if not filepath.exists():
        logger.warning("[DB Init] %s 파일이 없습니다: %s", label, filepath)
        return

    sql = filepath.read_text(encoding="utf-8")
    if not sql.strip():
        logger.warning("[DB Init] %s 파일이 비어 있습니다: %s", label, filepath)
        return

    # Tortoise asyncpg 백엔드는 execute_script 미구현
    # asyncpg 로우 커넥션을 직접 사용해야 멀티 구문 + DEFAULT 정상 처리
    conn = Tortoise.get_connection("default")
    raw_conn = conn._pool or conn._connection  # pool 또는 단일 커넥션

    try:
        await raw_conn.execute(sql)
        logger.info("[DB Init] %s 실행 완료: %s", label, filepath.name)
    except Exception as e:
        logger.error("[DB Init] %s 실행 실패: %s\n%s", label, filepath.name, e)
        raise


async def run_ddl() -> None:
    """
    create_tables.sql 을 실행하여 모든 테이블을 생성합니다.
    IF NOT EXISTS 덕분에 이미 존재하는 테이블은 건너뜁니다.
    """
    logger.info("[DB Init] DDL 실행 시작...")
    await _execute_sql_file(_DDL_FILE, "DDL")


async def run_seed_common_codes() -> None:
    """
    seed_common_codes.sql 을 실행하여 공통코드를 시딩합니다.
    ON CONFLICT 덕분에 이미 존재하는 코드는 업데이트만 합니다.
    """
    logger.info("[DB Init] 공통코드 시딩 시작...")
    await _execute_sql_file(_SEED_FILE, "SEED")


async def initialize_database() -> None:
    """
    DDL → 공통코드 순서로 실행합니다.
    main.py 의 startup 이벤트에서 호출하세요.

    Usage:
        from app.services.db_init_service import initialize_database
        await initialize_database()
    """
    await run_ddl()
    await run_seed_common_codes()
    logger.info("[DB Init] 데이터베이스 초기화 완료")
