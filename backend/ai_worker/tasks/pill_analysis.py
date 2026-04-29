# ai_worker/tasks/pill_analysis.py
# ──────────────────────────────────────────────
# 알약 분석 작업 핸들러 — v4 반영
#
# [3단계 흐름]
# 1단계: Clova OCR (각인 텍스트 추출) + GPT Vision
# 2단계: imprint RAG (metadata exact/swapped + vector)
#        → rerank → 조건부 2차 VLM
# 3단계: 허가정보 DB 직접 조회 + LLM 정제
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
from ai_worker.tasks.imprint_parser import (
    candidate_side_has_mark,
    color_tokens,
    mark_match_score,
    normalize_vision_result,
    shape_match_score,
)

logger = setup_logger("task.pill_analysis")
settings = get_worker_settings()

MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
TARGET_SIZE = 1024
IMPRINT_SIMILARITY_THRESHOLD = 0.55

# v4 설정값 (config에 없으면 기본값 사용)
VLM_MAX_TOKENS: int = getattr(settings, "VLM_MAX_TOKENS", 700)
ENABLE_SECOND_PASS: bool = getattr(settings, "ENABLE_SECOND_PASS", False)
SECOND_PASS_THRESHOLD: float = getattr(settings, "SECOND_PASS_THRESHOLD", 0.55)

SPECKLE_KEYWORDS = ["반점", "점박이", "검은 점", "갈색 점", "얼룩", "speckle", "spot", "dot"]
AMBIGUOUS_MARK_CHARS: set[str] = {"5", "S", "JS", "J5", "1", "I", "L", "7"}

# v5.1: 마크 오인 가능 각인 집합 (AMBIGUOUS_MARK_CHARS 확장)
MARK_CONFUSABLE_IMPRINTS: set[str] = {"5", "S", "JS", "J5", "15", "1S", "I5", "IS", "J", "L5"}

# v5.1: VLM color 정규화 alias
_COLOR_ALIAS: dict[str, str] = {
    "녹색": "초록",
    "초록색": "초록",
    "그린": "초록",
    "green": "초록",
    "흰색": "하양",
    "백색": "하양",
    "화이트": "하양",
    "white": "하양",
    "노란색": "노랑",
    "황색": "노랑",
    "yellow": "노랑",
    "브라운": "갈색",
    "brown": "갈색",
    "검정색": "검정",
    "black": "검정",
}


def normalize_color_name(color: str | None) -> str | None:
    if not color:
        return None
    c = str(color).strip()
    return _COLOR_ALIAS.get(c, c)


def is_mark_confusable_imprint(text: str | None) -> bool:
    if not text:
        return False
    t = str(text).strip().upper().replace(" ", "")
    return t in MARK_CONFUSABLE_IMPRINTS


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


# ── Clova OCR ─────────────────────────────────
async def _ocr_request(client: httpx.AsyncClient, image_bytes: bytes) -> str:
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
    """원본 + 180도 회전 OCR 병합 반환."""
    if not settings.OCR_INVOKE_URL or not settings.OCR_SECRET_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            normal, rotated = await asyncio.gather(
                _ocr_request(client, image_bytes),
                _ocr_request(client, _rotate_180(image_bytes)),
            )
        logger.info("Clova OCR 결과: normal=%s, rotated=%s", normal, rotated)
        seen: set[str] = set()
        merged: list[str] = []
        for t in (normal.split() if normal else []) + (rotated.split() if rotated else []):
            if t not in seen:
                seen.add(t)
                merged.append(t)
        result = " ".join(merged) or None
        logger.info("Clova OCR 병합 결과: %s", result)
        return result
    except Exception as e:
        logger.warning("Clova OCR 실패 (무시): %s", e)
        return None


# ── OCR 힌트 약화 (v4) ────────────────────────
def should_pass_ocr_to_llm(text: str | None) -> bool:
    if not text:
        return False
    t = str(text).strip()
    if not t or len(t) <= 1:
        return False
    return t not in {"-", "_", "|", "/", "\\", ".", ",", "·", "ㆍ"}


def build_ocr_hint(text: str | None) -> str:
    if not should_pass_ocr_to_llm(text):
        return "OCR 없음 또는 불완전"
    return (
        f"OCR 참고값: {text}. "
        "OCR은 분할선, 십자분할선, 마크, 희미한 각인, 반점이 있는 알약에서 틀릴 수 있다. "
        "이미지를 우선 판단하라."
    )


# -- speckle/mark helper (v5) --
def has_speckle_hint(vlm_result: dict) -> bool:
    text = " ".join(
        [
            str(vlm_result.get("color_detail") or ""),
            str(vlm_result.get("notes") or ""),
        ]
    )
    return any(kw in text for kw in SPECKLE_KEYWORDS)


def _append_note(old: str | None, new: str) -> str:
    return f"{old} / {new}" if old else new


def calibrate_vlm_confidence(vlm: dict) -> dict:
    """
    VLM confidence over-confidence correction (v5).
    Caps confidence when speckle/mark misread is likely.
    """
    result = dict(vlm)
    imprint_conf = float(result.get("imprint_confidence") or 0)
    score_line_conf = float(result.get("score_line_confidence") or 0)
    color_conf = float(result.get("color_confidence") or 0)

    if has_speckle_hint(result):
        result["imprint_confidence"] = min(imprint_conf, 0.65)
        result["color_confidence"] = min(color_conf, 0.75)
        if result.get("score_line_front_type") in {"분할선", "십자분할선"} or result.get("score_line_back_type") in {
            "분할선",
            "십자분할선",
        }:
            result["score_line_confidence"] = min(score_line_conf, 0.35)
            result["notes"] = _append_note(result.get("notes"), "반점/음영을 분할선으로 오인했을 가능성 있음")

    if has_speckle_hint(result) and result.get("color") in {"갈색", "검정", "검정색"}:
        result["color_confidence"] = min(float(result.get("color_confidence") or 0), 0.55)
        result["notes"] = _append_note(result.get("notes"), "반점 색상을 기본색으로 오인했을 가능성 있음")

    suspicious = {"5", "S", "JS", "J5", "15", "1S", "I5"}
    pf = str(result.get("print_front") or "").strip()
    pb = str(result.get("print_back") or "").strip()
    if pf in suspicious or pb in suspicious:
        result["imprint_confidence"] = min(float(result.get("imprint_confidence") or 0), 0.65)
        result["notes"] = _append_note(result.get("notes"), "짧은 문자/숫자가 마크 또는 로고일 가능성 있음")

    for key in ["imprint_confidence", "score_line_confidence", "color_confidence", "shape_confidence"]:
        if result.get(key) is not None:
            result[key] = min(float(result[key]), 0.95)

    return result


def normalize_multiple_pills_flag(vlm: dict) -> dict:
    """
    Same pill front/back in one image: correct multiple_pills=True to False.
    """
    result = dict(vlm)
    if result.get("multiple_pills") is True:
        if (
            bool(result.get("color"))
            and bool(result.get("shape"))
            and bool(result.get("print_front") or result.get("print_back"))
        ):
            result["multiple_pills"] = False
            result["notes"] = _append_note(
                result.get("notes"),
                "동일 색상/모양의 두 면 이미지로 판단하여 multiple_pills=false로 보정",
            )
    return result


def build_mark_hypothesis_variants(vlm: dict) -> list[str]:
    """
    VLM이 마크/로고를 JS, 5, S 등으로 잘못 읽은 경우를 대비해
    '마크' 가설 RAG query를 생성한다.
    VLM 결과 자체는 변경하지 않는다.
    """
    variants: list[str] = []
    front = vlm.get("print_front")
    back = vlm.get("print_back")
    color = normalize_color_name(vlm.get("color"))
    shape = vlm.get("shape")

    def _add(parts: list) -> None:
        q = " ".join(str(p) for p in parts if p)
        if q and q not in variants:
            variants.append(q)

    if is_mark_confusable_imprint(front):
        _add(["마크", back, color, shape])
        _add([back, "마크", color, shape])
        _add(["마크", color, shape])
        if back:
            _add([back, color, shape])

    if is_mark_confusable_imprint(back):
        _add([front, "마크", color, shape])
        _add(["마크", front, color, shape])
        _add(["마크", color, shape])
        if front:
            _add([front, color, shape])

    return variants


def build_rag_query_variants(vlm: dict) -> list[str]:
    """
    Build search variants including single-side imprint queries
    and mark hypothesis variants (v5.1).
    """
    from ai_worker.tasks.imprint_parser import (
        _normalize_color,
        _normalize_imprint,
        _normalize_shape,
    )

    front = vlm.get("print_front")
    back = vlm.get("print_back")
    color = normalize_color_name(vlm.get("color"))
    shape = vlm.get("shape")

    fn = _normalize_imprint(front.strip().upper()) if front else None
    bn = _normalize_imprint(back.strip().upper()) if back else None
    cn = _normalize_color(color or "")
    sn = _normalize_shape(shape or "")
    cs = f"{cn} {sn}".strip()

    variants: list[str] = []

    def _add(parts: list) -> None:
        q = " ".join(p for p in parts if p)
        if q and q not in variants:
            variants.append(q)

    # 기존 기본 variants
    _add([fn, bn, cs])
    _add([bn, fn, cs])
    _add([fn, cs])
    _add([bn, cs])
    _add([cs])

    # v5.1: 마크 hypothesis variants
    for q in build_mark_hypothesis_variants({**vlm, "color": color}):
        if q not in variants:
            variants.append(q)

    return variants


# ── 1차 VLM 프롬프트 (v4) ─────────────────────
PILL_VISION_PROMPT = """
너는 알약 이미지에서 각인, 색상, 모양, 분할선을 추출한다.
반드시 JSON만 출력한다. 마크다운, 설명문, 코드블록 금지.

[기본 원칙]
- OCR은 참고값일 뿐이며 이미지가 우선이다.
- 보이는 것만 기록하고 추측하지 않는다.
- 확실하지 않은 각인은 null로 두거나 낮은 confidence로 기록한다.
- 제조사 로고, 심볼, 비문자 도안은 "마크"로 기록한다.
- 점, 얼룩, 반점, 점박이 무늬, 재질 무늬는 각인이 아니다. color_detail 또는 notes에만 기록한다.

[각인 판독]
- print_front/print_back에는 실제 문자, 숫자, 또는 "마크"만 기록한다.
- "분할선", "십자분할선"이라는 단어는 print_front/print_back에 넣지 않는다.
- 분할선 주변에 문자가 있으면 해당 문자는 print_* 및 left/right/top/bottom 필드에 기록한다.
- 예: 1분할선3처럼 보이면 print는 "1 3", left_text="1", right_text="3".
- 마크가 5, S, JS, 곡선 문자처럼 보여도 문자로 확실하지 않으면 "마크"로 기록한다.
- 원형 알약은 회전 때문에 문자 방향이 애매할 수 있으므로 0/90/180/270도 방향을 고려한다.

[OCR 혼동 보정]
- 다음 혼동은 이미지에서 명확할 때만 보정한다: H↔N, 0↔O, 1↔I↔L, 5↔S, 6↔G, 8↔B, 2↔Z.
- OCR 결과가 한 글자이거나 기호뿐이면 신뢰하지 않는다.

[분할선]
- 선 하나가 있으면 "분할선"이다.
- 세로 분할선이면 left/right, 가로 분할선이면 top/bottom을 확인한다.
- 분할선 양쪽에 문자가 있을 수 있으므로 한쪽만 읽고 끝내지 않는다.
- 분할선은 각인 문자가 아니므로 print_*에 "분할선"을 넣지 않는다.

[십자분할선]
- + 모양으로 가로선과 세로선이 함께 있으면 "십자분할선"이다.
- 십자분할선은 텍스트가 없어도 반드시 기록한다.
- 십자분할선이 있으면 direction은 "십자"로 둔다.
- 점, 얼룩, 그림자, 알약 가장자리 선은 십자분할선이 아니다.

[색상]
- color는 알약 본체의 기본 색상이다.
- 반점, 검은 점, 갈색 점, 얼룩은 color_detail에만 기록한다.
- 예: 노란 알약에 검정/갈색 반점이 있으면 color="노랑", color_detail="검정/갈색 반점 있음".
- 두 색 경질캡슐은 "/"로 기록. 예: "갈색/하양".
- 투명 연질캡슐은 ", 투명"으로 기록. 예: "갈색, 투명".
- "반투명"은 쓰지 말고 "투명"으로만 기록한다.

[모양]
- shape는 아래 중 하나만 선택한다: "원형", "타원형", "장방형", "삼각형", "사각형", "기타", "판독불가".
- "캡슐형"은 shape로 쓰지 않는다. 캡슐 여부는 dosage_form_hint에 기록한다.
- 긴 직선 측면이면 "장방형", 전체가 연속 곡선이면 "타원형", 원에 가까우면 "원형".
- 타원형과 장방형은 자주 혼동되므로 외곽 윤곽을 우선한다.

[출력 JSON]
{
  "is_pill": true,
  "multiple_pills": false,
  "print_front": null,
  "print_back": null,
  "score_line_front_type": "없음|분할선|십자분할선|판독불가",
  "score_line_back_type": "없음|분할선|십자분할선|판독불가",
  "score_line_front_direction": "없음|세로|가로|십자|판독불가",
  "score_line_back_direction": "없음|세로|가로|십자|판독불가",
  "front_left_text": null,
  "front_right_text": null,
  "front_top_text": null,
  "front_bottom_text": null,
  "back_left_text": null,
  "back_right_text": null,
  "back_top_text": null,
  "back_bottom_text": null,
  "color": null,
  "color_detail": null,
  "shape": null,
  "dosage_form_hint": "정제|경질캡슐|연질캡슐|판독불가",
  "imprint_confidence": 0.0,
  "score_line_confidence": 0.0,
  "color_confidence": 0.0,
  "shape_confidence": 0.0,
  "notes": null
}
"""


async def extract_pill_features(
    client: AsyncOpenAI,
    image_b64_list: list[str],
    ocr_texts: list[str | None],
    model: str,
) -> dict:
    image_contents = []
    for i, b64 in enumerate(image_b64_list):
        face = "앞면" if i == 0 else "뒷면"
        ocr_hint = build_ocr_hint(ocr_texts[i] if i < len(ocr_texts) else None)
        # detail:high — 각인 판독 정확도 향상. low 대비 토큰 비용 약 3~4배 증가.
        image_contents.append(
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "high"}}
        )
        image_contents.append({"type": "text", "text": f"위 이미지는 알약의 {face}입니다. {ocr_hint}"})

    contents = image_contents + [{"type": "text", "text": PILL_VISION_PROMPT}]

    try:
        response = await client.chat.completions.create(
            model=model,
            max_tokens=VLM_MAX_TOKENS,
            temperature=0,
            response_format={"type": "json_object"},
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


# ── candidate helpers (v4) ────────────────────
def _candidate_has_score_line(meta: dict, side: str | None = None) -> bool:
    imp = meta.get("imprint") or {}
    sides = [side] if side else ["front", "back"]
    for s in sides:
        sd = imp.get(s) or {}
        if sd.get("has_score_line"):
            return True
        raw = sd.get("raw") or ""
        if "분할선" in raw:
            return True
        if meta.get(f"print_{s}") and "분할선" in str(meta.get(f"print_{s}")):
            return True
    return False


def _candidate_has_cross_score_line(meta: dict, side: str | None = None) -> bool:
    imp = meta.get("imprint") or {}
    sides = [side] if side else ["front", "back"]
    for s in sides:
        sd = imp.get(s) or {}
        if sd.get("is_cross"):
            return True
        raw = sd.get("raw") or ""
        if "십자분할선" in raw:
            return True
        if meta.get(f"print_{s}") and "십자분할선" in str(meta.get(f"print_{s}")):
            return True
    return False


def _candidate_has_any_imprint(meta: dict) -> bool:
    sk = meta.get("search_keys") or {}
    return bool(sk.get("front_norm") or sk.get("back_norm"))


# ── rerank 점수 계산 (v4 보강) ────────────────
def _rerank_score(query: dict, candidate_meta: dict) -> float:
    """
    query: normalize_vision_result 결과
    candidate_meta: DB metadata jsonb
    - query null 필드는 unknown → 감점 안 함
    - 마크 매칭 포함
    - 십자분할선/분할선 점수 보강
    - 색상 토큰 비교, 모양 유사 점수
    """
    score = 0.0
    sk = candidate_meta.get("search_keys") or {}
    ap = candidate_meta.get("appearance") or {}

    q_front = (query.get("front_norm") or "").upper()
    q_back = (query.get("back_norm") or "").upper()
    c_front = (sk.get("front_norm") or "").upper()
    c_back = (sk.get("back_norm") or "").upper()

    def _side_score(qv: str, cv: str, meta: dict, side: str) -> float:
        if not qv:
            return 0.0  # unknown — 감점 안 함
        # 마크 매칭 (정확 35점, suspicious 문자 18점)
        ms = mark_match_score(qv, meta, side)
        if ms > 0:
            return ms
        if qv and cv and qv == cv:
            return 35.0
        return 0.0

    direct = _side_score(q_front, c_front, candidate_meta, "front") + _side_score(
        q_back, c_back, candidate_meta, "back"
    )
    swapped = _side_score(q_front, c_back, candidate_meta, "back") + _side_score(
        q_back, c_front, candidate_meta, "front"
    )
    score += max(direct, swapped)

    # 분할선/십자분할선 점수 (v4: 방향 강제 안 함, 존재 여부 중심)
    q_front_type = query.get("score_line_front_type") or "없음"
    q_back_type = query.get("score_line_back_type") or "없음"
    q_has_cross = "십자분할선" in (q_front_type, q_back_type)
    q_has_line = q_front_type != "없음" or q_back_type != "없음"

    c_has_cross = _candidate_has_cross_score_line(candidate_meta)
    c_has_line = _candidate_has_score_line(candidate_meta)

    if q_has_cross and c_has_cross:
        score += 12.0
    elif q_has_cross and c_has_line:
        score += 6.0
    elif q_has_line and c_has_line:
        score += 8.0

    # 색상 (8점) — 토큰 세트 비교, 반점 색상 제외
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


# ── needs_recheck (v4) ────────────────────────
def _needs_recheck(vlm: dict, top_candidates: list[dict]) -> dict:
    flags: dict[str, bool] = {
        "faint_imprint_recheck": False,
        "scoreline_recheck": False,
        "cross_scoreline_recheck": False,
        "mark_recheck": False,
    }

    front_norm = (vlm.get("print_front") or "").replace(" ", "")
    back_norm = (vlm.get("print_back") or "").replace(" ", "")
    total_len = len(front_norm) + len(back_norm)
    imprint_conf = float(vlm.get("imprint_confidence") or 0.0)
    score_line_conf = float(vlm.get("score_line_confidence") or 0.0)

    vlm_front_type = vlm.get("score_line_front_type") or "없음"
    vlm_back_type = vlm.get("score_line_back_type") or "없음"
    vlm_has_cross = "십자분할선" in (vlm_front_type, vlm_back_type)
    vlm_has_line = vlm_front_type != "없음" or vlm_back_type != "없음"

    cross_count = sum(1 for c in top_candidates if _candidate_has_cross_score_line(c.get("metadata") or {}))
    line_count = sum(1 for c in top_candidates if _candidate_has_score_line(c.get("metadata") or {}))
    candidate_has_imprint = any(_candidate_has_any_imprint(c.get("metadata") or {}) for c in top_candidates)
    candidate_has_mark = any(
        candidate_side_has_mark(c.get("metadata") or {}, s) for c in top_candidates for s in ("front", "back")
    )

    if cross_count >= 1 and not vlm_has_cross:
        flags["cross_scoreline_recheck"] = True
    if line_count >= 2 and (not vlm_has_line or score_line_conf < 0.6):
        flags["scoreline_recheck"] = True
    if (total_len <= 2 and candidate_has_imprint) or imprint_conf < 0.65:
        flags["faint_imprint_recheck"] = True
    if has_speckle_hint(vlm):
        flags["faint_imprint_recheck"] = True
    # 마크 재검사: 후보에 마크가 있는데 VLM이 애매한 문자로 읽은 경우
    q_vals = {str(vlm.get("print_front") or "").strip(), str(vlm.get("print_back") or "").strip()}
    if candidate_has_mark and bool(q_vals & AMBIGUOUS_MARK_CHARS):
        flags["mark_recheck"] = True

    return flags


# ── 2차 VLM 프롬프트 ──────────────────────────
_SCORELINE_RECHECK_PROMPT = """알약의 분할선만 다시 확인한다. 각인/색상/모양은 무시한다.
반드시 JSON만 출력한다.
규칙: 직선 하나는 "분할선", + 모양은 "십자분할선". 십자분할선은 텍스트가 없어도 반드시 기록한다.
{
  "front_score_line_type": "없음|분할선|십자분할선|판독불가",
  "back_score_line_type": "없음|분할선|십자분할선|판독불가",
  "front_direction": "없음|세로|가로|십자|판독불가",
  "back_direction": "없음|세로|가로|십자|판독불가",
  "front_left_text": null, "front_right_text": null,
  "front_top_text": null, "front_bottom_text": null,
  "back_left_text": null, "back_right_text": null,
  "back_top_text": null, "back_bottom_text": null,
  "score_line_confidence": 0.0,
  "notes": null
}"""

_FAINT_IMPRINT_RECHECK_PROMPT = """알약의 희미한 각인만 다시 확인한다. 색상/모양은 무시한다.
반드시 JSON만 출력한다.
규칙: 반점/얼룩/점박이 무늬는 각인이 아니다. 눌린 자국, 음각/양각 문자만 각인이다.
문자/숫자가 확실하지 않으면 null. 로고/심볼이면 "마크".
{
  "print_front": null, "print_back": null,
  "front_candidates": [], "back_candidates": [],
  "imprint_confidence": 0.0,
  "notes": null
}"""

_MARK_RECHECK_PROMPT = """알약 표면 표시가 문자/숫자인지 마크/로고인지 확인한다.
반드시 JSON만 출력한다.
규칙: 곡선, 심볼, 회사 로고처럼 보이고 문자로 확정할 수 없으면 "마크"로 기록한다.
원형 알약의 곡선 마크는 5, S, JS처럼 보일 수 있다. 확실하지 않으면 "마크"로 둔다.
{
  "print_front": null, "print_back": null,
  "front_is_mark": false, "back_is_mark": false,
  "confidence": 0.0,
  "notes": null
}"""


async def _call_second_pass(
    client: AsyncOpenAI,
    model: str,
    image_b64_list: list[str],
    prompt: str,
    max_tokens: int = 300,
) -> dict:
    """공통 2차 VLM 호출."""
    contents: list[dict] = []
    for i, b64 in enumerate(image_b64_list):
        face = "앞면" if i == 0 else "뒷면"
        contents.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "high"}})
        contents.append({"type": "text", "text": f"위 이미지는 알약의 {face}입니다."})
    contents.append({"type": "text", "text": prompt})
    try:
        resp = await client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            temperature=0,
            messages=[{"role": "user", "content": contents}],
        )
        raw = resp.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()
        return json.loads(raw)
    except Exception as e:
        logger.warning("2차 VLM 호출 실패: %s", e)
        return {}


def merge_recheck_result(base: dict, recheck: dict, kind: str, threshold: float = 0.55) -> dict:
    """2차 VLM 결과를 confidence 기준으로 1차 결과에 병합."""
    result = dict(base)

    if kind == "faint_imprint":
        conf = float(recheck.get("imprint_confidence") or 0)
        base_conf = float(base.get("imprint_confidence") or 0)
        if conf >= threshold and conf >= base_conf:
            if recheck.get("print_front") and not result.get("print_front"):
                result["print_front"] = recheck["print_front"]
            if recheck.get("print_back") and not result.get("print_back"):
                result["print_back"] = recheck["print_back"]
            result["imprint_confidence"] = conf

    elif kind == "scoreline":
        conf = float(recheck.get("score_line_confidence") or 0)
        if conf >= threshold:
            result["score_line_front_type"] = recheck.get("front_score_line_type", result.get("score_line_front_type"))
            result["score_line_back_type"] = recheck.get("back_score_line_type", result.get("score_line_back_type"))
            result["score_line_front_direction"] = recheck.get(
                "front_direction", result.get("score_line_front_direction")
            )
            result["score_line_back_direction"] = recheck.get("back_direction", result.get("score_line_back_direction"))
            result["score_line_confidence"] = conf

    elif kind == "mark":
        conf = float(recheck.get("confidence") or 0)
        if conf >= threshold:
            if recheck.get("front_is_mark"):
                result["print_front"] = "마크"
            elif recheck.get("print_front"):
                result["print_front"] = recheck["print_front"]
            if recheck.get("back_is_mark"):
                result["print_back"] = "마크"
            elif recheck.get("print_back"):
                result["print_back"] = recheck["print_back"]
            result["imprint_confidence"] = max(float(result.get("imprint_confidence") or 0), conf)

    notes = []
    if base.get("notes"):
        notes.append(str(base["notes"]))
    if recheck.get("notes"):
        notes.append(f"{kind}: {recheck['notes']}")
    result["notes"] = " / ".join(notes) if notes else None

    return result


# ── 매칭 실패 판단 (v4) ───────────────────────
# 색상 유사 그룹 — 같은 그룹 내면 유사 색상으로 처리
_COLOR_GROUPS: list[set[str]] = [
    {"하양", "아이보리"},
    {"노랑", "연노랑", "아이보리", "갈색", "주황"},
    {"분홍", "빨강", "주황"},
    {"초록", "연두"},
    {"파랑", "보라"},
    {"회색", "검정", "하양"},
]


def _is_color_similar(c1: str, c2: str) -> bool:
    """두 색상이 같거나 같은 유사 그룹에 속하면 True.
    GPT가 노랑을 연한 갈색으로 보는 등의 케이스를 허용.
    """
    if not c1 or not c2:
        return True  # 한쪽이 없으면 판단 보류
    if c1 == c2:
        return True
    return any(c1 in group and c2 in group for group in _COLOR_GROUPS)


def should_return_match_failure(
    best_candidate: dict | None,
    second_candidate: dict | None,
    vlm_result: dict,
    best_score: float,
) -> tuple[bool, str]:
    if not best_candidate:
        return True, "RAG 후보 없음"

    imprint_conf = float(vlm_result.get("imprint_confidence") or 0)
    sk = (best_candidate.get("metadata") or {}).get("search_keys") or {}
    ap = (best_candidate.get("metadata") or {}).get("appearance") or {}

    q_back = (vlm_result.get("print_back") or "").strip().upper()
    c_back = (sk.get("back_norm") or "").upper()
    q_color = (vlm_result.get("color") or "").strip()
    c_color = (ap.get("color_normalized") or "").strip()

    back_mismatch = bool(q_back and c_back and q_back != c_back)

    color_conf = float(vlm_result.get("color_confidence") or 0)
    color_clearly_different = (
        bool(q_color and c_color) and not _is_color_similar(q_color, c_color) and color_conf >= 0.7
    )

    shape_conf = float(vlm_result.get("shape_confidence") or 0)
    q_shape = (vlm_result.get("shape") or "").strip()
    c_shape = (ap.get("shape_normalized") or "").strip()
    shape_clearly_different = (
        bool(q_shape and c_shape)
        and q_shape != c_shape
        and shape_match_score(q_shape, c_shape) == 0.0
        and shape_conf >= 0.7
    )

    if back_mismatch and color_clearly_different:
        return True, (f"뒷면 각인 불일치({q_back}≠{c_back}) + 색상 불일치({q_color}≠{c_color})")

    # 색상 + 모양 동시 불일치 실패
    if color_clearly_different and shape_clearly_different:
        return True, (f"색상 불일치({q_color}≠{c_color}) + 모양 불일치({q_shape}≠{c_shape})")

    return False, ""


# ── 앞뒷면 합산 각인 분리 보정 ────────────────
def _split_combined_imprint(features: dict) -> dict:
    front = features.get("print_front") or ""
    back = features.get("print_back") or ""
    score_line_type = features.get("score_line_front_type") or "없음"

    if back or not front or score_line_type not in ("없음", ""):
        return features

    tokens = front.strip().split()
    if len(tokens) != 2:
        return features

    left = (features.get("front_left_text") or "").strip()
    right = (features.get("front_right_text") or "").strip()
    if left == tokens[0] and right == tokens[1]:
        logger.info("앞뒷면 합산 각인 감지 → 분리: front=%s, back=%s", tokens[0], tokens[1])
        return {**features, "print_front": tokens[0], "print_back": tokens[1]}

    return features


# ── 2단계: imprint RAG + rerank ───────────────
# ── v5.1: candidate visual verification helpers ──────────────────────────
_CANDIDATE_VISUAL_VERIFY_PROMPT = """
너는 알약 이미지가 주어진 후보 의약품 metadata와 시각적으로 일치하는지 검증한다.
반드시 JSON만 출력한다.

[마크 검증 추가 규칙]
- 후보 metadata에 "마크"가 있고 이미지 표시가 JS, 5, S, 15처럼 보이면,
  그것이 실제 문자라기보다 로고/마크가 회전되어 보이는 것인지 판단하라.
- 원형 알약의 로고/마크는 회전 방향에 따라 JS, 5, S처럼 보일 수 있다.
- 후보가 "마크 + 10"이고 이미지 한 면이 10, 다른 면이 곡선형 로고라면
  "마크 + 10" 후보를 지지할 수 있다.
- 실제로 J와 S의 독립된 문자 획이 명확하지 않으면 "마크"로 보는 것이 안전하다.
- 단, 후보 목록에 실제 "JS" 각인 후보가 있고 이미지에서 J와 S가 명확하면 JS 후보를 지지하라.

후보 metadata를 보고 다음을 판단하라:
1. 후보의 색상과 이미지 기본 색상이 맞는가?
2. 후보의 모양과 이미지 모양이 맞는가?
3. 후보의 각인/마크/분할선이 이미지에서 시각적으로 지지되는가?
4. VLM이 읽은 문자보다 후보의 "마크" 해석이 더 자연스러운가?

출력:
{
  "best_candidate_index": null,
  "supported": false,
  "confidence": 0.0,
  "visual_findings": {
    "front": null,
    "back": null,
    "front_is_mark": false,
    "back_is_mark": false,
    "color": null,
    "shape": null
  },
  "reason": null,
  "warnings": []
}
"""


def compact_candidate_for_verify(candidate: dict, index: int) -> dict:
    md = candidate.get("metadata") or {}
    return {
        "index": index,
        "item_seq": md.get("item_seq") or candidate.get("item_seq"),
        "item_name": md.get("item_name") or candidate.get("item_name"),
        "print_front": md.get("print_front"),
        "print_back": md.get("print_back"),
        "front_raw": ((md.get("imprint") or {}).get("front") or {}).get("raw"),
        "back_raw": ((md.get("imprint") or {}).get("back") or {}).get("raw"),
        "front_norm": (md.get("search_keys") or {}).get("front_norm"),
        "back_norm": (md.get("search_keys") or {}).get("back_norm"),
        "color": (md.get("appearance") or {}).get("color_normalized"),
        "shape": (md.get("appearance") or {}).get("shape_normalized"),
        "size": (md.get("size") or {}).get("raw"),
    }


def should_force_mark_visual_verification(vlm: dict, candidates: list[dict]) -> bool:
    """Part 6: 마크 hypothesis 후보가 있으면 visual verification 강제 실행."""
    q_values = {
        str(vlm.get("print_front") or "").strip().upper().replace(" ", ""),
        str(vlm.get("print_back") or "").strip().upper().replace(" ", ""),
    }
    if not any(v in MARK_CONFUSABLE_IMPRINTS for v in q_values):
        return False
    for candidate in candidates[:10]:
        metadata = candidate.get("metadata") or {}
        if candidate_side_has_mark(metadata, "front") or candidate_side_has_mark(metadata, "back"):
            return True
    return False


def apply_mark_hypothesis_if_verified(
    vlm: dict,
    verify: dict,
    selected_candidate: dict,
) -> dict:
    """Part 8: verification 결과가 마크를 지지하면 VLM 결과 보정."""
    result = dict(vlm)
    if not verify or not verify.get("supported"):
        return result
    if float(verify.get("confidence") or 0) < 0.55:
        return result

    metadata = selected_candidate.get("metadata") or {}
    findings = verify.get("visual_findings") or {}

    if candidate_side_has_mark(metadata, "front") and findings.get("front_is_mark"):
        result["print_front"] = "마크"
    elif findings.get("front") and findings["front"] != "마크":
        result["print_front"] = findings["front"]

    if candidate_side_has_mark(metadata, "back") and findings.get("back_is_mark"):
        result["print_back"] = "마크"
    elif findings.get("back") and findings["back"] != "마크":
        result["print_back"] = findings["back"]

    result["imprint_confidence"] = min(
        max(float(result.get("imprint_confidence") or 0), float(verify.get("confidence") or 0)),
        0.85,
    )
    result["notes"] = _append_note(result.get("notes"), "마크 hypothesis verification으로 각인 보정")
    return result


def should_enable_mark_hypothesis(vlm: dict, exact_candidates: list[dict]) -> bool:
    """Part 9: 정확한 JS 후보가 강하면 마크 hypothesis를 약하게만 사용."""
    if not (is_mark_confusable_imprint(vlm.get("print_front")) or is_mark_confusable_imprint(vlm.get("print_back"))):
        return False
    if not exact_candidates:
        return True
    best_score = max(float(c.get("score") or c.get("vector_similarity") or 0) for c in exact_candidates)
    return best_score < 0.75


async def _run_candidate_visual_verification(
    client,
    model: str,
    image_b64_list: list[str],
    candidates: list[dict],
) -> dict:
    """Part 6: top 3~5 후보를 압축해서 VLM에 전달하고 visual verification 수행."""
    compact = [compact_candidate_for_verify(c, i) for i, c in enumerate(candidates[:5])]
    prompt = _CANDIDATE_VISUAL_VERIFY_PROMPT + "\n\n후보 목록:\n" + json.dumps(compact, ensure_ascii=False, indent=2)
    return await _call_second_pass(client, model, image_b64_list, prompt, max_tokens=400)


async def _search_mark_hypothesis_metadata(
    conn,
    vector_str: str,
    stable_imprint: str,
    color: str,
    shape: str,
    limit: int = 20,
) -> list:
    """
    v5.1: DB metadata JSONB에서 마크 + stable_imprint + color + shape 조건으로 직접 검색.
    DB schema 변경 없음. parameter binding 사용.
    """
    if not stable_imprint:
        return []
    try:
        rows = await conn.fetch(
            """
            SELECT item_seq, item_name, chunk_text, metadata,
                   1 - (embedding <=> $1::vector) AS similarity
            FROM drug_embeddings
            WHERE chunk_type = 'imprint'
              AND (
                metadata->'search_keys'->>'front_norm' = '마크'
                OR metadata->'search_keys'->>'back_norm' = '마크'
                OR metadata->>'print_front' = '마크'
                OR metadata->>'print_back' = '마크'
              )
              AND (
                metadata->'search_keys'->>'front_norm' = $2
                OR metadata->'search_keys'->>'back_norm' = $2
                OR metadata->>'print_front' = $2
                OR metadata->>'print_back' = $2
              )
              AND (
                metadata->'appearance'->>'color_normalized' = $3
                OR metadata->'source'->>'raw_color' = $3
              )
              AND (
                metadata->'appearance'->>'shape_normalized' = $4
                OR metadata->>'drug_shape' = $4
              )
              AND embedding IS NOT NULL
            ORDER BY embedding <=> $1::vector
            LIMIT $5
            """,
            vector_str,
            stable_imprint,
            color,
            shape,
            limit,
        )
        return list(rows)
    except Exception as e:
        logger.warning("v5.1 mark metadata fallback 실패 (무시): %s", e)
        return []


async def find_drug_by_imprint(
    conn: asyncpg.Connection,
    client: AsyncOpenAI,
    features: dict,
    image_b64_list: list[str] | None = None,
) -> dict | None:
    features = _split_combined_imprint(features)

    parts = [
        v
        for v in [
            features.get("print_front"),
            features.get("print_back"),
            features.get("color"),
            features.get("shape"),
        ]
        if v
    ]

    if not parts:
        return None

    query_str = " ".join(parts)
    logger.info("2단계 imprint 검색 쿼리: %s", query_str)

    norm = normalize_vision_result(features)
    front_norm = norm["front_norm"] or ""
    back_norm = norm["back_norm"] or ""

    # v5.1: 모든 RAG query variant 로그
    rag_variants_for_search = build_rag_query_variants(features)
    for _vq in rag_variants_for_search:
        logger.info("v5.1 variant search query: %s", _vq)

    try:
        # v5.1: 모든 variant로 검색하고 item_seq 기준 merge
        seen_vector_seqs: set[str] = set()
        vector_rows_merged: list = []
        for _vq in rag_variants_for_search:
            emb_response = await client.embeddings.create(
                model="text-embedding-3-small",
                input=_vq,
            )
            _vstr = "[" + ",".join(str(v) for v in emb_response.data[0].embedding) + "]"
            _rows = await conn.fetch(
                """
                SELECT item_seq, item_name, chunk_text, metadata,
                       1 - (embedding <=> $1::vector) AS similarity
                FROM drug_embeddings
                WHERE chunk_type = 'imprint' AND embedding IS NOT NULL
                ORDER BY embedding <=> $1::vector
                LIMIT 10
                """,
                _vstr,
            )
            for _r in _rows:
                if _r["item_seq"] not in seen_vector_seqs:
                    seen_vector_seqs.add(_r["item_seq"])
                    vector_rows_merged.append(_r)
                else:
                    # 더 높은 similarity로 교체
                    for _existing in vector_rows_merged:
                        if _existing["item_seq"] == _r["item_seq"]:
                            if float(_r["similarity"]) > float(_existing["similarity"]):
                                vector_rows_merged.remove(_existing)
                                vector_rows_merged.append(_r)
                            break

        vector_rows = vector_rows_merged
        logger.info("v5.1 merged candidate count: %d", len(vector_rows))

        # fallback: 기본 query_str으로도 검색 (기존 동작 유지)
        emb_response = await client.embeddings.create(
            model="text-embedding-3-small",
            input=query_str,
        )
        vector_str = "[" + ",".join(str(v) for v in emb_response.data[0].embedding) + "]"

        _fallback_rows = await conn.fetch(
            """
            SELECT item_seq, item_name, chunk_text, metadata,
                   1 - (embedding <=> $1::vector) AS similarity
            FROM drug_embeddings
            WHERE chunk_type = 'imprint' AND embedding IS NOT NULL
            ORDER BY embedding <=> $1::vector
            LIMIT 20
            """,
            vector_str,
        )
        for _r in _fallback_rows:
            if _r["item_seq"] not in seen_vector_seqs:
                seen_vector_seqs.add(_r["item_seq"])
                vector_rows_merged.append(_r)
        vector_rows = vector_rows_merged

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
                      AND ({" AND ".join(conditions)}) AND embedding IS NOT NULL
                    LIMIT 10
                    """,
                        *params,
                    )
                )
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

        # v5.1: mark metadata fallback
        mark_fallback_rows: list = []
        if is_mark_confusable_imprint(features.get("print_front")):
            stable = back_norm or ""
            color_n = normalize_color_name(features.get("color")) or ""
            shape_n = features.get("shape") or ""
            if stable:
                logger.info("v5.1 mark metadata fallback: stable=%s, color=%s, shape=%s", stable, color_n, shape_n)
                mark_fallback_rows = await _search_mark_hypothesis_metadata(conn, vector_str, stable, color_n, shape_n)
                logger.info("v5.1 mark metadata fallback candidates: %d", len(mark_fallback_rows))

        if is_mark_confusable_imprint(features.get("print_back")):
            stable = front_norm or ""
            color_n = normalize_color_name(features.get("color")) or ""
            shape_n = features.get("shape") or ""
            if stable:
                logger.info("v5.1 mark metadata fallback: stable=%s, color=%s, shape=%s", stable, color_n, shape_n)
                mark_fallback_rows += await _search_mark_hypothesis_metadata(conn, vector_str, stable, color_n, shape_n)
                logger.info("v5.1 mark metadata fallback candidates: %d", len(mark_fallback_rows))

        seen_seqs: set[str] = set()
        candidates: list[dict] = []
        for r in list(mark_fallback_rows) + list(exact_rows) + list(vector_rows):
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

        for c in candidates:
            rerank = _rerank_score(norm, c["metadata"])
            c["rerank_score"] = rerank + c["vector_similarity"] * 10
            c["rerank_base"] = rerank

        candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
        logger.info(
            "imprint 상위 5개: %s",
            ", ".join(
                f"{c['item_name']}(r={c['rerank_base']:.0f},v={c['vector_similarity']:.3f})" for c in candidates[:5]
            ),
        )

        # 조건부 2차 VLM
        if image_b64_list and ENABLE_SECOND_PASS:
            recheck = _needs_recheck(features, candidates[:5])
            logger.info("needs_recheck: %s", recheck)
            model_name = await get_ai_model(conn)

            if recheck.get("faint_imprint_recheck"):
                r2 = await _call_second_pass(client, model_name, image_b64_list, _FAINT_IMPRINT_RECHECK_PROMPT)
                if r2:
                    features = merge_recheck_result(features, r2, "faint_imprint", SECOND_PASS_THRESHOLD)
                    logger.info("2차 VLM faint_imprint 병합: %s", r2)

            if recheck.get("cross_scoreline_recheck") or recheck.get("scoreline_recheck"):
                r2 = await _call_second_pass(client, model_name, image_b64_list, _SCORELINE_RECHECK_PROMPT)
                if r2:
                    features = merge_recheck_result(features, r2, "scoreline", SECOND_PASS_THRESHOLD)
                    logger.info("2차 VLM scoreline 병합: %s", r2)

            if recheck.get("mark_recheck"):
                r2 = await _call_second_pass(client, model_name, image_b64_list, _MARK_RECHECK_PROMPT)
                if r2:
                    features = merge_recheck_result(features, r2, "mark", SECOND_PASS_THRESHOLD)
                    logger.info("2차 VLM mark 병합: %s", r2)

            if any(recheck.values()):
                norm = normalize_vision_result(features)
                for c in candidates:
                    rerank = _rerank_score(norm, c["metadata"])
                    c["rerank_score"] = rerank + c["vector_similarity"] * 10
                    c["rerank_base"] = rerank
                candidates.sort(key=lambda x: x["rerank_score"], reverse=True)
                logger.info("2차 VLM 후 재랭크 1위: %s", candidates[0]["item_name"] if candidates else "none")

        # v5.1: mark hypothesis visual verification
        if image_b64_list and ENABLE_SECOND_PASS and should_force_mark_visual_verification(features, candidates):
            model_name_vv = await get_ai_model(conn)
            verify_result = await _run_candidate_visual_verification(client, model_name_vv, image_b64_list, candidates)
            logger.info("v5.1 candidate visual verification result: %s", verify_result)
            if verify_result and verify_result.get("best_candidate_index") is not None:
                idx_vv = int(verify_result["best_candidate_index"])
                if 0 <= idx_vv < len(candidates):
                    selected = candidates[idx_vv]
                    features = apply_mark_hypothesis_if_verified(features, verify_result, selected)
                    logger.info(
                        "v5.1 after verification: print_front=%s, print_back=%s",
                        features.get("print_front"),
                        features.get("print_back"),
                    )
                    # 보정 후 재랭크
                    norm = normalize_vision_result(features)
                    for c in candidates:
                        rerank = _rerank_score(norm, c["metadata"])
                        c["rerank_score"] = rerank + c["vector_similarity"] * 10
                        c["rerank_base"] = rerank
                    candidates.sort(key=lambda x: x["rerank_score"], reverse=True)

        best = candidates[0]
        second = candidates[1] if len(candidates) > 1 else None

        # v4 매칭 실패 판단
        fail, reason = should_return_match_failure(best, second, features, best["rerank_score"])
        if fail:
            logger.info(
                "imprint 매칭 실패 (%s) - rerank=%.1f, vec=%.3f", reason, best["rerank_base"], best["vector_similarity"]
            )
            return None

        logger.info(
            "imprint 매칭 성공: '%s' → '%s' (rerank=%.1f, vec=%.3f)",
            query_str,
            best["item_name"],
            best["rerank_base"],
            best["vector_similarity"],
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
async def fetch_drug_info_from_db(conn: asyncpg.Connection, item_seq: str) -> dict:
    rows = await conn.fetch(
        """
        SELECT chunk_type, chunk_text FROM drug_embeddings
        WHERE item_seq = $1 AND chunk_type IN ('efficacy', 'caution', 'ingredient')
        """,
        item_seq,
    )
    db_info: dict[str, str] = {}
    for r in rows:
        text = r["chunk_text"]
        if ": " in text:
            db_info[r["chunk_type"]] = text.split(": ", 1)[1].strip()
    return db_info


async def refine_drug_info(client: AsyncOpenAI, model: str, item_name: str, db_info: dict) -> dict:
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
  "usage_method": "복용법 및 용량",
  "warning": "복용 전 반드시 확인해야 할 경고 사항",
  "caution": "일반 주의사항",
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
async def save_analysis_result(conn: asyncpg.Connection, user_id: int, file_id: int, result: dict) -> int:
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

        image_b64_list: list[str] = []
        image_bytes_list: list[bytes] = []
        for s3_key in s3_keys[:2]:
            raw_bytes = download_file_from_s3(s3_key)
            b64, processed_bytes = preprocess_image(raw_bytes)
            image_b64_list.append(b64)
            image_bytes_list.append(processed_bytes)

        if not image_b64_list:
            raise ValueError("처리할 이미지가 없습니다.")

        ocr_texts: list[str | None] = list(await asyncio.gather(*[extract_imprint_ocr(b) for b in image_bytes_list]))

        # 앞면이 숫자만이고 뒷면이 영문자면 swap
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

        features = await extract_pill_features(client, image_b64_list, ocr_texts, model)
        logger.info("1단계 완료: %s", features)

        # v5.1: color 정규화 (녹색→초록 등)
        raw_color = features.get("color")
        features["color"] = normalize_color_name(raw_color)
        if raw_color and raw_color != features["color"]:
            logger.info("v5.1 color normalized: %s -> %s", raw_color, features["color"])

        # v5.1: mark-confusable 감지 로그
        pf = str(features.get("print_front") or "").strip()
        pb = str(features.get("print_back") or "").strip()
        if is_mark_confusable_imprint(pf) or is_mark_confusable_imprint(pb):
            logger.info("v5.1 mark-confusable imprint detected: front=%s, back=%s", pf, pb)

        # v5: multiple_pills 보정 + confidence 보정
        features = normalize_multiple_pills_flag(features)
        features = calibrate_vlm_confidence(features)
        logger.info(
            "v5 보정 후: multiple_pills=%s, imprint_conf=%.2f",
            features.get("multiple_pills"),
            features.get("imprint_confidence") or 0,
        )

        if not features.get("is_pill", True):
            result = {"product_name": "알약 이미지가 아닙니다", "gpt_model_version": model}
            analysis_id = await save_analysis_result(conn, user_id, file_id, result)
            return {"analysis_id": analysis_id, "product_name": result["product_name"], "result": result}

        if features.get("multiple_pills"):
            result = {"product_name": "여러 알약 감지 - 분석 실패", "gpt_model_version": model}
            analysis_id = await save_analysis_result(conn, user_id, file_id, result)
            return {"analysis_id": analysis_id, "product_name": result["product_name"], "result": result}

        # v5: RAG query variants 로그
        rag_variants = build_rag_query_variants(features)
        logger.info("v5 RAG query variants: %s", rag_variants)

        matched_drug = await find_drug_by_imprint(conn, client, features, image_b64_list)

        if matched_drug is None:
            parts = [v for v in [features.get("print_front"), features.get("print_back")] if v]
            product_name = f"각인: {', '.join(parts)} (DB 미매칭)" if parts else "식별 불가"
            result = {
                "product_name": product_name,
                "gpt_model_version": model,
                "vision_result": {
                    "print_front": features.get("print_front"),
                    "print_back": features.get("print_back"),
                    "color": features.get("color"),
                    "shape": features.get("shape"),
                    "imprint_confidence": features.get("imprint_confidence"),
                },
            }
            analysis_id = await save_analysis_result(conn, user_id, file_id, result)
            return {"analysis_id": analysis_id, "product_name": result["product_name"], "result": result}

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
