"""
scripts/sync_drug_data.py
──────────────────────────────────────────────
공공데이터 API 증분 동기화 스크립트

사용:
  # dry-run (DB 변경 없음)
  uv run python scripts/sync_drug_data.py --dry-run

  # 최근 7일 변경분 동기화
  uv run python scripts/sync_drug_data.py --since-days 7

  # 특정 날짜 이후 변경분
  uv run python scripts/sync_drug_data.py --since-date 20250101

  # 특정 item_seq만 강제 업데이트
  uv run python scripts/sync_drug_data.py --item-seq 200003092
──────────────────────────────────────────────
"""

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import unquote

import asyncpg
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai_worker.tasks.imprint_parser import parse_imprint_chunk

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── API 설정 ──────────────────────────────────────────────────
PRMSN_URL = "https://apis.data.go.kr/1471000/DrugPrdtPrmsnInfoService07/getDrugPrdtPrmsnDtlInq06"
IDNTFC_URL = "https://apis.data.go.kr/1471000/MdcinGrnIdntfcInfoService03/getMdcinGrnIdntfcInfoList03"

SERVICE_KEY = unquote(os.getenv("PUBLIC_DATA_SERVICE_KEY", ""))


def get_db_config() -> dict:
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "15432")),
        "user": os.getenv("DB_USER", "healthguide"),
        "password": os.getenv("DB_PASSWORD", "healthguide_local_pw"),
        "database": os.getenv("DB_NAME", "healthguide_db"),
    }


# ── HTML 정제 ─────────────────────────────────────────────────
def _clean_html(text: str | None) -> str:
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)
    return text.replace("&nbsp;", " ").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&").strip()


def _clean_ingr(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\[M\d+\]", "", text).strip()


def parse_doc_xml(xml_str: str, doc_type: str = "") -> dict:
    if not xml_str or not xml_str.strip():
        return {}
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError:
        return {}
    result = {}
    nb_idx = 1
    for article in root.findall(".//ARTICLE"):
        title = article.get("title", "").strip()
        if not title:
            if doc_type == "EE":
                title = "효능효과"
            else:
                continue
        paragraphs = []
        for p in article.findall("PARAGRAPH"):
            if p.get("tagName") == "table":
                continue
            cleaned = _clean_html(p.text or "")
            if cleaned:
                paragraphs.append(cleaned)
        if paragraphs:
            if doc_type == "NB":
                stripped = re.sub(r"^\d+\.\s*", "", title)
                key = f"{nb_idx}. {stripped}"
                nb_idx += 1
            else:
                key = title
            result[key] = " ".join(paragraphs)
    return result


_NON_ORAL_KEYWORDS = [
    "주사", "연고", "크림", "패치", "좌제", "좌약",
    "점안", "점이", "점비", "흡입", "에어로졸",
    "외용", "도포", "로션", "스프레이",
    "안약", "이약", "비약", "관장", "질정",
]


def is_oral_drug(item: dict) -> bool:
    name = (item.get("ITEM_NAME") or "").lower()
    chart = (item.get("CHART") or "").lower()
    return not any(kw in name + " " + chart for kw in _NON_ORAL_KEYWORDS)


# ── API 호출 ──────────────────────────────────────────────────
async def fetch_prmsn_page(
    client: httpx.AsyncClient,
    page_no: int,
    num_of_rows: int = 100,
    change_date: str | None = None,
    item_seq: str | None = None,
) -> tuple[int, list[dict]]:
    """의약품 제품허가 상세정보 API 호출."""
    params: dict = {
        "serviceKey": SERVICE_KEY,
        "pageNo": page_no,
        "numOfRows": num_of_rows,
        "type": "json",
    }
    if change_date:
        params["change_date"] = change_date
    if item_seq:
        params["item_seq"] = item_seq

    for attempt in range(1, 4):
        try:
            resp = await client.get(PRMSN_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            body = data.get("body", {})
            total = int(body.get("totalCount", 0))
            items = body.get("items", [])
            if isinstance(items, dict):
                items = items.get("item", [])
            if isinstance(items, dict):
                items = [items]
            return total, items or []
        except Exception as e:
            wait = attempt * 3
            logger.warning("PRMSN API 재시도 %d/3: %s → %d초 대기", attempt, e, wait)
            await asyncio.sleep(wait)
    return 0, []


async def fetch_idntfc_page(
    client: httpx.AsyncClient,
    page_no: int,
    num_of_rows: int = 100,
    change_date: str | None = None,
    item_seq: str | None = None,
) -> tuple[int, list[dict]]:
    """의약품 낱알식별 정보 API 호출."""
    params: dict = {
        "serviceKey": SERVICE_KEY,
        "pageNo": page_no,
        "numOfRows": num_of_rows,
        "type": "json",
    }
    if change_date:
        params["change_date"] = change_date
    if item_seq:
        params["item_seq"] = item_seq

    for attempt in range(1, 4):
        try:
            resp = await client.get(IDNTFC_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            body = data.get("body", {})
            total = int(body.get("totalCount", 0))
            items = body.get("items", [])
            if isinstance(items, dict):
                items = items.get("item", [])
            if isinstance(items, dict):
                items = [items]
            return total, items or []
        except Exception as e:
            wait = attempt * 3
            logger.warning("IDNTFC API 재시도 %d/3: %s → %d초 대기", attempt, e, wait)
            await asyncio.sleep(wait)
    return 0, []


# ── chunk 생성 ────────────────────────────────────────────────
def build_chunks_from_prmsn(item: dict) -> list[dict]:
    """허가정보 API → efficacy/caution chunk 생성."""
    chunks = []
    item_seq = item.get("ITEM_SEQ", "")
    item_name = item.get("ITEM_NAME", "")
    etc_otc = item.get("ETC_OTC_CODE", "")

    efficacy = parse_doc_xml(item.get("EE_DOC_DATA", ""), doc_type="EE").get("효능효과", "")
    if efficacy:
        chunks.append({
            "item_seq": item_seq,
            "item_name": item_name,
            "etc_otc_code": etc_otc,
            "chunk_type": "efficacy",
            "chunk_text": f"효능효과: {efficacy}",
        })

    caution_dict = parse_doc_xml(item.get("NB_DOC_DATA", ""), doc_type="NB")
    caution_text = " ".join(caution_dict.values())
    if caution_text:
        chunks.append({
            "item_seq": item_seq,
            "item_name": item_name,
            "etc_otc_code": etc_otc,
            "chunk_type": "caution",
            "chunk_text": f"주의사항: {caution_text}",
        })

    ingr = _clean_ingr(item.get("MAIN_ITEM_INGR", ""))
    if ingr:
        chunks.append({
            "item_seq": item_seq,
            "item_name": item_name,
            "etc_otc_code": etc_otc,
            "chunk_type": "ingredient",
            "chunk_text": f"성분: {ingr}",
        })

    return chunks


def build_imprint_chunk_from_idntfc(item: dict) -> dict | None:
    """낱알식별 API → imprint chunk 생성."""
    item_seq = item.get("ITEM_SEQ", "")
    item_name = item.get("ITEM_NAME", "")
    etc_otc = item.get("ETC_OTC_CODE", "")

    front = item.get("PRINT_FRONT", "") or ""
    back = item.get("PRINT_BACK", "") or ""
    color = item.get("COLOR_CLASS1", "") or ""
    shape = item.get("DRUG_SHAPE", "") or ""
    size_long = item.get("LENG_LONG", "") or ""
    size_short = item.get("LENG_SHORT", "") or ""

    imprint_parts = []
    if front:
        imprint_parts.append(f"앞면 {front}")
    if back:
        imprint_parts.append(f"뒷면 {back}")
    imprint_str = ", ".join(imprint_parts) if imprint_parts else "없음"

    size_str = ""
    if size_long and size_short:
        size_str = f" | 크기: {size_long}x{size_short}mm"
    elif size_long:
        size_str = f" | 크기: {size_long}mm"

    chunk_text = f"[{item_name}] 각인: {imprint_str} | 색상: {color} | 모양: {shape}{size_str}"

    return {
        "item_seq": item_seq,
        "item_name": item_name,
        "etc_otc_code": etc_otc,
        "chunk_type": "imprint",
        "chunk_text": chunk_text,
    }


# ── DB upsert ─────────────────────────────────────────────────
async def upsert_chunk(
    conn: asyncpg.Connection,
    chunk: dict,
    dry_run: bool = False,
) -> str:
    """
    item_seq + chunk_type 기준 upsert.
    반환: 'inserted' | 'updated' | 'skipped' | 'dry_run'
    """
    existing = await conn.fetchrow(
        "SELECT id, chunk_text FROM drug_embeddings WHERE item_seq = $1 AND chunk_type = $2",
        chunk["item_seq"],
        chunk["chunk_type"],
    )

    if existing and existing["chunk_text"] == chunk["chunk_text"]:
        return "skipped"

    if dry_run:
        action = "would_insert" if not existing else "would_update"
        logger.info("[DRY-RUN] %s: %s / %s", action, chunk["item_seq"], chunk["chunk_type"])
        return "dry_run"

    metadata = None
    if chunk["chunk_type"] == "imprint":
        parsed = parse_imprint_chunk(chunk["chunk_text"])
        if parsed:
            metadata = json.dumps(parsed, ensure_ascii=False)

    if existing:
        await conn.execute(
            """
            UPDATE drug_embeddings
            SET item_name = $1, chunk_text = $2, metadata = $3::jsonb, embedding = NULL
            WHERE item_seq = $4 AND chunk_type = $5
            """,
            chunk["item_name"],
            chunk["chunk_text"],
            metadata,
            chunk["item_seq"],
            chunk["chunk_type"],
        )
        return "updated"
    else:
        await conn.execute(
            """
            INSERT INTO drug_embeddings (item_seq, item_name, etc_otc_code, chunk_type, chunk_text, metadata)
            VALUES ($1, $2, $3, $4, $5, $6::jsonb)
            """,
            chunk["item_seq"],
            chunk["item_name"],
            chunk["etc_otc_code"],
            chunk["chunk_type"],
            chunk["chunk_text"],
            metadata,
        )
        return "inserted"


async def record_sync_log(
    conn: asyncpg.Connection,
    sync_type: str,
    since_date: str | None,
    inserted: int,
    updated: int,
    skipped: int,
    failed: int,
    dry_run: bool,
) -> None:
    """동기화 이력 기록 (drug_sync_log 테이블)."""
    try:
        await conn.execute(
            """
            INSERT INTO drug_sync_log
                (sync_type, since_date, inserted, updated, skipped, failed, dry_run, synced_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
            """,
            sync_type,
            since_date,
            inserted,
            updated,
            skipped,
            failed,
            dry_run,
        )
    except Exception as e:
        logger.warning("동기화 이력 기록 실패 (무시): %s", e)


# ── 메인 동기화 로직 ──────────────────────────────────────────
async def sync(
    since_date: str | None = None,
    item_seq: str | None = None,
    dry_run: bool = False,
    page_size: int = 100,
) -> dict:
    if not SERVICE_KEY:
        raise ValueError("PUBLIC_DATA_SERVICE_KEY 환경변수가 설정되지 않았습니다.")

    pool = await asyncpg.create_pool(**get_db_config(), min_size=1, max_size=3)
    stats = {"inserted": 0, "updated": 0, "skipped": 0, "failed": 0}

    async with httpx.AsyncClient() as client:
        # ── 1. 허가정보 API (efficacy/caution/ingredient) ──
        logger.info("=== 허가정보 API 동기화 시작 (since=%s) ===", since_date)
        total, _ = await fetch_prmsn_page(client, 1, 1, since_date, item_seq)
        total_pages = (total + page_size - 1) // page_size
        logger.info("허가정보 총 %d건 (%d페이지)", total, total_pages)

        for page in range(1, total_pages + 1):
            _, items = await fetch_prmsn_page(client, page, page_size, since_date, item_seq)
            for item in items:
                if not is_oral_drug(item):
                    continue
                try:
                    chunks = build_chunks_from_prmsn(item)
                    async with pool.acquire() as conn:
                        for chunk in chunks:
                            result = await upsert_chunk(conn, chunk, dry_run)
                            stats[result if result in stats else "skipped"] += 1
                except Exception as e:
                    logger.error("허가정보 처리 실패 item_seq=%s: %s", item.get("ITEM_SEQ"), e)
                    stats["failed"] += 1
            logger.info("허가정보 %d/%d 페이지 완료", page, total_pages)

        # ── 2. 낱알식별 API (imprint) ──
        logger.info("=== 낱알식별 API 동기화 시작 (since=%s) ===", since_date)
        total2, _ = await fetch_idntfc_page(client, 1, 1, since_date, item_seq)
        total_pages2 = (total2 + page_size - 1) // page_size
        logger.info("낱알식별 총 %d건 (%d페이지)", total2, total_pages2)

        for page in range(1, total_pages2 + 1):
            _, items = await fetch_idntfc_page(client, page, page_size, since_date, item_seq)
            for item in items:
                try:
                    chunk = build_imprint_chunk_from_idntfc(item)
                    if chunk:
                        async with pool.acquire() as conn:
                            result = await upsert_chunk(conn, chunk, dry_run)
                            stats[result if result in stats else "skipped"] += 1
                except Exception as e:
                    logger.error("낱알식별 처리 실패 item_seq=%s: %s", item.get("ITEM_SEQ"), e)
                    stats["failed"] += 1
            logger.info("낱알식별 %d/%d 페이지 완료", page, total_pages2)

    # ── 동기화 이력 기록 ──
    async with pool.acquire() as conn:
        await record_sync_log(
            conn,
            sync_type="incremental" if since_date else "full",
            since_date=since_date,
            dry_run=dry_run,
            **{k: stats[k] for k in ("inserted", "updated", "skipped", "failed")},
        )

    await pool.close()

    logger.info(
        "동기화 완료 | inserted=%d updated=%d skipped=%d failed=%d dry_run=%s",
        stats["inserted"], stats["updated"], stats["skipped"], stats["failed"], dry_run,
    )
    return stats


# ── CLI ───────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="공공데이터 의약품 증분 동기화")
    parser.add_argument("--dry-run", action="store_true", help="DB 변경 없이 시뮬레이션")
    parser.add_argument("--since-days", type=int, help="최근 N일 변경분 동기화")
    parser.add_argument("--since-date", type=str, help="YYYYMMDD 이후 변경분 동기화")
    parser.add_argument("--item-seq", type=str, help="특정 item_seq만 동기화")
    parser.add_argument("--page-size", type=int, default=100, help="API 페이지 크기")
    args = parser.parse_args()

    since = None
    if args.since_days:
        since = (date.today() - timedelta(days=args.since_days)).strftime("%Y%m%d")
    elif args.since_date:
        since = args.since_date

    asyncio.run(sync(
        since_date=since,
        item_seq=args.item_seq,
        dry_run=args.dry_run,
        page_size=args.page_size,
    ))
