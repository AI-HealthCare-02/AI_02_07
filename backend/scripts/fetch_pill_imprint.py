"""
scripts/fetch_pill_imprint.py
──────────────────────────────────────────────
식품의약품안전처 의약품 낱알식별 정보 수집 스크립트

수집 필드 (식별에 필요한 것만):
  ITEM_SEQ, ITEM_NAME, PRINT_FRONT, PRINT_BACK,
  DRUG_SHAPE, COLOR_CLASS1, COLOR_CLASS2,
  LENG_LONG, LENG_SHORT, CLASS_NAME, ETC_OTC_NAME

제외 조건:
  - PRINT_FRONT, PRINT_BACK 둘 다 없는 항목 (각인 없으면 식별 불가)
  - (PRINT_FRONT, PRINT_BACK, DRUG_SHAPE, COLOR_CLASS1) 동일한 중복
    → ITEM_NAME 가장 짧은 대표 1개만 유지

실행 방법:
  PUBLIC_DATA_API_KEY=your-key uv run python scripts/fetch_pill_imprint.py

  # 특정 약품명 테스트
  PUBLIC_DATA_API_KEY=your-key uv run python scripts/fetch_pill_imprint.py --item-name "타이레놀"

  # 최대 수집 건수 지정
  PUBLIC_DATA_API_KEY=your-key uv run python scripts/fetch_pill_imprint.py --max-rows 100000
──────────────────────────────────────────────
"""

import argparse
import asyncio
import json
import logging
import os
import time
from pathlib import Path

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

API_BASE = "https://apis.data.go.kr/1471000/MdcinGrnIdntfcInfoService03"
ENDPOINT = "getMdcinGrnIdntfcInfoList03"
PAGE_SIZE = 100
REQUEST_DELAY = 0.3
OUTPUT_FILE = Path(__file__).parent.parent / "drug_json" / "imprint_data.jsonl"


def get_api_key() -> str:
    from urllib.parse import unquote

    key = os.getenv("PUBLIC_DATA_API_KEY", "")
    if not key:
        # .prod.env 또는 .local.env에서 직접 읽기 시도
        env_paths = [
            Path(__file__).parent.parent / "envs" / ".prod.env",
            Path(__file__).parent.parent / "envs" / ".local.env",
        ]
        for env_path in env_paths:
            if env_path.exists():
                with open(env_path) as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("PUBLIC_DATA_API_KEY="):
                            key = line.split("=", 1)[1].strip()
                            break
            if key:
                break
    if not key:
        raise ValueError("PUBLIC_DATA_API_KEY 환경변수가 설정되지 않았습니다.")
    # URL 인코딩된 키는 디코딩 (이중 인코딩 방지)
    return unquote(key)


def parse_item(raw: dict) -> dict | None:
    """
    필요한 필드만 추출. 각인 없으면 None 반환.
    """
    print_front = str(raw.get("PRINT_FRONT") or "").strip()
    print_back = str(raw.get("PRINT_BACK") or "").strip()

    # 각인 없으면 식별 불가 → 제외
    if not print_front and not print_back:
        return None

    item_seq = str(raw.get("ITEM_SEQ") or "").strip()
    if not item_seq:
        return None

    return {
        "item_seq": item_seq,
        "item_name": str(raw.get("ITEM_NAME") or "").strip(),
        "print_front": print_front,
        "print_back": print_back,
        "drug_shape": str(raw.get("DRUG_SHAPE") or "").strip(),
        "color_class1": str(raw.get("COLOR_CLASS1") or "").strip(),
        "color_class2": str(raw.get("COLOR_CLASS2") or "").strip(),
        "leng_long": str(raw.get("LENG_LONG") or "").strip(),
        "leng_short": str(raw.get("LENG_SHORT") or "").strip(),
        "class_name": str(raw.get("CLASS_NAME") or "").strip(),
        "etc_otc_name": str(raw.get("ETC_OTC_NAME") or "").strip(),
    }


def dedup_items(items: list[dict]) -> list[dict]:
    """
    (print_front, print_back, drug_shape, color_class1) 동일한 중복 제거.
    같은 키에서 item_name이 가장 짧은 대표 1개만 유지.
    """
    seen: dict[tuple, dict] = {}
    for item in items:
        key = (
            item["print_front"].upper(),
            item["print_back"].upper(),
            item["drug_shape"],
            item["color_class1"],
        )
        if key not in seen:
            seen[key] = item
        else:
            # 더 짧은 이름(대표 제품명)으로 교체
            if len(item["item_name"]) < len(seen[key]["item_name"]):
                seen[key] = item
    return list(seen.values())


async def fetch_page(
    client: httpx.AsyncClient,
    api_key: str,
    page_no: int,
    item_name: str | None = None,
) -> tuple[list[dict], int]:
    params = {
        "serviceKey": api_key,
        "pageNo": page_no,
        "numOfRows": PAGE_SIZE,
        "type": "json",
    }
    if item_name:
        params["item_name"] = item_name

    resp = await client.get(f"{API_BASE}/{ENDPOINT}", params=params, timeout=30.0)
    resp.raise_for_status()

    data = resp.json()
    body = data.get("body", {})
    total_count = int(body.get("totalCount", 0))
    items = body.get("items", []) or []
    return items, total_count


async def main(args: argparse.Namespace) -> None:
    api_key = get_api_key()
    logger.info("낱알식별 정보 수집 시작")

    all_items: list[dict] = []
    start = time.time()

    async with httpx.AsyncClient() as client:
        first_items, total_count = await fetch_page(client, api_key, 1, args.item_name)

        max_rows = min(total_count, args.max_rows)
        total_pages = (max_rows + PAGE_SIZE - 1) // PAGE_SIZE
        logger.info("전체 %d건 중 최대 %d건 수집 (%d페이지)", total_count, max_rows, total_pages)

        # 1페이지 처리
        for raw in first_items:
            item = parse_item(raw)
            if item:
                all_items.append(item)

        # 2페이지~
        for page_no in range(2, total_pages + 1):
            try:
                items, _ = await fetch_page(client, api_key, page_no, args.item_name)
                for raw in items:
                    item = parse_item(raw)
                    if item:
                        all_items.append(item)

                if page_no % 20 == 0:
                    logger.info("[%d/%d] 수집 중 (각인 있는 항목: %d건)", page_no, total_pages, len(all_items))

                await asyncio.sleep(REQUEST_DELAY)

            except httpx.HTTPError as e:
                logger.error("페이지 %d 오류: %s | 5초 후 재시도...", page_no, e)
                await asyncio.sleep(5)
                try:
                    items, _ = await fetch_page(client, api_key, page_no, args.item_name)
                    for raw in items:
                        item = parse_item(raw)
                        if item:
                            all_items.append(item)
                except Exception as e2:
                    logger.error("페이지 %d 재시도 실패: %s | 건너뜀", page_no, e2)

    # 중복 제거
    before = len(all_items)
    all_items = dedup_items(all_items)
    after = len(all_items)
    logger.info("중복 제거: %d건 → %d건 (제거: %d건)", before, after, before - after)

    # 저장
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for item in all_items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    elapsed = time.time() - start
    logger.info("완료! %d건 저장 | 소요시간: %.1f초", after, elapsed)
    logger.info("저장 위치: %s", OUTPUT_FILE)
    logger.info("")
    logger.info("다음 단계: imprint 임베딩 실행")
    logger.info("  OPENAI_API_KEY=sk-... DB_PORT=15432 uv run python scripts/embed_drugs.py --imprint-only --skip-existing")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="낱알식별 정보 수집 스크립트")
    parser.add_argument("--max-rows", type=int, default=50000, help="최대 수집 건수 (기본: 50000)")
    parser.add_argument("--item-name", type=str, default=None, help="특정 약품명 필터 (테스트용)")
    asyncio.run(main(parser.parse_args()))
