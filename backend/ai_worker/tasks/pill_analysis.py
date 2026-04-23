# ai_worker/tasks/pill_analysis.py
# ──────────────────────────────────────────────
# 알약 분석 작업 핸들러 — 안은지 담당
#
# 흐름:
#   S3에서 이미지 다운로드 → 전처리(리사이즈/JPEG/Base64)
#   → RAG 컨텍스트 조회 → GPT 멀티모달 분석 → DB 저장
# ──────────────────────────────────────────────

import base64
import io
import json

import asyncpg
from openai import AsyncOpenAI
from PIL import Image

from ai_worker.core.config import get_worker_settings
from ai_worker.core.logger import setup_logger
from ai_worker.core.s3_client import download_from_s3

logger = setup_logger("task.pill_analysis")
settings = get_worker_settings()

MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
TARGET_SIZE = 1024  # 최대 1024px (최소 768px 유지)


# ── 이미지 전처리 ──────────────────────────────
def preprocess_image(image_bytes: bytes) -> str:
    """
    이미지를 전처리하고 Base64 문자열로 반환합니다.
    - 크기: 768~1024px (비율 유지)
    - 포맷: JPEG
    - 용량: 5MB 이하 검증
    """
    if len(image_bytes) > MAX_IMAGE_SIZE:
        raise ValueError(f"이미지 용량이 5MB를 초과합니다: {len(image_bytes) / 1024 / 1024:.1f}MB")

    img = Image.open(io.BytesIO(image_bytes))

    # EXIF 회전 보정
    try:
        from PIL import ImageOps

        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    # RGB 변환
    if img.mode != "RGB":
        img = img.convert("RGB")

    # 리사이즈: 최대 1024px, 최소 768px 유지 (비율 유지)
    w, h = img.size
    max_dim = max(w, h)
    if max_dim > TARGET_SIZE:
        ratio = TARGET_SIZE / max_dim
        new_w, new_h = int(w * ratio), int(h * ratio)
        img = img.resize((new_w, new_h), Image.LANCZOS)

    # JPEG 인코딩
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=90)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


# ── RAG 컨텍스트 조회 ──────────────────────────
async def get_rag_context(query: str) -> str:
    """
    약품명/증상으로 RAG 검색하여 컨텍스트 반환.
    실패 시 빈 문자열 반환 (분석은 계속 진행).
    """
    try:
        from tortoise import Tortoise

        from app.services.rag_service import get_rag_service

        if not Tortoise._inited:
            await Tortoise.init(
                db_url=settings.database_url,
                modules={"models": []},
            )

        rag = get_rag_service()
        context = await rag.build_context(
            query=query,
            top_k=3,
            chunk_type="caution",
            min_similarity=0.4,
        )
        return context
    except Exception as e:
        logger.warning("RAG 조회 실패 (무시): %s", e)
        return ""


# ── ai_settings 조회 ───────────────────────────
async def get_ai_model(conn: asyncpg.Connection) -> str:
    """ai_settings 테이블에서 활성화된 모델명 조회."""
    row = await conn.fetchrow("SELECT api_model FROM ai_settings WHERE is_active = TRUE LIMIT 1")
    return row["api_model"] if row else "gpt-4o-mini"


# ── GPT 멀티모달 분석 ──────────────────────────
async def analyze_pill_images(
    client: AsyncOpenAI,
    image_b64_list: list[str],
    rag_context: str,
    model: str,
) -> dict:
    """
    알약 이미지(앞/뒷면)를 GPT 멀티모달로 분석합니다.
    """
    # 이미지 콘텐츠 구성
    image_contents = []
    for i, b64 in enumerate(image_b64_list):
        image_contents.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{b64}",
                    "detail": "high",
                },
            }
        )
        image_contents.append(
            {
                "type": "text",
                "text": f"위 이미지는 알약의 {'앞면' if i == 0 else '뒷면'}입니다.",
            }
        )

    # RAG 컨텍스트 프롬프트 구성
    rag_section = f"\n\n[약품 공식 DB 참고 정보]\n{rag_context}" if rag_context else ""

    prompt = f"""당신은 약학 전문가입니다. 제공된 알약 이미지를 분석하여 약품 정보를 추출해주세요.{rag_section}

위 이미지의 알약을 분석하여 아래 JSON 형식으로만 응답하세요. 다른 말은 하지 마세요.
이미지에서 확인할 수 없는 정보는 null로 설정하세요.

{{
  "product_name": "제품명 (알약에 각인된 문자나 색상/모양으로 추정)",
  "active_ingredients": "주요 성분 (확인 가능한 경우)",
  "efficacy": "효능 및 효과",
  "usage_method": "복용 방법 및 용량",
  "warning": "경고 사항",
  "caution": "주의사항",
  "interactions": "약물 상호작용",
  "side_effects": "부작용",
  "storage_method": "보관 방법",
  "gpt_model_version": "{model}"
}}"""

    contents = image_contents + [{"type": "text", "text": prompt}]

    response = await client.chat.completions.create(
        model=model,
        max_tokens=1500,
        temperature=0,
        messages=[{"role": "user", "content": contents}],
    )

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "product_name": "분석 실패",
            "gpt_model_version": model,
            "raw_response": raw,
        }


# ── DB 저장 ────────────────────────────────────
async def save_analysis_result(
    conn: asyncpg.Connection,
    user_id: int,
    file_id: int,
    result: dict,
) -> int:
    """pill_analysis_history 테이블에 분석 결과 저장."""
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
    """
    알약 분석 태스크 메인 핸들러.

    payload:
        user_id: int
        file_id: int          — uploaded_file PK
        s3_keys: list[str]    — 앞면/뒷면 S3 키 (최대 2개)
    """
    payload = task_data["payload"]
    user_id: int = payload["user_id"]
    file_id: int = payload["file_id"]
    s3_keys: list[str] = payload["s3_keys"]

    logger.info("알약 분석 시작 | user_id=%s, file_id=%s", user_id, file_id)

    # DB 연결
    conn = await asyncpg.connect(settings.database_url.replace("asyncpg://", "postgresql://"))

    try:
        # 1. ai_settings에서 모델 조회
        model = await get_ai_model(conn)
        logger.info("사용 모델: %s", model)

        # 2. S3에서 이미지 다운로드 + 전처리
        image_b64_list = []
        for s3_key in s3_keys[:2]:  # 최대 2장
            image_bytes = await download_from_s3(s3_key)
            b64 = preprocess_image(image_bytes)
            image_b64_list.append(b64)
            logger.info("이미지 전처리 완료: %s", s3_key)

        if not image_b64_list:
            raise ValueError("처리할 이미지가 없습니다.")

        # 3. RAG 컨텍스트 조회 (첫 번째 이미지 기반 쿼리)
        rag_context = await get_rag_context("알약 주의사항 부작용 복용방법")

        # 4. GPT 멀티모달 분석
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        result = await analyze_pill_images(client, image_b64_list, rag_context, model)
        logger.info("GPT 분석 완료: %s", result.get("product_name"))

        # 5. DB 저장
        analysis_id = await save_analysis_result(conn, user_id, file_id, result)
        logger.info("DB 저장 완료: analysis_id=%s", analysis_id)

        return {
            "analysis_id": analysis_id,
            "product_name": result.get("product_name"),
            "result": result,
        }

    finally:
        await conn.close()
