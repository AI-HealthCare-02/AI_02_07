# ai_worker/tasks/pill_analysis.py
# ──────────────────────────────────────────────
# 알약 분석 작업 핸들러 — 안은지 담당
#
# [3단계 흐름]
#
# 1단계: Clova OCR (각인 텍스트 추출) +
#        GPT Vision detail:low (색상/모양만 추출)
#
# 2단계: imprint RAG
#   → metadata exact/swapped match + vector search 통합
#   → STEP 6 rerank 점수로 최종 순위 결정
#
# 3단계: 허가정보 DB 직접 조회 (GPT 재호출 없음)
#   → item_seq로 efficacy/caution/ingredient 조회
# ──────────────────────────────────────────────

import asyncio
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
from ai_worker.tasks.imprint_parser import color_tokens, normalize_vision_result, shape_match_score

logger = setup_logger("task.pill_analysis")
settings = get_worker_settings()

MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
TARGET_SIZE = 1024
IMPRINT_SIMILARITY_THRESHOLD = 0.55


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
async def _ocr_request(client: httpx.AsyncClient, image_bytes: bytes) -> str:
    """단일 이미지 OCR 요청, 인식된 텍스트 반환 (없으면 빈 문자열)."""
    payload = {
        "version": "V2",
        "requestId": str(uuid.uuid4()),
        "timestamp": 0,
        "images": [{"format": "jpg", "name": "pill", "data": base64.b64encode(image_bytes).decode()}],
    }
    headers = {"X-OCR-SECRET": settings.OCR_SECRET_KEY, "Content-Type": "application/json"}
    resp = await client.post(settings.OCR_INVOKE_URL, json=payload, headers=headers)
    resp.raise_for_status()
    fields = resp.json()["images"][0].get("fields", [])
    return " ".join(f["inferText"] for f in fields if f.get("inferText")).strip().upper()


def _rotate_180(image_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(image_bytes)).rotate(180, expand=True)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


async def extract_imprint_ocr(image_bytes: bytes) -> str | None:
    """
    원본 + 180도 회전 OCR을 모두 실행하고 결과를 합산 반환.
    분할선 양쪽 각인이 방향에 따라 한쪽만 잡히는 문제를 완화.
    """
    if not settings.OCR_INVOKE_URL or not settings.OCR_SECRET_KEY:
        return None

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            normal, rotated = await asyncio.gather(
                _ocr_request(client, image_bytes),
                _ocr_request(client, _rotate_180(image_bytes)),
            )
        logger.info("Clova OCR 결과: normal=%s, rotated=%s", normal, rotated)

        # 두 결과를 토큰 단위로 합산 — 중복 제거 후 병합
        # 분할선 기준 한쪽만 잡히는 경우를 보완
        normal_tokens = normal.split() if normal else []
        rotated_tokens = rotated.split() if rotated else []
        seen: set[str] = set()
        merged: list[str] = []
        for t in normal_tokens + rotated_tokens:
            if t not in seen:
                seen.add(t)
                merged.append(t)

        result = " ".join(merged) or None
        logger.info("Clova OCR 병합 결과: %s", result)
        return result
    except Exception as e:
        logger.warning("Clova OCR 실패 (무시): %s", e)
        return None


# ── 1단계: GPT Vision ─────────────────────────
async def extract_pill_features(
    client: AsyncOpenAI,
    image_b64_list: list[str],
    ocr_texts: list[str | None],
    model: str,
) -> dict:
    image_contents = []
    for i, b64 in enumerate(image_b64_list):
        face = "앞면" if i == 0 else "뒷면"
        ocr_hint = f" (OCR 각인: {ocr_texts[i]})" if i < len(ocr_texts) and ocr_texts[i] else ""
        # detail:high — 각인 판독 정확도 향상 목적. low 대비 토큰 비용 약 3~4배 증가.
        image_contents.append(
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "high"}}
        )
        image_contents.append({"type": "text", "text": f"위 이미지는 알약의 {face}입니다.{ocr_hint}"})

    ocr_front = ocr_texts[0] if ocr_texts else None
    ocr_back = ocr_texts[1] if len(ocr_texts) > 1 else None

    prompt = f"""
당신은 알약 이미지에서 각인, 분할선, 십자분할선, 색상, 모양을 추출하는 분석기입니다.
반드시 JSON만 출력하세요. 설명/마크다운/코드블록은 금지입니다.

[핵심 원칙]
- OCR은 정답이 아니라 참고값입니다. 최종 판단은 이미지에서 보이는 내용을 우선하세요.
- OCR은 분할선, 십자분할선, 분할선 반대편 문자/숫자를 누락할 수 있습니다.
- OCR이 한 글자 또는 일부 문자열만 제공되어도 전체 각인이라고 확정하지 마세요.
- 이미지에 없는 문자/숫자/기호를 임의로 만들지 마세요.
- 실제 약품명처럼 보이도록 무리하게 보정하지 마세요.
- 분할선/십자분할선은 각인이 아니므로 print_front/print_back에 "분할선"이라는 단어를 넣지 마세요.
- 하지만 분할선 주변 또는 분할된 영역 안의 문자/숫자는 각인입니다.

OCR 참고값:
- 앞면 OCR: {ocr_front or "없음 또는 불완전"}
- 뒷면 OCR: {ocr_back or "없음 또는 불완전"}

[업로드 패턴]
- 첫 번째 이미지=앞면 후보, 두 번째 이미지=뒷면 후보입니다.
- 앞뒤가 바뀌었을 수 있으므로 이미지의 각인/분할선/OCR을 종합해 판단하세요.
- 한 이미지에 같은 알약의 앞뒷면이 같이 있으면 각각 구분하세요. 이 경우 multiple_pills=false입니다.
- 서로 다른 알약이 여러 개 있으면 multiple_pills=true입니다.

[각인 판독]
- 알약 표면의 문자, 숫자, 로고, 기호만 기록하세요.
- 공백이 보이면 유지하세요.
- 같은 면에 "HL"과 "PGN300"이 보이면 "HL PGN300"처럼 출력하세요.
- 각인이 없거나 판독 불가능하면 null입니다.
- 혼동 주의: O/0, I/1/L, S/5, B/8, G/6, Z/2, H/N, M/W/N, C/G, P/R.
- 혼동 문자는 이미지에서 명확할 때만 교정하세요.

[분할선 판단 - 매우 중요]
score_line_type 값:
- "없음"
- "분할선": 한 줄짜리 분할선. 세로/가로/대각선 포함
- "십자분할선": 가로선과 세로선이 교차하는 십자 모양
- "판독불가"

score_line_direction 값:
- "없음"
- "세로"
- "가로"
- "대각선"
- "십자"
- "판독불가"

[십자분할선 판단 기준 - 특히 주의]
- 알약 표면에 가로선과 세로선이 동시에 보이면 반드시 "십자분할선"으로 판단하세요.
- 십자분할선은 알약을 4등분하는 선입니다. 원형 알약에서 자주 보입니다.
- 조명/각도에 따라 한 선만 보일 수 있어도, 알약을 돌려보면서 십자 패턴이 확인되면 "십자분할선"으로 판단하세요.
- "분할선"(한 줄)과 "십자분할선"(두 줄 교차)을 혼동하지 마세요.
- 십자분할선이 있는 면에 각인이 없으면: print=null, score_line_type="십자분할선"
- 십자분할선이 있는 면에 각인이 있으면: 각 영역(top/bottom/left/right)에서 각인 확인

분할선이 있으면 각인을 한 덩어리로 읽지 말고 영역별로 확인하세요.
- 세로 분할선: left_text, right_text 확인. 예: ID|25 -> print="ID 25", raw="ID|25"
- 가로 분할선: top_text, bottom_text 확인. 예: ID/25 -> print="ID 25", raw="ID/25"
- 각 영역은 한 글자일 수도 있고 여러 글자일 수도 있습니다.
- 십자분할선만 있고 텍스트가 없으면 print는 null입니다.
- DB에는 세로/가로 구분 없이 "분할선"만 있을 수 있지만, 이미지 분석에서는 보이는 방향을 기록하세요.

[색상 판단]
- 배경/그림자/반사는 제외하고 알약 본체 색만 판단하세요.
- 표준 색상명 사용: 하양, 아이보리, 노랑, 주황, 분홍, 빨강, 갈색, 연두, 초록, 파랑, 보라, 회색, 검정, 투명.
- "반투명"은 사용하지 말고, 투명해 보이면 "투명"으로만 기록하세요.
- 단색이면 예: "하양", "갈색"
- 두 가지 불투명 색으로 나뉜 경질캡슐이면 "/" 사용. 예: "갈색/하양", "초록/하양"
- 투명한 연질캡슐이면 ", 투명" 사용. 예: "갈색, 투명", "노랑, 투명"
- 투명이 보이면 is_transparent=true로 설정하세요.

[모양/제형 판단]
shape는 반드시 아래 중 하나만 사용하세요. "캡슐형"은 사용하지 마세요.
- 원형, 타원형, 장방형, 반원형, 삼각형, 사각형, 마름모형, 오각형, 육각형, 팔각형, 기타, 판독불가

dosage_form_hint 값:
- "정제"
- "경질캡슐"
- "연질캡슐"
- "판독불가"

캡슐 기준:
- 경질캡슐: 두 개의 캡슐 껍질이 결합된 형태, 중앙 결합선 또는 두 색 구역이 보일 수 있음. 대부분 shape="장방형".
- 연질캡슐: 매끈한 젤라틴 캡슐, 투명하거나 내부 액상 느낌이 보일 수 있음. shape는 타원형/장방형/삼각형 가능.
- 캡슐 여부는 shape가 아니라 dosage_form_hint에 기록하세요.

[원형/타원형/장방형 구분 - 매우 중요]
- 원형: 가로와 세로가 거의 같음. 외곽이 원에 가까움.
- 타원형: 전체 외곽이 매끄러운 달걀형/타원형. 중앙부에 긴 직선 구간이 거의 없음.
- 장방형: 가로가 세로보다 뚜렷하게 김. 가운데 몸통 부분이 직선에 가깝고, 양 끝만 둥글게 처리된 긴 직사각형 형태.
- 중앙부가 직선처럼 길게 뻗어 있으면 장방형. 전체가 연속된 곡선으로 둥글게 이어지면 타원형.
- 애매하면 notes에 "타원형/장방형 혼동 가능"이라고 적으세요.

[출력 JSON]
{{
  "is_pill": true,
  "multiple_pills": false,

  "print_front": null,
  "print_front_raw": null,
  "score_line_front_type": "없음 | 분할선 | 십자분할선 | 판독불가",
  "score_line_front_direction": "없음 | 세로 | 가로 | 대각선 | 십자 | 판독불가",
  "front_left_text": null,
  "front_right_text": null,
  "front_top_text": null,
  "front_bottom_text": null,

  "print_back": null,
  "print_back_raw": null,
  "score_line_back_type": "없음 | 분할선 | 십자분할선 | 판독불가",
  "score_line_back_direction": "없음 | 세로 | 가로 | 대각선 | 십자 | 판독불가",
  "back_left_text": null,
  "back_right_text": null,
  "back_top_text": null,
  "back_bottom_text": null,

  "color": "예: 하양, 갈색/하양, 갈색, 투명",
  "color_count": 1,
  "color_detail": "짧은 색상 설명",
  "is_transparent": false,

  "shape": "원형 | 타원형 | 장방형 | 반원형 | 삼각형 | 사각형 | 마름모형 | 오각형 | 육각형 | 팔각형 | 기타 | 판독불가",
  "dosage_form_hint": "정제 | 경질캡슐 | 연질캡슐 | 판독불가",

  "confidence": 0.0,
  "imprint_confidence": 0.0,
  "score_line_confidence": 0.0,
  "color_confidence": 0.0,
  "shape_confidence": 0.0,
  "notes": null
}}

예시:
- ID|25가 보이면 print_front="ID 25", print_front_raw="ID|25", score_line_front_type="분할선"
- 1|3이 보이면 print_back="1 3", print_back_raw="1|3", score_line_back_type="분할선"
- 십자분할선만 있고 글자가 없으면 print=null, score_line_type="십자분할선"
- 원형 알약에 가로선+세로선이 보이면 반드시 score_line_type="십자분할선" ("분할선" 아님)
- 갈색/하양 경질캡슐이면 color="갈색/하양", shape="장방형", dosage_form_hint="경질캡슐"
- 갈색 투명 연질캡슐이면 color="갈색, 투명", dosage_form_hint="연질캡슐", shape는 외곽에 따라 타원형 또는 장방형

알약이 아니면 is_pill=false.
서로 다른 알약이 여러 개면 multiple_pills=true.
"""

    contents = image_contents + [{"type": "text", "text": prompt}]

    try:
        response = await client.chat.completions.create(
            model=model,
            max_tokens=600,
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


# ── STEP 6: rerank 점수 계산 (순수 함수) ───────
def _rerank_score(query: dict, candidate_meta: dict) -> float:
    """
    query: normalize_vision_result 결과
    candidate_meta: DB metadata jsonb
    반환: 0~100 점수

    원칙:
    - query가 null인 필드는 unknown — 감점 안 함
    - 각인 exact match 최우선
    - 색상은 토큰 세트 비교
    - 모양은 유사 점수 포함
    """
    score = 0.0
    sk = candidate_meta.get("search_keys") or {}
    ap = candidate_meta.get("appearance") or {}

    q_front = (query.get("front_norm") or "").upper()
    q_back = (query.get("back_norm") or "").upper()
    c_front = (sk.get("front_norm") or "").upper()
    c_back = (sk.get("back_norm") or "").upper()

    def _imprint_score(qf: str, qb: str, cf: str, cb: str) -> float:
        s = 0.0
        # query가 null이면 unknown — 감점 안 함
        if qf and cf and qf == cf:
            s += 35.0
        if qb and cb and qb == cb:
            s += 35.0
        return s

    direct = _imprint_score(q_front, q_back, c_front, c_back)
    swapped = _imprint_score(q_front, q_back, c_back, c_front)
    score += max(direct, swapped)

    # 분할선 (12점)
    imprint = candidate_meta.get("imprint") or {}
    for side_key, score_line_key in [("front", "score_line_front_type"), ("back", "score_line_back_type")]:
        side = imprint.get(side_key) or {}
        q_type = query.get(score_line_key) or "없음"
        q_has = q_type != "없음"
        q_cross = q_type == "십자분할선"
        c_has = side.get("has_score_line", False)
        c_cross = side.get("is_cross", False)
        if q_cross and c_cross:
            score += 6.0
        elif q_has == c_has:
            score += 4.0
        else:
            score -= 4.0

    # 색상 (8점) — 토큰 세트 비교
    q_color = query.get("color_norm") or ""
    c_color = ap.get("color_normalized") or ""
    if q_color and c_color:
        q_ctok = color_tokens(q_color)
        c_ctok = color_tokens(c_color)
        if q_ctok == c_ctok:
            score += 8.0
        elif q_ctok & c_ctok:
            score += 4.0

    # 모양 (8점) — 유사 점수 포함
    score += shape_match_score(query.get("shape_norm") or "", ap.get("shape_normalized") or "")

    return score


# ── needs_recheck ────────────────────────────────
def _needs_recheck(vlm: dict, top_candidates: list[dict]) -> dict:
    """
    1차 VLM 결과와 상위 후보 metadata를 비교해
    2차 VLM 호출 필요 여부를 판단.
    """
    flags: dict[str, bool] = {
        "faint_imprint_recheck": False,
        "scoreline_recheck": False,
        "cross_scoreline_recheck": False,
        "transparent_color_recheck": False,
    }

    front_norm = (vlm.get("print_front") or "").replace(" ", "")
    back_norm = (vlm.get("print_back") or "").replace(" ", "")
    total_len = len(front_norm) + len(back_norm)
    imprint_conf = vlm.get("imprint_confidence") or 0.0
    score_line_conf = vlm.get("score_line_confidence") or 0.0
    color_conf = vlm.get("color_confidence") or 0.0
    is_transparent = vlm.get("is_transparent", False)
    dosage_hint = vlm.get("dosage_form_hint") or ""

    cross_count = sum(1 for c in top_candidates if _candidate_has_cross_score_line(c.get("metadata") or {}))
    score_line_count = sum(1 for c in top_candidates if _candidate_has_score_line(c.get("metadata") or {}))
    candidate_has_imprint = any(_candidate_has_any_imprint(c.get("metadata") or {}) for c in top_candidates)

    vlm_front_type = vlm.get("score_line_front_type") or "없음"
    vlm_back_type = vlm.get("score_line_back_type") or "없음"
    vlm_has_cross = "십자분할선" in (vlm_front_type, vlm_back_type)
    vlm_has_score = vlm_front_type != "없음" or vlm_back_type != "없음"

    if cross_count >= 1 and not vlm_has_cross:
        flags["cross_scoreline_recheck"] = True
    if score_line_count >= 2 and (not vlm_has_score or score_line_conf < 0.75):
        flags["scoreline_recheck"] = True
    if (total_len <= 2 and candidate_has_imprint) or imprint_conf < 0.7:
        flags["faint_imprint_recheck"] = True
    if color_conf < 0.75 or is_transparent or dosage_hint == "연질캡슐":
        flags["transparent_color_recheck"] = True

    return flags


# ── candidate helper ────────────────────────────────
def _candidate_has_score_line(meta: dict) -> bool:
    imp = meta.get("imprint") or {}
    for side in ("front", "back"):
        s = imp.get(side) or {}
        if s.get("has_score_line"):
            return True
        if "분할선" in (s.get("raw") or ""):
            return True
    return False


def _candidate_has_cross_score_line(meta: dict) -> bool:
    imp = meta.get("imprint") or {}
    for side in ("front", "back"):
        s = imp.get(side) or {}
        if s.get("is_cross"):
            return True
        if "십자분할선" in (s.get("raw") or ""):
            return True
    return False


def _candidate_has_any_imprint(meta: dict) -> bool:
    sk = meta.get("search_keys") or {}
    return bool(sk.get("front_norm") or sk.get("back_norm"))


# ── 2차 VLM ────────────────────────────────────────
async def _second_pass_faint_imprint(
    client: AsyncOpenAI,
    model: str,
    image_b64_list: list[str],
    side: str,
) -> dict:
    """2차 VLM: 희미한 각인 전용 판독."""
    face = "앞면" if side == "front" else "뒷면"
    idx = 0 if side == "front" else min(1, len(image_b64_list) - 1)
    b64 = image_b64_list[idx]
    prompt = f"""알약 {face}의 각인만 재판독하세요. 색상/모양은 무시하세요.
- 흡릿한 음각/양각/업인트 각인을 주의 깊게 확인하세요.
- 분할선이 있으면 양쪽/위아래 영역을 모두 확인하세요.
- 이미지에 없는 문자를 만들지 마세요.
- JSON만 출력하세요.
{{
  "print_text": null,
  "raw_text": null,
  "has_score_line": false,
  "score_line_type": "없음 | 분할선 | 십자분할선 | 판독불가",
  "score_line_direction": "없음 | 세로 | 가로 | 대각선 | 십자 | 판독불가",
  "left_text": null,
  "right_text": null,
  "top_text": null,
  "bottom_text": null,
  "confidence": 0.0,
  "notes": null
}}"""
    try:
        resp = await client.chat.completions.create(
            model=model,
            max_tokens=300,
            temperature=0,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "high"}},
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
        raw = resp.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()
        return json.loads(raw)
    except Exception as e:
        logger.warning("2차 VLM faint_imprint 실패: %s", e)
        return {}


async def _second_pass_cross_scoreline(
    client: AsyncOpenAI,
    model: str,
    image_b64_list: list[str],
    side: str,
) -> dict:
    """2차 VLM: 십자분할선 전용 판독."""
    face = "앞면" if side == "front" else "뒷면"
    idx = 0 if side == "front" else min(1, len(image_b64_list) - 1)
    b64 = image_b64_list[idx]
    prompt = f"""알약 {face}의 분할선만 확인하세요. 각인/색상/모양은 무시하세요.
- + 모양 홈이 있는지 확인하세요.
- 글자가 없고 십자분할선만 있을 수 있습니다.
- 십자분할선을 각인 문자로 쓰지 마세요.
- JSON만 출력하세요.
{{
  "has_score_line": true,
  "score_line_type": "없음 | 분할선 | 십자분할선 | 판독불가",
  "score_line_direction": "없음 | 세로 | 가로 | 대각선 | 십자 | 판독불가",
  "has_text": false,
  "text": null,
  "confidence": 0.0,
  "notes": null
}}"""
    try:
        resp = await client.chat.completions.create(
            model=model,
            max_tokens=200,
            temperature=0,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "high"}},
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
        raw = resp.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()
        return json.loads(raw)
    except Exception as e:
        logger.warning("2차 VLM cross_scoreline 실패: %s", e)
        return {}


def _merge_second_pass(
    features: dict,
    recheck: dict,
    faint_result: dict | None,
    cross_result: dict | None,
    threshold: float = 0.55,
) -> dict:
    """
    2차 VLM 결과를 1차 features에 병합.
    confidence 미달이면 1차 유지.
    """
    updated = dict(features)

    # 희미한 각인 보완
    if faint_result and recheck.get("faint_imprint_recheck"):
        conf = faint_result.get("confidence") or 0.0
        if conf >= threshold:
            side = "front" if not features.get("print_front") else "back"
            key = f"print_{side}"
            raw_key = f"print_{side}_raw"
            if not updated.get(key) and faint_result.get("print_text"):
                updated[key] = faint_result["print_text"]
                updated[raw_key] = faint_result.get("raw_text")
                logger.info("2차 VLM faint_imprint 보완: %s=%s", key, updated[key])
            sl_type = faint_result.get("score_line_type")
            if sl_type and sl_type != "판독불가":
                updated[f"score_line_{side}_type"] = sl_type
                updated[f"score_line_{side}_direction"] = faint_result.get("score_line_direction", "없음")

    # 십자분할선 보완
    if cross_result and recheck.get("cross_scoreline_recheck"):
        conf = cross_result.get("confidence") or 0.0
        sl_type = cross_result.get("score_line_type") or ""
        if conf >= threshold and sl_type == "십자분할선":
            # 십자분할선이 확인된 면의 print는 null 유지
            for side in ("front", "back"):
                cur = updated.get(f"score_line_{side}_type") or "없음"
                if cur in ("없음", "분할선"):
                    updated[f"score_line_{side}_type"] = "십자분할선"
                    logger.info("2차 VLM cross_scoreline 보완: score_line_%s_type=십자분할선", side)
                    break

    return updated


# ── STEP 5: metadata 기반 후보 검색 + rerank ───
def _split_combined_imprint(features: dict) -> dict:
    """
    GPT가 앞뒷면을 한 면으로 합쳐서 반환한 경우를 보정.

    조건:
    - print_back이 없고
    - print_front에 공백으로 구분된 토큰이 정확히 2개이고
    - front_left_text/front_right_text 힌트가 각 토큰과 일치하며
    - score_line_front_type이 "없음" 또는 누락인 경우만 분리
      (분할선이 있는 경우는 한 면의 각인이 맞으므로 분리 금지)
    """
    front = features.get("print_front") or ""
    back = features.get("print_back") or ""
    score_line_type = features.get("score_line_front_type") or "없음"

    # 뒷면이 있거나, 앞면에 분할선이 있으면 분리 안 함
    if back or not front or score_line_type not in ("없음", ""):
        return features

    tokens = front.strip().split()
    if len(tokens) != 2:
        return features

    # left_text/right_text 힌트가 각 토큰과 일치하면 분리 확정
    left = (features.get("front_left_text") or "").strip()
    right = (features.get("front_right_text") or "").strip()
    if left == tokens[0] and right == tokens[1]:
        logger.info(
            "앞뒷면 합산 각인 감지 → 분리: front=%s, back=%s",
            tokens[0],
            tokens[1],
        )
        return {**features, "print_front": tokens[0], "print_back": tokens[1]}

    return features


async def find_drug_by_imprint(
    conn: asyncpg.Connection,
    client: AsyncOpenAI,
    features: dict,
    image_b64_list: list[str] | None = None,
) -> dict | None:
    # GPT가 앞뒷면을 한 면으로 합쳐서 반환한 경우 보정
    features = _split_combined_imprint(features)

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

    query_str = " ".join(parts)
    logger.info("2단계 imprint 검색 쿼리: %s", query_str)

    norm = normalize_vision_result(features)
    front_norm = norm["front_norm"] or ""
    back_norm = norm["back_norm"] or ""

    try:
        # vector 검색 (fallback 포함)
        emb_response = await client.embeddings.create(
            model="text-embedding-3-small",
            input=query_str,
        )
        vector_str = "[" + ",".join(str(v) for v in emb_response.data[0].embedding) + "]"

        vector_rows = await conn.fetch(
            """
            SELECT item_seq, item_name, chunk_text, metadata,
                   1 - (embedding <=> $1::vector) AS similarity
            FROM drug_embeddings
            WHERE chunk_type = 'imprint'
              AND embedding IS NOT NULL
            ORDER BY embedding <=> $1::vector
            LIMIT 20
            """,
            vector_str,
        )

        # metadata exact match 후보
        exact_rows: list = []
        if front_norm or back_norm:
            conditions = []
            params: list = [vector_str]
            if front_norm:
                params.append(front_norm)
                conditions.append(f"metadata->'search_keys'->>'front_norm' = ${len(params)}")
            if back_norm:
                params.append(back_norm)
                conditions.append(f"metadata->'search_keys'->>'back_norm' = ${len(params)}")

            if conditions:
                exact_rows = list(
                    await conn.fetch(
                        f"""
                        SELECT item_seq, item_name, chunk_text, metadata,
                               1 - (embedding <=> $1::vector) AS similarity
                        FROM drug_embeddings
                        WHERE chunk_type = 'imprint'
                          AND ({" AND ".join(conditions)})
                          AND embedding IS NOT NULL
                        LIMIT 10
                        """,
                        *params,
                    )
                )

            # swapped match
            if front_norm and back_norm:
                swap_rows = await conn.fetch(
                    """
                    SELECT item_seq, item_name, chunk_text, metadata,
                           1 - (embedding <=> $1::vector) AS similarity
                    FROM drug_embeddings
                    WHERE chunk_type = 'imprint'
                      AND metadata->'search_keys'->>'front_norm' = $2
                      AND metadata->'search_keys'->>'back_norm' = $3
                      AND embedding IS NOT NULL
                    LIMIT 5
                    """,
                    vector_str,
                    back_norm,
                    front_norm,
                )
                exact_rows += list(swap_rows)

        # 후보 통합 + item_seq 기준 중복 제거
        seen_seqs: set[str] = set()
        candidates: list[dict] = []
        for r in list(exact_rows) + list(vector_rows):
            if r["item_seq"] not in seen_seqs:
                seen_seqs.add(r["item_seq"])
                meta = r["metadata"] or {}
                if isinstance(meta, str):
                    try:
                        meta = json.loads(meta)
                    except Exception:
                        meta = {}
                candidates.append(
                    {
                        "item_seq": r["item_seq"],
                        "item_name": r["item_name"],
                        "chunk_text": r["chunk_text"],
                        "metadata": meta,
                        "vector_similarity": float(r["similarity"]),
                    }
                )

        if not candidates:
            logger.info("imprint 데이터 없음 (임베딩 미구축)")
            return None

        # STEP 6: rerank
        for c in candidates:
            rerank = _rerank_score(norm, c["metadata"])
            c["rerank_score"] = rerank + c["vector_similarity"] * 10
            c["rerank_base"] = rerank

        candidates.sort(key=lambda x: x["rerank_score"], reverse=True)

        top5 = ", ".join(
            f"{c['item_name']}(rerank={c['rerank_base']:.0f}, vec={c['vector_similarity']:.3f})" for c in candidates[:5]
        )
        logger.info("imprint 상위 5개 후보 (rerank 내림차순): %s", top5)

        # needs_recheck 판단 + 2차 VLM (설정값으로 켜고 끄기 가능)
        if image_b64_list and getattr(settings, "ENABLE_SECOND_PASS", False):
            recheck = _needs_recheck(features, candidates[:5])
            logger.info("needs_recheck: %s", recheck)

            faint_result: dict | None = None
            cross_result: dict | None = None
            model_name = await get_ai_model(conn)

            if recheck.get("faint_imprint_recheck") or recheck.get("scoreline_recheck"):
                side = "back" if features.get("print_front") else "front"
                faint_result = await _second_pass_faint_imprint(client, model_name, image_b64_list, side)
                logger.info("2차 VLM faint_imprint 결과: %s", faint_result)

            if recheck.get("cross_scoreline_recheck"):
                side = "front" if not features.get("print_front") else "back"
                cross_result = await _second_pass_cross_scoreline(client, model_name, image_b64_list, side)
                logger.info("2차 VLM cross_scoreline 결과: %s", cross_result)

            if faint_result or cross_result:
                features = _merge_second_pass(features, recheck, faint_result, cross_result)
                # 병합 후 norm 재계산
                norm = normalize_vision_result(features)
                for c in candidates:
                    rerank = _rerank_score(norm, c["metadata"])
                    c["rerank_score"] = rerank + c["vector_similarity"] * 10
                    c["rerank_base"] = rerank
                candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
                logger.info(
                    "2차 VLM 후 재랜크 상위: %s",
                    candidates[0]["item_name"] if candidates else "none",
                )

        best = candidates[0]

        # 임계값: rerank 10점 이상 OR vector 유사도 0.55 이상
        if best["rerank_base"] < 10.0 and best["vector_similarity"] < IMPRINT_SIMILARITY_THRESHOLD:
            logger.info(
                "imprint 매칭 실패 - rerank=%.1f, vec=%.3f\n  쿼리: %s\n  최유사 DB: %s",
                best["rerank_base"],
                best["vector_similarity"],
                query_str,
                best["chunk_text"],
            )
            return None

        logger.info(
            "imprint 매칭 성공: '%s' → '%s' (rerank=%.1f, vec=%.3f)\n  DB chunk: %s",
            query_str,
            best["item_name"],
            best["rerank_base"],
            best["vector_similarity"],
            best["chunk_text"],
        )
        return {
            "item_seq": best["item_seq"],
            "item_name": best["item_name"],
            "similarity": best["vector_similarity"],
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


# ── LLM 정제 ──────────────────────────────────
async def refine_drug_info(
    client: AsyncOpenAI,
    model: str,
    item_name: str,
    db_info: dict,
) -> dict:
    """
    RAG 원본 텍스트를 LLM으로 정제해 DB 필드 구조에 맞게 반환.
    실패 시 원본 텍스트를 그대로 반환.
    """
    raw_efficacy = db_info.get("efficacy") or ""
    raw_caution = db_info.get("caution") or ""
    raw_ingredient = db_info.get("ingredient") or ""

    if not any([raw_efficacy, raw_caution, raw_ingredient]):
        return {}

    prompt = f"""아래는 '{item_name}'의 의약품 허가정보 원문입니다.
일반 사용자가 이해하기 쉬운 한국어로 정리해주세요.

[원본 데이터]
- 유효성분: {raw_ingredient or "없음"}
- 효능효과: {raw_efficacy or "없음"}
- 주의사항: {raw_caution or "없음"}

[출력 규칙]
- 반드시 JSON만 출력하세요. 설명/마크다운/코드블록 금지.
- 각 항목은 2~4문장 이내로 요약하세요.
- 정보가 없는 항목은 null로 두세요.
- 원본에 없는 내용을 임의로 만들지 마세요.

{{
  "active_ingredients": "유효성분명 및 함량 요약",
  "efficacy": "이 약의 주요 효능과 효과",
  "usage_method": "복용법 및 용량 (원본에 있으면)",
  "warning": "복용 전 반드시 확인해야 할 경고 사항",
  "caution": "일반 주의사항 (운전, 음주, 식사 등)",
  "interactions": "함께 복용 시 주의할 약물",
  "side_effects": "발생 가능한 부작용",
  "storage_method": "보관 방법"
}}"""

    try:
        resp = await client.chat.completions.create(
            model=model,
            max_tokens=800,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()
        refined = json.loads(raw)
        logger.info("약품정보 LLM 정제 완료: %s", item_name)
        return refined
    except Exception as e:
        logger.warning("약품정보 LLM 정제 실패 (원본 사용): %s", e)
        return {
            "active_ingredients": raw_ingredient or None,
            "efficacy": raw_efficacy or None,
            "usage_method": None,
            "warning": None,
            "caution": raw_caution or None,
            "interactions": None,
            "side_effects": None,
            "storage_method": None,
        }


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

        # Clova OCR - 각인 텍스트 추출
        ocr_texts: list[str | None] = list(await asyncio.gather(*[extract_imprint_ocr(b) for b in image_bytes_list]))

        # 앞면이 숫자만이고 뒷면이 영문자면 앞뒤 swap
        if (
            len(ocr_texts) == 2
            and ocr_texts[0]
            and ocr_texts[1]
            and ocr_texts[0].replace(" ", "").isdigit()
            and any(c.isalpha() for c in ocr_texts[1])
        ):
            ocr_texts[0], ocr_texts[1] = ocr_texts[1], ocr_texts[0]
            logger.info("OCR 앞뒤 swap 적용")

        logger.info(
            "OCR 결과: front=%s, back=%s",
            ocr_texts[0] if ocr_texts else None,
            ocr_texts[1] if len(ocr_texts) > 1 else None,
        )

        # 1단계: GPT Vision
        features = await extract_pill_features(client, image_b64_list, ocr_texts, model)
        logger.info("1단계 완료: %s", features)

        if not features.get("is_pill", True):
            logger.info("알약 이미지가 아님 → 식별 불가 반환")
            result = {"product_name": "알약 이미지가 아닙니다", "gpt_model_version": model}
            analysis_id = await save_analysis_result(conn, user_id, file_id, result)
            return {"analysis_id": analysis_id, "product_name": result["product_name"], "result": result}

        if features.get("multiple_pills"):
            logger.info("여러 알약 감지 → 분석 실패 반환")
            result = {"product_name": "여러 알약 감지 - 분석 실패", "gpt_model_version": model}
            analysis_id = await save_analysis_result(conn, user_id, file_id, result)
            return {"analysis_id": analysis_id, "product_name": result["product_name"], "result": result}

        # 2단계: imprint RAG + rerank
        matched_drug = await find_drug_by_imprint(conn, client, features, image_b64_list)

        if matched_drug is None:
            logger.info("2단계 매칭 실패 → 각인 정보만 저장")
            parts = [v for v in [features.get("print_front"), features.get("print_back")] if v]
            product_name = f"각인: {', '.join(parts)} (DB 미매칭)" if parts else "식별 불가"
            result = {"product_name": product_name, "gpt_model_version": model}
            analysis_id = await save_analysis_result(conn, user_id, file_id, result)
            return {"analysis_id": analysis_id, "product_name": result["product_name"], "result": result}

        # 3단계: 허가정보 DB 직접 조회 + LLM 정제
        db_info = await fetch_drug_info_from_db(conn, matched_drug["item_seq"])
        logger.info("3단계 완료: item_seq=%s, 조회 필드=%s", matched_drug["item_seq"], list(db_info.keys()))

        refined = await refine_drug_info(client, model, matched_drug["item_name"], db_info)

        result = {
            "product_name": matched_drug["item_name"],
            "active_ingredients": refined.get("active_ingredients"),
            "efficacy": refined.get("efficacy"),
            "usage_method": refined.get("usage_method"),
            "warning": refined.get("warning"),
            "caution": refined.get("caution"),
            "interactions": refined.get("interactions"),
            "side_effects": refined.get("side_effects"),
            "storage_method": refined.get("storage_method"),
            "gpt_model_version": model,
        }

        analysis_id = await save_analysis_result(conn, user_id, file_id, result)
        logger.info("분석 완료: analysis_id=%s, product_name=%s", analysis_id, result["product_name"])

        return {"analysis_id": analysis_id, "product_name": result["product_name"], "result": result}

    finally:
        await conn.close()
