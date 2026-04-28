"""
scripts/backfill_imprint_metadata.py
──────────────────────────────────────────────
STEP 2: 기존 imprint 데이터 metadata backfill

실행:
  # dry-run
  DB_PORT=15432 uv run python scripts/backfill_imprint_metadata.py --dry-run

  # 실제 실행
  DB_PORT=15432 uv run python scripts/backfill_imprint_metadata.py

  # batch size 조정
  DB_PORT=15432 uv run python scripts/backfill_imprint_metadata.py --batch-size 50
──────────────────────────────────────────────
"""

import argparse
import asyncio
import json
import logging
import os

# ai_worker 경로 추가
import sys
from pathlib import Path

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai_worker.tasks.imprint_parser import parse_imprint_chunk

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def get_db_config() -> dict:
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "15432")),
        "user": os.getenv("DB_USER", "healthguide"),
        "password": os.getenv("DB_PASSWORD", "healthguide_local_pw"),
        "database": os.getenv("DB_NAME", "healthguide_db"),
    }


async def main(dry_run: bool, batch_size: int, force: bool) -> None:
    pool = await asyncpg.create_pool(**get_db_config(), min_size=1, max_size=3)

    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, chunk_text, metadata FROM drug_embeddings WHERE chunk_type = 'imprint'")

    total = len(rows)
    logger.info("대상 imprint 행: %d개 | dry_run=%s | batch_size=%d | force=%s", total, dry_run, batch_size, force)

    success = skip = fail = 0
    fail_samples: list[str] = []

    batch: list[tuple[int, str]] = []

    async def flush(b: list[tuple[int, str]]) -> None:
        nonlocal success, fail
        if not b or dry_run:
            if dry_run:
                success += len(b)
            return
        async with pool.acquire() as conn:
            async with conn.transaction():
                for row_id, new_meta_json in b:
                    await conn.execute(
                        "UPDATE drug_embeddings SET metadata = metadata || $1::jsonb WHERE id = $2",
                        new_meta_json,
                        row_id,
                    )
                    success += 1

    for row in rows:
        existing = row["metadata"] or {}
        if isinstance(existing, str):
            try:
                existing = json.loads(existing)
            except Exception:
                existing = {}

        # --force 없으면 이미 처리된 행 스킵
        if not force and existing.get("imprint_schema_version", 0) >= 1:
            skip += 1
            continue

        parsed = parse_imprint_chunk(row["chunk_text"])
        if parsed is None:
            fail += 1
            if len(fail_samples) < 3:
                fail_samples.append(row["chunk_text"][:80])
            continue

        batch.append((row["id"], json.dumps(parsed, ensure_ascii=False)))

        if len(batch) >= batch_size:
            try:
                await flush(batch)
            except Exception as e:
                logger.error("batch flush 실패: %s", e)
                fail += len(batch)
            batch = []

    if batch:
        try:
            await flush(batch)
        except Exception as e:
            logger.error("마지막 batch flush 실패: %s", e)
            fail += len(batch)

    await pool.close()

    logger.info("완료 | 총 %d개 | 성공 %d | 건너뜀 %d | 실패 %d", total, success, skip, fail)
    if fail_samples:
        logger.warning("실패 샘플: %s", fail_samples)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--force", action="store_true", help="이미 처리된 행도 재처리 (shape_normalized 버그 수정 등)")
    args = parser.parse_args()
    asyncio.run(main(args.dry_run, args.batch_size, args.force))
