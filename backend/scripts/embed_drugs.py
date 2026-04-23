"""
scripts/embed_drugs.py
──────────────────────────────────────────────
약품 데이터 임베딩 스크립트 (1회성 실행)

실행 방법:
  # 1. SSH 터널링 (별도 터미널에서 먼저 실행)
  ssh -i ~/.ssh/<key>.pem -L 15432:localhost:5432 ubuntu@13.209.187.137 -N

  # 2. 허가정보 임베딩 (efficacy/caution/ingredient)
  DB_PORT=15432 uv run python scripts/embed_drugs.py

  # 3. 낱알식별 임베딩 (imprint) - fetch_pill_imprint.py 실행 후
  DB_PORT=15432 uv run python scripts/embed_drugs.py --imprint-only

  # 특정 파일만 실행 (테스트용)
  DB_PORT=15432 uv run python scripts/embed_drugs.py --files drugs_0000.jsonl

  # 재시도 (이미 임베딩된 항목 건너뜀)
  DB_PORT=15432 uv run python scripts/embed_drugs.py --skip-existing
──────────────────────────────────────────────
"""

import argparse
import asyncio
import json
import logging
import os
import time
from pathlib import Path

import asyncpg
from openai import AsyncOpenAI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ── 설정 ──────────────────────────────────────
DRUG_JSON_DIR = Path(__file__).parent.parent / "drug_json"
IMPRINT_FILE = DRUG_JSON_DIR / "imprint_data.jsonl"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536
BATCH_SIZE = 100          # OpenAI API 배치 크기
CONCURRENT_BATCHES = 5    # 동시 처리 배치 수
RATE_LIMIT_DELAY = 0.5    # 배치 간 딜레이(초)


# ── DB 연결 설정 ───────────────────────────────
def get_db_config() -> dict:
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "15432")),  # SSH 터널 기본 포트
        "user": os.getenv("DB_USER", "healthguide"),
        "password": os.getenv("DB_PASSWORD", "healthguide_local_pw"),
        "database": os.getenv("DB_NAME", "healthguide_db"),
    }


# ── 허가정보 청크 생성 ─────────────────────────
def build_chunks(record: dict) -> list[dict]:
    """
    약품 허가정보 레코드 1개를 청크 단위로 분리.
    chunk_type: 'efficacy' | 'caution' | 'ingredient'
    """
    item_seq = record.get("item_seq", "")
    item_name = record.get("item_name", "")
    etc_otc_code = record.get("etc_otc_code", "")
    chunks = []

    # 1. 효능효과
    efficacy = record.get("효능효과", "")
    if efficacy and efficacy.strip():
        chunks.append({
            "item_seq": item_seq,
            "item_name": item_name,
            "etc_otc_code": etc_otc_code,
            "chunk_type": "efficacy",
            "chunk_text": f"[{item_name}] 효능효과: {efficacy.strip()}",
            "metadata": record,
        })

    # 2. 주의사항 (dict → 텍스트 변환)
    caution = record.get("주의사항", "")
    if caution:
        if isinstance(caution, dict):
            caution_text = "\n".join(
                f"{k}: {v}" for k, v in caution.items() if v
            )
        else:
            caution_text = str(caution)

        if caution_text.strip():
            chunks.append({
                "item_seq": item_seq,
                "item_name": item_name,
                "etc_otc_code": etc_otc_code,
                "chunk_type": "caution",
                "chunk_text": f"[{item_name}] 주의사항: {caution_text.strip()[:8000]}",
                "metadata": record,
            })

    # 3. 주성분
    ingredient = record.get("main_item_ingr", "")
    if ingredient and ingredient.strip():
        chunks.append({
            "item_seq": item_seq,
            "item_name": item_name,
            "etc_otc_code": etc_otc_code,
            "chunk_type": "ingredient",
            "chunk_text": f"[{item_name}] 주성분: {ingredient.strip()}",
            "metadata": record,
        })

    return chunks


# ── 낱알식별 청크 생성 ─────────────────────────
def build_imprint_chunk(record: dict) -> dict | None:
    """
    낱알식별 레코드 1개를 imprint 청크로 변환.
    각인 정보가 없으면 None 반환.

    chunk_text 예시:
      [타이레놀정500mg] 각인: 앞면 TYLENOL, 뒷면 500 | 색상: 흰색 | 모양: 타원형 | 크기: 14.0x7.0mm
    """
    item_seq = record.get("item_seq", "")
    item_name = record.get("item_name", "")
    if not item_seq or not item_name:
        return None

    print_front = record.get("print_front", "").strip()
    print_back = record.get("print_back", "").strip()
    drug_shape = record.get("drug_shape", "").strip()
    color1 = record.get("color_class1", "").strip()
    color2 = record.get("color_class2", "").strip()
    leng_long = record.get("leng_long", "").strip()
    leng_short = record.get("leng_short", "").strip()
    etc_otc_code = record.get("etc_otc_code", "").strip()

    # 각인이 하나도 없으면 스킵
    if not print_front and not print_back:
        return None

    # 각인 텍스트 구성
    imprint_parts = []
    if print_front:
        imprint_parts.append(f"앞면 {print_front}")
    if print_back:
        imprint_parts.append(f"뒷면 {print_back}")
    imprint_str = ", ".join(imprint_parts)

    # 색상 구성
    color_parts = [c for c in [color1, color2] if c]
    color_str = "/".join(color_parts) if color_parts else ""

    # 크기 구성
    size_str = ""
    if leng_long and leng_short:
        size_str = f"{leng_long}x{leng_short}mm"
    elif leng_long:
        size_str = f"{leng_long}mm"

    # chunk_text 조합
    parts = [f"[{item_name}] 각인: {imprint_str}"]
    if color_str:
        parts.append(f"색상: {color_str}")
    if drug_shape:
        parts.append(f"모양: {drug_shape}")
    if size_str:
        parts.append(f"크기: {size_str}")

    chunk_text = " | ".join(parts)

    return {
        "item_seq": item_seq,
        "item_name": item_name,
        "etc_otc_code": etc_otc_code,
        "chunk_type": "imprint",
        "chunk_text": chunk_text,
        "metadata": record,
    }


# ── 임베딩 생성 ────────────────────────────────
MAX_CHARS = 6000  # 8192 토큰 안전 마진


def truncate_text(text: str) -> str:
    return text[:MAX_CHARS] if len(text) > MAX_CHARS else text


async def embed_texts(client: AsyncOpenAI, texts: list[str]) -> list[list[float]]:
    truncated = [truncate_text(t) for t in texts]
    response = await client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=truncated,
    )
    return [item.embedding for item in response.data]


# ── DB upsert ──────────────────────────────────
async def upsert_chunks(
    conn: asyncpg.Connection,
    chunks: list[dict],
    embeddings: list[list[float]],
) -> int:
    inserted = 0
    for chunk, embedding in zip(chunks, embeddings):
        vector_str = "[" + ",".join(str(v) for v in embedding) + "]"
        await conn.execute(
            """
            INSERT INTO drug_embeddings
                (item_seq, item_name, etc_otc_code, chunk_type, chunk_text, embedding, metadata)
            VALUES ($1, $2, $3, $4, $5, $6::vector, $7)
            ON CONFLICT (item_seq, chunk_type) DO UPDATE SET
                item_name    = EXCLUDED.item_name,
                etc_otc_code = EXCLUDED.etc_otc_code,
                chunk_text   = EXCLUDED.chunk_text,
                embedding    = EXCLUDED.embedding,
                metadata     = EXCLUDED.metadata,
                created_at   = NOW()
            """,
            chunk["item_seq"],
            chunk["item_name"],
            chunk["etc_otc_code"],
            chunk["chunk_type"],
            chunk["chunk_text"],
            vector_str,
            json.dumps(chunk["metadata"], ensure_ascii=False),
        )
        inserted += 1
    return inserted


# ── 기존 임베딩 item_seq 조회 ──────────────────
async def get_existing_item_seqs(
    conn: asyncpg.Connection,
    chunk_type: str | None = None,
) -> set[str]:
    if chunk_type:
        rows = await conn.fetch(
            "SELECT DISTINCT item_seq FROM drug_embeddings WHERE chunk_type = $1",
            chunk_type,
        )
    else:
        rows = await conn.fetch("SELECT DISTINCT item_seq FROM drug_embeddings")
    return {row["item_seq"] for row in rows}


# ── 배치 임베딩 + 저장 공통 함수 ──────────────
async def embed_and_save(
    all_chunks: list[dict],
    pool: asyncpg.Pool,
    client: AsyncOpenAI,
) -> int:
    total_inserted = 0
    for i in range(0, len(all_chunks), BATCH_SIZE):
        batch = all_chunks[i: i + BATCH_SIZE]
        texts = [c["chunk_text"] for c in batch]

        try:
            embeddings = await embed_texts(client, texts)
        except Exception as e:
            logger.error("임베딩 실패 (배치 %d): %s | 5초 후 재시도...", i // BATCH_SIZE, e)
            await asyncio.sleep(5)
            try:
                embeddings = await embed_texts(client, texts)
            except Exception as e2:
                logger.error("임베딩 재시도 실패 (배치 %d): %s | 건너뜀", i // BATCH_SIZE, e2)
                continue

        async with pool.acquire() as conn:
            inserted = await upsert_chunks(conn, batch, embeddings)
            total_inserted += inserted

        await asyncio.sleep(RATE_LIMIT_DELAY)

    return total_inserted


# ── 허가정보 파일 처리 ─────────────────────────
async def process_file(
    filepath: Path,
    pool: asyncpg.Pool,
    client: AsyncOpenAI,
    skip_existing: bool,
    existing_seqs: set[str],
) -> tuple[int, int]:
    """파일 1개 처리. (처리된 약품 수, 삽입된 청크 수) 반환"""
    all_chunks: list[dict] = []

    with open(filepath, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            item_seq = record.get("item_seq", "")
            if skip_existing and item_seq in existing_seqs:
                continue

            all_chunks.extend(build_chunks(record))

    if not all_chunks:
        return 0, 0

    drug_count = len({c["item_seq"] for c in all_chunks})
    total_inserted = await embed_and_save(all_chunks, pool, client)
    return drug_count, total_inserted


# ── 낱알식별 파일 처리 ─────────────────────────
async def process_imprint_file(
    pool: asyncpg.Pool,
    client: AsyncOpenAI,
    skip_existing: bool,
) -> tuple[int, int]:
    """imprint_data.jsonl 처리. (처리된 약품 수, 삽입된 청크 수) 반환"""
    if not IMPRINT_FILE.exists():
        logger.error(
            "낱알식별 파일이 없습니다: %s\n"
            "먼저 실행하세요: uv run python scripts/fetch_pill_imprint.py",
            IMPRINT_FILE,
        )
        return 0, 0

    # 기존 imprint 청크 조회
    existing_seqs: set[str] = set()
    if skip_existing:
        async with pool.acquire() as conn:
            existing_seqs = await get_existing_item_seqs(conn, chunk_type="imprint")
        logger.info("기존 imprint 임베딩: %d개 (건너뜀)", len(existing_seqs))

    all_chunks: list[dict] = []
    skipped = 0

    with open(IMPRINT_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            item_seq = record.get("item_seq", "")
            if skip_existing and item_seq in existing_seqs:
                skipped += 1
                continue

            chunk = build_imprint_chunk(record)
            if chunk:
                all_chunks.append(chunk)

    logger.info(
        "낱알식별 청크: %d개 생성 (각인 없음 제외, %d개 건너뜀)",
        len(all_chunks), skipped,
    )

    if not all_chunks:
        return 0, 0

    drug_count = len({c["item_seq"] for c in all_chunks})
    total_inserted = await embed_and_save(all_chunks, pool, client)
    return drug_count, total_inserted


# ── 메인 ──────────────────────────────────────
async def main(args: argparse.Namespace) -> None:
    db_cfg = get_db_config()
    logger.info("DB 연결: %s:%s/%s", db_cfg["host"], db_cfg["port"], db_cfg["database"])

    openai_key = os.getenv("OPENAI_API_KEY", "")
    if not openai_key:
        raise ValueError("OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")

    pool = await asyncpg.create_pool(**db_cfg, min_size=2, max_size=5)
    client = AsyncOpenAI(api_key=openai_key)
    start = time.time()

    # ── imprint 전용 모드 ──
    if args.imprint_only:
        logger.info("=== 낱알식별(imprint) 임베딩 시작 ===")
        drugs, chunks = await process_imprint_file(pool, client, args.skip_existing)
        logger.info("완료! 약품 %d개, 청크 %d개 | 소요시간: %.1f초", drugs, chunks, time.time() - start)
        await pool.close()
        return

    # ── 허가정보 임베딩 ──
    if args.files:
        files = [DRUG_JSON_DIR / f for f in args.files]
    else:
        # imprint_data.jsonl 제외하고 drugs_*.jsonl만 처리
        files = sorted(DRUG_JSON_DIR.glob("drugs_*.jsonl"))

    if not files:
        logger.error("처리할 jsonl 파일이 없습니다: %s", DRUG_JSON_DIR)
        await pool.close()
        return

    logger.info("=== 허가정보 임베딩 시작 (파일 %d개) ===", len(files))

    existing_seqs: set[str] = set()
    if args.skip_existing:
        async with pool.acquire() as conn:
            existing_seqs = await get_existing_item_seqs(conn)
        logger.info("기존 임베딩 약품 수: %d개 (건너뜀)", len(existing_seqs))

    total_drugs = 0
    total_chunks = 0
    failed_files: list[str] = []

    for idx, filepath in enumerate(files, 1):
        logger.info("[%d/%d] 처리 중: %s", idx, len(files), filepath.name)
        try:
            drugs, chunks = await process_file(
                filepath, pool, client, args.skip_existing, existing_seqs
            )
            total_drugs += drugs
            total_chunks += chunks
            logger.info("  → 약품 %d개, 청크 %d개 완료", drugs, chunks)
        except Exception as e:
            logger.error("  → 실패: %s | %s", filepath.name, e)
            failed_files.append(filepath.name)

    if failed_files:
        logger.warning("실패한 파일 %d개: %s", len(failed_files), ", ".join(failed_files))
        logger.warning(
            "재실행: uv run python scripts/embed_drugs.py --skip-existing --files %s",
            " ".join(failed_files),
        )

    elapsed = time.time() - start
    logger.info("완료! 총 약품 %d개, 청크 %d개 | 소요시간: %.1f초", total_drugs, total_chunks, elapsed)
    logger.info(
        "\n낱알식별 임베딩도 실행하려면:\n"
        "  1. uv run python scripts/fetch_pill_imprint.py\n"
        "  2. uv run python scripts/embed_drugs.py --imprint-only"
    )
    logger.info(
        "\n임베딩 완료 후 IVFFlat 인덱스 생성:\n"
        "  CREATE INDEX idx_drug_emb_ivfflat\n"
        "      ON drug_embeddings USING ivfflat (embedding vector_cosine_ops)\n"
        "      WITH (lists = 100);"
    )

    await pool.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="약품 데이터 pgvector 임베딩 스크립트")
    parser.add_argument(
        "--files", nargs="+", help="처리할 jsonl 파일명 (미지정 시 drugs_*.jsonl 전체)"
    )
    parser.add_argument(
        "--skip-existing", action="store_true",
        help="이미 임베딩된 item_seq는 건너뜀",
    )
    parser.add_argument(
        "--imprint-only", action="store_true",
        help="낱알식별(imprint) 청크만 임베딩 (imprint_data.jsonl 필요)",
    )
    asyncio.run(main(parser.parse_args()))
