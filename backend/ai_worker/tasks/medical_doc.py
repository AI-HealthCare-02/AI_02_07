# ai_worker/tasks/medical_doc.py
# ──────────────────────────────────────────
# 의료 문서 분석 작업 핸들러 – 이승원 담당
#
# 이 파일에 vLLM 기반 의료 문서 분석 로직을 구현하세요.
# S3에서 문서를 다운로드 → vLLM 추론 → 결과 반환
# ──────────────────────────────────────────

import base64
import io
import json

import httpx
from openai import AsyncOpenAI
from PIL import Image, ImageOps

from ai_worker.core.config import get_worker_settings
from ai_worker.core.logger import setup_logger

logger = setup_logger("task.medical_doc")
settings = get_worker_settings()

# ── 상수 ──────────────────────────────────
CONFIDENCE_THRESHOLD = 0.7
INSTRUCTION_KEYWORDS = ["식전", "식후", "취침전"]


# ── OpenAI 클라이언트 ──────────────────────
def get_openai_client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


# ── 이미지 전처리 ──────────────────────────
def preprocess_image(image_bytes: bytes, rotate: int = 0) -> bytes:
    img = Image.open(io.BytesIO(image_bytes))
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass
    if rotate != 0:
        img = img.rotate(rotate, expand=True)
    max_size = 1500
    if max(img.size) > max_size:
        img.thumbnail((max_size, max_size), Image.LANCZOS)
    if img.mode != "RGB":
        img = img.convert("RGB")
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


# ── 클로버 OCR ─────────────────────────────
async def extract_text_with_clova(image_bytes: bytes) -> str | None:
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    payload = {
        "images": [{"format": "jpg", "name": "medical_doc", "data": image_base64}],
        "requestId": "healthguide",
        "version": "V2",
        "timestamp": 0,
    }
    headers = {
        "X-OCR-SECRET": settings.OCR_SECRET_KEY,
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(
            settings.OCR_INVOKE_URL,
            headers=headers,
            json=payload,
            timeout=30,
        )
    if response.status_code != 200:
        logger.error(f"클로버 OCR 오류: {response.status_code}")
        return None
    result = response.json()
    texts = []
    for image in result.get("images", []):
        for field in image.get("fields", []):
            texts.append(field.get("inferText", ""))
    return " ".join(texts)


# ── 자동 회전 감지 + 텍스트 추출 (재시도 포함) ─────────────
async def extract_text_with_auto_rotate(
    image_bytes: bytes,
    max_retries: int = 3,
    retry_delay: float = 1.0,
) -> str | None:
    import asyncio

    for angle in [0, 90, 180, 270]:
        processed = preprocess_image(image_bytes, rotate=angle)

        for attempt in range(1, max_retries + 1):
            try:
                text = await extract_text_with_clova(processed)
                if text and len(text.strip()) > 10:
                    logger.info(f"{angle}도에서 텍스트 추출 성공 ({len(text)}자)")
                    return text
                else:
                    logger.info(f"{angle}도 실패, 다음 각도 시도...")
                    break  # 텍스트가 없으면 재시도 없이 다음 각도로

            except Exception as e:
                if attempt < max_retries:
                    logger.warning(
                        f"{angle}도 OCR 오류 (시도 {attempt}/{max_retries}): {e} "
                        f"→ {retry_delay}초 후 재시도"
                    )
                    await asyncio.sleep(retry_delay)
                else:
                    logger.error(
                        f"{angle}도 OCR 최종 실패 (시도 {max_retries}/{max_retries}): {e}"
                    )

    return None


# ── 문서 종류별 프롬프트 ───────────────────
def get_prompt_by_document_type(doc_type: str, extracted_text: str) -> str:
    prompts = {
        "처방전": f"""아래는 처방전에서 OCR로 추출한 텍스트야.
이 텍스트를 분석해서 JSON 형식으로 구조화해줘.

규칙:
- 텍스트에 있는 내용만 추출해. 절대 추측하거나 지어내지 마.
- 텍스트에 명시되지 않은 정보는 반드시 null로 설정해.
- 확실하지 않은 필드는 null로 설정하고 confidence를 낮게 설정해.
반드시 JSON만 출력하고 다른 말은 하지 마.

{{
  "document_type": "처방전",
  "hospital_name": "병원명",
  "doctor_name": "의사명 (없으면 null)",
  "prescription_date": "처방일 (YYYY-MM-DD)",
  "diagnosis": "진단명 (없으면 null)",
  "medications": [
    {{
      "medication_name": "약품명",
      "dosage": "1회 용량",
      "frequency": "1일 몇 회",
      "duration_days": 복용일수,
      "instructions": "식전/식후 등 복용법 (없으면 null)",
      "confidence": 0.0
    }}
  ],
  "cautions": "주의사항 (없으면 null)",
  "overall_confidence": 0.0,
  "raw_summary": "문서 전체 요약"
}}

--- 추출된 텍스트 ---
{extracted_text}""",

        "진료기록": f"""아래는 진료기록에서 OCR로 추출한 텍스트야.
이 텍스트를 분석해서 JSON 형식으로 구조화해줘.

규칙:
- 텍스트에 있는 내용만 추출해. 절대 추측하거나 지어내지 마.
- 텍스트에 명시되지 않은 정보는 반드시 null로 설정해.
- 확실하지 않은 필드는 null로 설정하고 confidence를 낮게 설정해.
반드시 JSON만 출력하고 다른 말은 하지 마.

{{
  "document_type": "진료기록",
  "hospital_name": "병원명",
  "doctor_name": "의사명 (없으면 null)",
  "visit_date": "진료일 (YYYY-MM-DD)",
  "diagnosis": "진단명 (없으면 null)",
  "symptoms": "주요 증상 (없으면 null)",
  "treatment": "처치 내용 (없으면 null)",
  "medications": [
    {{
      "medication_name": "약품명",
      "dosage": "1회 용량",
      "frequency": "1일 몇 회",
      "duration_days": 복용일수,
      "instructions": "식전/식후 등 복용법 (없으면 null)",
      "confidence": 0.0
    }}
  ],
  "cautions": "주의사항 (없으면 null)",
  "next_visit": "다음 방문일 (없으면 null)",
  "overall_confidence": 0.0,
  "raw_summary": "문서 전체 요약"
}}

--- 추출된 텍스트 ---
{extracted_text}""",

        "검진결과": f"""아래는 건강검진결과서에서 OCR로 추출한 텍스트야.
이 텍스트를 분석해서 JSON 형식으로 구조화해줘.

규칙:
- 텍스트에 있는 내용만 추출해. 절대 추측하거나 지어내지 마.
- 텍스트에 명시되지 않은 정보는 반드시 null로 설정해.
- 표 형태 데이터도 항목별로 구조화해줘.
- 확실하지 않은 필드는 null로 설정하고 confidence를 낮게 설정해.
반드시 JSON만 출력하고 다른 말은 하지 마.

{{
  "document_type": "검진결과",
  "hospital_name": "검진기관명",
  "exam_date": "검진일 (YYYY-MM-DD)",
  "patient_name": "수검자명 (없으면 null)",
  "exam_items": [
    {{
      "item_name": "검사항목명",
      "value": "측정값",
      "unit": "단위 (없으면 null)",
      "normal_range": "정상범위 (없으면 null)",
      "status": "정상/주의/이상 (없으면 null)",
      "confidence": 0.0
    }}
  ],
  "overall_result": "종합 소견 (없으면 null)",
  "cautions": "주의사항 (없으면 null)",
  "overall_confidence": 0.0,
  "raw_summary": "문서 전체 요약"
}}

--- 추출된 텍스트 ---
{extracted_text}""",

        "약봉투": f"""아래는 약봉투에서 OCR로 추출한 텍스트야.
이 텍스트를 분석해서 JSON 형식으로 구조화해줘.

규칙:
- 반드시 '복약안내' 또는 '복약안내문' 섹션 내용을 기준으로 분석해.
- 약제비 계산서, 영수증, 손글씨 메모는 무시해.
- 텍스트에 있는 내용만 추출해. 절대 추측하거나 지어내지 마.
- 텍스트에 명시되지 않은 정보는 반드시 null로 설정해.
- instructions 필드는 텍스트에 식전/식후가 명확히 적혀있을 때만 채워. 없으면 null.
- 확실하지 않은 필드는 null로 설정하고 confidence를 낮게 설정해.
반드시 JSON만 출력하고 다른 말은 하지 마.

{{
  "document_type": "약봉투",
  "hospital_name": "병원명 또는 약국명",
  "prescription_date": "조제일 (YYYY-MM-DD)",
  "diagnosis": null,
  "medications": [
    {{
      "medication_name": "약품명",
      "dosage": "1회 용량",
      "frequency": "1일 몇 회",
      "duration_days": 복용일수,
      "instructions": "식전/식후 등 복용법 (없으면 null)",
      "confidence": 0.0
    }}
  ],
  "cautions": "주의사항 (없으면 null)",
  "overall_confidence": 0.0,
  "raw_summary": "문서 전체 요약"
}}

--- 추출된 텍스트 ---
{extracted_text}""",
    }
    return prompts.get(doc_type, prompts["약봉투"])


# ── 문서 종류 자동 감지 ───────────────────
async def detect_document_type(client: AsyncOpenAI, extracted_text: str) -> str:
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        messages=[
            {
                "role": "user",
                "content": f"""아래 텍스트가 어떤 종류의 의료 문서인지 판단해줘.
반드시 아래 JSON만 출력하고 다른 말은 하지 마.

{{"document_type": "처방전" 또는 "진료기록" 또는 "검진결과" 또는 "약봉투"}}

--- 텍스트 ---
{extracted_text[:300]}""",
            }
        ],
        max_tokens=50,
    )
    result = response.choices[0].message.content.strip()
    try:
        parsed = json.loads(result)
        return parsed.get("document_type", "약봉투")
    except Exception:
        return "약봉투"


# ── GPT 구조화 분석 ───────────────────────
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
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1500,
    )
    result = response.choices[0].message.content.strip()
    cleaned = result
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    return json.loads(cleaned)


# ── 메인 분석 파이프라인 ──────────────────
async def analyze_medical_document(
    image_bytes_list: list[bytes],
    document_type: str,
) -> dict:
    """
    여러 이미지를 받아서 OCR + GPT 분석 후 결과 반환

    Args:
        image_bytes_list: 이미지 바이트 리스트 (앞면, 뒷면 등)
        document_type: 문서 종류 (처방전/진료기록/약봉투/검진결과/자동인식)

    Returns:
        분석 결과 JSON dict
    """
    client = get_openai_client()
    all_texts = []

    for i, image_bytes in enumerate(image_bytes_list):
        logger.info(f"[{i+1}/{len(image_bytes_list)}] 이미지 처리 중...")
        text = await extract_text_with_auto_rotate(image_bytes)
        if text:
            all_texts.append(f"=== 이미지 {i+1} ===\n{text}")
        else:
            logger.warning(f"이미지 {i+1} 텍스트 추출 실패")

    if not all_texts:
        return {"error": "텍스트 추출 실패", "overall_confidence": 0.0}

    combined_text = "\n\n".join(all_texts)
    logger.info(f"전체 추출 텍스트 길이: {len(combined_text)}자")

    result = await analyze_with_gpt(client, combined_text, document_type)
    return result