# ai_worker/tasks/pill_analysis.py
# ──────────────────────────────────────────────
# 알약 분석 작업 핸들러 — 안은지 담당
#
# [개선된 3단계 흐름]
#
# 1단계: GPT Vision (detail:low, 이미지 사용)
#   → 각인/색상/모양만 추출 (약품정보 생성 안 함)
#   → 각인 없으면 "알약 식별 불가" 반환
#
# 2단계: imprint RAG (텍스트만, 이미지 없음)
#   → 각인+색상+모양으로 pgvector 검색
#   → 매칭 실패 시 GPT 추론 결과만 반환
#
# 3단계: 허가정보 DB 직접 조회 (텍스트만, GPT 재호출 없음)
#   → item_seq로 efficacy/caution/ingredient 조회
#   → 결과 조합 후 저장
#
# 토큰: ~270 (1단계만 GPT 사용, 2~3단계는 DB 조회)
# ──────────────────────────────────────────────

import base64
import io
import json

import asyncpg
from openai import AsyncOpenAI
from PIL import Image

from ai_worker.core.config import get_worker_settings
from ai_worker.core.logger import setup_logger
from ai_worker.core.s3_client import download_file_from_s3

logger = setup_logger("task.pill_analysis")
settings = get_worker_settings()

MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
TARGET_SIZE = 1024
IMPRINT_SIMILARITY_THRESHOLD = 0.5  # imprint 매칭 최소 유사도


# ── 이미지 전처리 ──────────────────────────────
def preprocess_image(image_bytes: bytes) -> str:
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

    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=90)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


# ── 1단계: GPT Vision - 각인/색상/모양만 추출 ──
async def extract_pill_features(
    client: AsyncOpenAI,
    image_b64_list: list[str],
    model: str,
) -> dict:
    """
    이미지에서 각인/색상/모양만 추출. 약품정보는 생성하지 않음.
    detail:low 사용 → 이미지 2장 약 170 토큰.

    반환:
        {
            "print_front": "IH AL" | null,
            "print_back": null,
            "color": "하양",
            "shape": "장방형",
            "is_pill": true  ← 알약 여부
        }
    """
    image_contents = []
    for i, b64 in enumerate(image_b64_list):
        image_contents.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{b64}",
                "detail": "low",  # 고정 85 토큰/장
            },
        })
        image_contents.append({
            "type": "text",
            "text": f"위 이미지는 알약의 {'앞면' if i == 0 else '뒷면'}입니다.",
        })

    prompt = """알약 이미지를 보고 아래 JSON만 출력하세요. 다른 말은 하지 마세요.

{
  "is_pill": true,
  "print_front": "앞면 각인 문자 그대로 (없으면 null)",
  "print_back": "뒷면 각인 문자 그대로 (없으면 null)",
  "color": "색상 (예: 하양, 노랑, 분홍)",
  "shape": "모양 (예: 원형, 타원형, 장방형)"
}

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
    """
    각인+색상+모양으로 imprint 청크 벡터 검색.
    매칭된 약품의 item_seq, item_name 반환.
    imprint 데이터 없거나 유사도 낮으면 None 반환.
    """
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
                "imprint 매칭 실패 - 유사도 낮음 (%.3f < %.1f): %s",
                similarity, IMPRINT_SIMILARITY_THRESHOLD, query,
            )
            return None

        logger.info(
            "imprint 매칭 성공: '%s' → '%s' (유사도: %.3f)",
            query, best["item_name"], similarity,
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
    """
    item_seq로 drug_embeddings에서 허가정보 직접 조회.
    GPT 재호출 없음.

    반환:
        {
            "efficacy": "...",
            "active_ingredients": "...",
            "caution": "...",
        }
    """
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
        # "[약품명] 효능효과: 실제내용" → "실제내용" 추출
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
        user_id, file_id,
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
        image_b64_list = []
        for s3_key in s3_keys[:2]:
            image_bytes = download_file_from_s3(s3_key)
            image_b64_list.append(preprocess_image(image_bytes))

        if not image_b64_list:
            raise ValueError("처리할 이미지가 없습니다.")

        # ── 1단계: GPT Vision - 각인/색상/모양 추출 ──
        features = await extract_pill_features(client, image_b64_list, model)
        logger.info("1단계 완료: %s", features)

        # 알약이 아닌 이미지 처리
        if not features.get("is_pill", True):
            logger.info("알약 이미지가 아님 → 식별 불가 반환")
            result = {
                "product_name": "알약 이미지가 아닙니다",
                "gpt_model_version": model,
            }
            analysis_id = await save_analysis_result(conn, user_id, file_id, result)
            return {"analysis_id": analysis_id, "product_name": result["product_name"], "result": result}

        # ── 2단계: imprint RAG - 약품 특정 ──
        matched_drug = await find_drug_by_imprint(conn, client, features)

        if matched_drug is None:
            # imprint 매칭 실패 → 각인 정보만 저장
            logger.info("2단계 매칭 실패 → 각인 정보만 저장")
            product_name = None
            if features.get("print_front") or features.get("print_back"):
                parts = [v for v in [features.get("print_front"), features.get("print_back")] if v]
                product_name = f"각인: {', '.join(parts)} (DB 미매칭)"

            result = {
                "product_name": product_name or "식별 불가",
                "gpt_model_version": model,
            }
            analysis_id = await save_analysis_result(conn, user_id, file_id, result)
            return {"analysis_id": analysis_id, "product_name": result["product_name"], "result": result}

        # ── 3단계: 허가정보 DB 직접 조회 ──
        db_info = await fetch_drug_info_from_db(conn, matched_drug["item_seq"])
        logger.info("3단계 완료: item_seq=%s, 조회 필드=%s", matched_drug["item_seq"], list(db_info.keys()))

        # 결과 조합 (GPT 재호출 없음)
        result = {
            "product_name": matched_drug["item_name"],
            "active_ingredients": db_info.get("ingredient"),
            "efficacy": db_info.get("efficacy"),
            "usage_method": None,       # 허가정보에 없는 필드
            "warning": None,
            "caution": db_info.get("caution"),
            "interactions": None,
            "side_effects": None,
            "storage_method": None,
            "gpt_model_version": model,
        }

        analysis_id = await save_analysis_result(conn, user_id, file_id, result)
        logger.info("분석 완료: analysis_id=%s, product_name=%s", analysis_id, result["product_name"])

        return {
            "analysis_id": analysis_id,
            "product_name": result["product_name"],
            "result": result,
        }

    finally:
        await conn.close()
