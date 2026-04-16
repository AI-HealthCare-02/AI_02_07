# ai_worker/tasks/medical_doc.py
# ──────────────────────────────────────────────
# 의료 문서 분석 워커 — 이승원 담당
#
# S3에서 문서를 다운로드 → GPT Vision OCR → GPT 구조화 분석 → 결과 반환
# ──────────────────────────────────────────────

import base64
import io
import json

import httpx
from PIL import Image, ImageOps

from ai_worker.core.config import get_worker_settings
from ai_worker.core.logger import setup_logger

try:
    from langfuse.openai import AsyncOpenAI
except ImportError:
    from openai import AsyncOpenAI  # type: ignore[assignment]

logger = setup_logger("task.medical_doc")
settings = get_worker_settings()


# ── 이미지 전처리 ─────────────────────────────
def preprocess_image(image_bytes: bytes) -> str:
    """이미지를 base64로 인코딩하여 반환"""
    image = Image.open(io.BytesIO(image_bytes))
    image = ImageOps.exif_transpose(image)
    if image.mode != "RGB":
        image = image.convert("RGB")
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


# ── GPT Vision OCR ────────────────────────────
async def extract_text_from_image(client: AsyncOpenAI, image_b64: str) -> str:
    response = await client.chat.completions.create(
        model="gpt-4o",
        max_tokens=2000,
        name="ocr_extract",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "이 의료 문서 이미지에서 모든 텍스트를 정확하게 추출해줘. 원본 형식을 최대한 유지해줘.",
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_b64}", "detail": "high"},
                    },
                ],
            }
        ],
    )
    return response.choices[0].message.content or ""


# ── 문서 종류 자동 감지 ───────────────────────
async def detect_document_type(client: AsyncOpenAI, extracted_text: str) -> str:
    messages = [
        {
            "role": "user",
            "content": f"""아래 텍스트가 어떤 종류의 의료 문서인지 판단해줘.
반드시 아래 JSON만 출력하고 다른 말은 하지 마.
{{"document_type": "처방전" | "진료기록" | "약봉투"}}

--- 텍스트 ---
{extracted_text[:300]}""",
        }
    ]
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        max_tokens=50,
        name="detect_doc_type",
        messages=messages,
    )
    result = response.choices[0].message.content.strip()
    try:
        parsed = json.loads(result)
        return parsed.get("document_type", "약봉투")
    except Exception:
        return "약봉투"


# ── 문서 종류별 프롬프트 ──────────────────────
def get_prompt_by_document_type(doc_type: str, extracted_text: str) -> str:
    base = f"아래는 의료 문서에서 추출한 텍스트입니다.\n반드시 JSON만 출력하고 다른 말은 하지 마세요.\n\n--- 텍스트 ---\n{extracted_text}\n\n"

    if doc_type == "처방전":
        return base + """다음 JSON 형식으로 추출해줘:
{
  "hospital_name": "병원명",
  "visit_date": "진료일(YYYY-MM-DD)",
  "diagnosis_name": "진단명",
  "medications": [{"name": "약품명", "dosage": "용량", "frequency": "복용횟수", "duration": "복용기간"}],
  "medication_schedule": "복약 일정 요약",
  "cautions": "주의사항",
  "overall_confidence": 0.95,
  "raw_summary": "전체 요약"
}"""
    elif doc_type == "진료기록":
        return base + """다음 JSON 형식으로 추출해줘:
{
  "hospital_name": "병원명",
  "visit_date": "진료일(YYYY-MM-DD)",
  "diagnosis_name": "진단명",
  "symptoms": "증상",
  "treatment": "치료 내용",
  "cautions": "주의사항",
  "overall_confidence": 0.95,
  "raw_summary": "전체 요약"
}"""
    else:  # 약봉투
        return base + """다음 JSON 형식으로 추출해줘:
{
  "hospital_name": "약국명",
  "visit_date": "조제일(YYYY-MM-DD)",
  "medications": [{"name": "약품명", "dosage": "용량", "frequency": "복용횟수", "duration": "복용기간"}],
  "medication_schedule": "복약 일정 요약",
  "cautions": "주의사항",
  "overall_confidence": 0.95,
  "raw_summary": "전체 요약"
}"""


# ── GPT 구조화 분석 ───────────────────────────
async def analyze_with_gpt(
    client: AsyncOpenAI,
    extracted_text: str,
    doc_type: str,
) -> dict:
    if doc_type == "자동인식":
        doc_type = await detect_document_type(client, extracted_text)
        logger.info(f"자동 감지된 문서 종류: {doc_type}")
    else:
        logger.info(f"선택된 문서 종류: {doc_type}")

    prompt = get_prompt_by_document_type(doc_type, extracted_text)
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        max_tokens=1500,
        name="analyze_doc",
        messages=[{"role": "user", "content": prompt}],
    )
    raw = response.choices[0].message.content.strip()
    try:
        result = json.loads(raw)
    except Exception:
        result = {"raw_summary": raw, "overall_confidence": 0.5}
    result["doc_type"] = doc_type
    return result


# ── 메인 진입점 ───────────────────────────────
async def analyze_medical_document(
    image_bytes_list: list[bytes],
    document_type: str = "자동인식",
) -> dict:
    """
    이미지 바이트 리스트를 받아 OCR → 구조화 분석 결과 dict 반환
    """
    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    ocr_texts = []
    for image_bytes in image_bytes_list:
        image_b64 = preprocess_image(image_bytes)
        text = await extract_text_from_image(client, image_b64)
        ocr_texts.append(text)
        logger.info(f"OCR 완료: {len(text)}자 추출")

    combined_text = "\n\n".join(ocr_texts)
    return await analyze_with_gpt(client, combined_text, document_type)
