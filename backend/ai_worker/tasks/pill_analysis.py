# ai_worker/tasks/pill_analysis.py
# ──────────────────────────────────────────────
# 알약 분석 작업 핸들러 — 안은지 담당
#
# [3단계 흐름]
#
# 1단계: Clova OCR (각인 텍스트 추출) +
#        GPT Vision detail:low (색상/모양만 추출)
#
# 2단계: imprint RAG (텍스트만, 이미지 없음)
#   → 각인+색상+모양으로 pgvector 검색
#   → 매칭 실패 시 각인 정보만 저장
#
# 3단계: 허가정보 DB 직접 조회 (GPT 재호출 없음)
#   → item_seq로 efficacy/caution/ingredient 조회
# ──────────────────────────────────────────────

import base64
import io
import json
import uuid

import asyncpg
import httpx
from PIL import Image

try:
    from langfuse.openai import AsyncOpenAI
except ImportError:
    from openai import AsyncOpenAI  # type: ignore[assignment]

from ai_worker.core.config import get_worker_settings
from ai_worker.core.logger import setup_logger
from ai_worker.core.s3_client import download_file_from_s3

logger = setup_logger("task.pill_analysis")
settings = get_worker_settings()

MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
TARGET_SIZE = 1024
IMPRINT_SIMILARITY_THRESHOLD = 0.45


# ── 이미지 전처리 ──────────────────────────────
def preprocess_image(image_bytes: bytes) -> tuple[str, bytes]:
    """리사이즈된 이미지의 (base64, bytes) 반환."""
    if len(image_bytes) > MAX_IMAGE_SIZE:
        raise ValueError(f"이미지 용량이 5MB를 초과합니다: {len(image_bytes) / 1024 / 1024:.1f}MB")

    img = Image.open(io.BytesIO(image_bytes))

    try:
        from PIL import ImageOps

        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    if img.mode != "RGB":
        img = img.convert("RGB")

    w, h = img.size
    if max(w, h) > TARGET_SIZE:
        ratio = TARGET_SIZE / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    img_bytes = buf.getvalue()
    return base64.b64encode(img_bytes).decode("utf-8"), img_bytes


# ── Clova OCR - 각인 텍스트 추출 ──────────────
async def extract_imprint_ocr(image_bytes: bytes) -> str | None:
    """Clova OCR로 이미지에서 텍스트를 추출해 각인 문자열 반환."""
    if not settings.OCR_INVOKE_URL or not settings.OCR_SECRET_KEY:
        return None

    payload = {
        "version": "V2",
        "requestId": str(uuid.uuid4()),
        "timestamp": 0,
        "images": [{"format": "jpg", "name": "pill", "data": base64.b64encode(image_bytes).decode()}],
    }
    headers = {"X-OCR-SECRET": settings.OCR_SECRET_KEY, "Content-Type": "application/json"}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(settings.OCR_INVOKE_URL, json=payload, headers=headers)
            resp.raise_for_status()
            fields = resp.json()["images"][0].get("fields", [])
            texts = [f["inferText"] for f in fields if f.get("inferText")]
            result = " ".join(texts).strip().upper()
            logger.info("Clova OCR 결과: %s", result)
            return result or None
    except Exception as e:
        logger.warning("Clova OCR 실패 (무시): %s", e)
        return None


# ── 1단계: GPT Vision - 색상/모양만 추출 ───────
async def extract_pill_features(
    client: AsyncOpenAI,
    image_b64_list: list[str],
    ocr_texts: list[str | None],
    model: str,
) -> dict:
    """
    OCR로 추출한 각인 텍스트를 힌트로 제공하고,
    GPT Vision은 색상/모양만 판단.
    """
    image_contents = []
    for i, b64 in enumerate(image_b64_list):
        face = "앞면" if i == 0 else "뒷면"
        ocr_hint = f" (OCR 각인: {ocr_texts[i]})" if i < len(ocr_texts) and ocr_texts[i] else ""
        image_contents.append(
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "low"}}
        )
        image_contents.append({"type": "text", "text": f"위 이미지는 알약의 {face}입니다.{ocr_hint}"})

    ocr_front = ocr_texts[0] if ocr_texts else None
    ocr_back = ocr_texts[1] if len(ocr_texts) > 1 else None

    prompt = f"""알약 이미지를 보고 아래 JSON만 출력하세요. 다른 말은 하지 마세요.

각인 문자는 OCR로 이미 추출되었습니다. print_front/print_back은 아래 값을 그대로 사용하세요.
- 앞면 OCR: {ocr_front or "없음"}
- 뒷면 OCR: {ocr_back or "없음"}

이미지에서는 색상과 모양만 판단하세요.

{{
  "is_pill": true,
  "print_front": "앞면 OCR 결과 그대로 (없으면 null)",
  "print_back": "뒷면 OCR 결과 그대로 (없으면 null)",
  "color": "색상 (예: 하양, 노랑, 분홍)",
  "shape": "모양 (예: 원형, 타원형, 장방형)"
}}

알약이 아닌 이미지면 is_pill을 false로 설정하세요."""

    contents = image_contents + [{"type": "text", "text": prompt}]

    try:
        response = await client.chat.completions.create(
            model=model,
            max_tokens=150,
            temperature=0,
            messages=[{"role": "user", "content": contents}],
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        return json.loads(raw)
    except Exception as e:
        logger.warning("1단계 특징 추출 실패: %s", e)
        return {"is_pill": False}


# ── 2단계: imprint RAG - 약품 특정 ────────────
async def find_drug_by_imprint(
    conn: asyncpg.Connection,
    client: AsyncOpenAI,
    features: dict,
) -> dict | None:
    parts = []
    if features.get("print_front"):
        parts.append(features["print_front"])
    if features.get("print_back"):
        parts.append(features["print_back"])
    if features.get("color"):
        parts.append(features["color"])
    if features.get("shape"):
        parts.append(features["shape"])

    if not parts:
        return None

    query = " ".join(parts)
    logger.info("2단계 imprint 검색 쿼리: %s", query)

    try:
        emb_response = await client.embeddings.create(
            model="text-embedding-3-small",
            input=query,
        )
        vector_str = "[" + ",".join(str(v) for v in emb_response.data[0].embedding) + "]"

        rows = await conn.fetch(
            """
            SELECT item_seq, item_name, chunk_text,
                   1 - (embedding <=> $1::vector) AS similarity
            FROM drug_embeddings
            WHERE chunk_type = 'imprint'
              AND embedding IS NOT NULL
            ORDER BY embedding <=> $1::vector
            LIMIT 1
            """,
            vector_str,
        )

        if not rows:
            logger.info("imprint 데이터 없음 (임베딩 미구축)")
            return None

        best = rows[0]
        similarity = float(best["similarity"])

        if similarity < IMPRINT_SIMILARITY_THRESHOLD:
            logger.info(
                "imprint 매칭 실패 - 유사도 낮음 (%.3f < %.2f): %s",
                similarity,
                IMPRINT_SIMILARITY_THRESHOLD,
                query,
            )
            return None

        logger.info(
            "imprint 매칭 성공: '%s' → '%s' (유사도: %.3f)",
            query,
            best["item_name"],
            similarity,
        )
        return {
            "item_seq": best["item_seq"],
            "item_name": best["item_name"],
            "similarity": similarity,
        }

    except Exception as e:
        logger.warning("2단계 imprint 검색 실패 (무시): %s", e)
        return None


# ── 3단계: 허가정보 DB 직접 조회 ──────────────
async def fetch_drug_info_from_db(
    conn: asyncpg.Connection,
    item_seq: str,
) -> dict:
    rows = await conn.fetch(
        """
        SELECT chunk_type, chunk_text
        FROM drug_embeddings
        WHERE item_seq = $1
          AND chunk_type IN ('efficacy', 'caution', 'ingredient')
        """,
        item_seq,
    )

    db_info: dict[str, str] = {}
    for r in rows:
        text = r["chunk_text"]
        if ": " in text:
            content = text.split(": ", 1)[1].strip()
            db_info[r["chunk_type"]] = content

    return db_info


# ── ai_settings 조회 ───────────────────────────
async def get_ai_model(conn: asyncpg.Connection) -> str:
    row = await conn.fetchrow("SELECT api_model FROM ai_settings WHERE is_active = TRUE LIMIT 1")
    return row["api_model"] if row else "gpt-4o-mini"


# ── DB 저장 ────────────────────────────────────
async def save_analysis_result(
    conn: asyncpg.Connection,
    user_id: int,
    file_id: int,
    result: dict,
) -> int:
    row = await conn.fetchrow(
        """
        INSERT INTO pill_analysis_history (
            user_id, file_id, product_name, active_ingredients,
            efficacy, usage_method, warning, caution,
            interactions, side_effects, storage_method, gpt_model_version
        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
        RETURNING analysis_id
        """,
        user_id,
        file_id,
        result.get("product_name"),
        result.get("active_ingredients"),
        result.get("efficacy"),
        result.get("usage_method"),
        result.get("warning"),
        result.get("caution"),
        result.get("interactions"),
        result.get("side_effects"),
        result.get("storage_method"),
        result.get("gpt_model_version"),
    )
    return row["analysis_id"]


# ── 메인 태스크 핸들러 ─────────────────────────
async def process_pill_analysis(task_data: dict) -> dict:
    payload = task_data["payload"]
    user_id: int = payload["user_id"]
    file_id: int = payload["file_id"]
    s3_keys: list[str] = payload["s3_keys"]

    logger.info("알약 분석 시작 | user_id=%s, file_id=%s", user_id, file_id)

    conn = await asyncpg.connect(settings.database_url.replace("asyncpg://", "postgresql://"))

    try:
        model = await get_ai_model(conn)
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        # 이미지 다운로드 + 전처리
        image_b64_list: list[str] = []
        image_bytes_list: list[bytes] = []
        for s3_key in s3_keys[:2]:
            raw_bytes = download_file_from_s3(s3_key)
            b64, processed_bytes = preprocess_image(raw_bytes)
            image_b64_list.append(b64)
            image_bytes_list.append(processed_bytes)

        if not image_b64_list:
            raise ValueError("처리할 이미지가 없습니다.")

        # ── Clova OCR - 각인 텍스트 추출 ──
        import asyncio

        ocr_texts: list[str | None] = list(await asyncio.gather(*[extract_imprint_ocr(b) for b in image_bytes_list]))
        logger.info(
            "OCR 결과: front=%s, back=%s",
            ocr_texts[0] if ocr_texts else None,
            ocr_texts[1] if len(ocr_texts) > 1 else None,
        )

        # ── 1단계: GPT Vision - 색상/모양 추출 ──
        features = await extract_pill_features(client, image_b64_list, ocr_texts, model)
        logger.info("1단계 완료: %s", features)

        if not features.get("is_pill", True):
            logger.info("알약 이미지가 아님 → 식별 불가 반환")
            result = {"product_name": "알약 이미지가 아닙니다", "gpt_model_version": model}
            analysis_id = await save_analysis_result(conn, user_id, file_id, result)
            return {"analysis_id": analysis_id, "product_name": result["product_name"], "result": result}

        # ── 2단계: imprint RAG ──
        matched_drug = await find_drug_by_imprint(conn, client, features)

        if matched_drug is None:
            logger.info("2단계 매칭 실패 → 각인 정보만 저장")
            parts = [v for v in [features.get("print_front"), features.get("print_back")] if v]
            product_name = f"각인: {', '.join(parts)} (DB 미매칭)" if parts else "식별 불가"
            result = {"product_name": product_name, "gpt_model_version": model}
            analysis_id = await save_analysis_result(conn, user_id, file_id, result)
            return {"analysis_id": analysis_id, "product_name": result["product_name"], "result": result}

        # ── 3단계: 허가정보 DB 직접 조회 ──
        db_info = await fetch_drug_info_from_db(conn, matched_drug["item_seq"])
        logger.info("3단계 완료: item_seq=%s, 조회 필드=%s", matched_drug["item_seq"], list(db_info.keys()))

        result = {
            "product_name": matched_drug["item_name"],
            "active_ingredients": db_info.get("ingredient"),
            "efficacy": db_info.get("efficacy"),
            "usage_method": None,
            "warning": None,
            "caution": db_info.get("caution"),
            "interactions": None,
            "side_effects": None,
            "storage_method": None,
            "gpt_model_version": model,
        }

        analysis_id = await save_analysis_result(conn, user_id, file_id, result)
        logger.info("분석 완료: analysis_id=%s, product_name=%s", analysis_id, result["product_name"])

        return {"analysis_id": analysis_id, "product_name": result["product_name"], "result": result}

    finally:
        await conn.close()
