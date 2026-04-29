# ai_worker/tasks/imprint_parser.py
# ──────────────────────────────────────────────
# STEP 1: imprint chunk_text 파서 → metadata 생성
# STEP 4: 이미지 분석 결과 정규화 유틸
# ──────────────────────────────────────────────

import logging
import re

logger = logging.getLogger(__name__)

# ── 색상 정규화 맵 ─────────────────────────────
_COLOR_MAP: dict[str, str] = {
    "흰색": "하양",
    "백색": "하양",
    "화이트": "하양",
    "흰": "하양",
    "황색": "노랑",
    "연노랑": "노랑",
    "연노": "노랑",
    "황": "노랑",
    "핑크": "분홍",
    "연분홍": "분홍",
    "살색": "분홍",
    "빨강": "빨강",
    "적색": "빨강",
    "파랑": "파랑",
    "청색": "파랑",
    "연파랑": "파랑",
    "초록": "초록",
    "녹색": "초록",
    "연두": "초록",
    "보라": "보라",
    "자색": "보라",
    "연보라": "보라",
    "주황": "주황",
    "오렌지": "주황",
    "갈색": "갈색",
    "브라운": "갈색",
    "회색": "회색",
    "그레이": "회색",
    "검정": "검정",
    "흑색": "검정",
    "투명": "투명",
}

# ── 모양 정규화 맵 (긴 키 우선 — 부분 매칭 오염 방지) ──────
# 반드시 긴 문자열이 앞에 와야 "타원형"이 "원"에 먼저 걸리지 않음
_SHAPE_MAP: list[tuple[str, str]] = [
    ("긴타원형", "장방형"),
    ("장방형정제", "장방형"),
    ("직사각형", "장방형"),
    # 타원형을 명시적으로 추가 — "원" 키에 먼저 걸리지 않도록
    ("타원형", "타원형"),
    ("동그라미", "원형"),
    ("정사각형", "사각형"),
    ("구형", "원형"),
    ("반원", "반원형"),
    ("삼각", "삼각형"),
    ("사각", "사각형"),
    ("마름모", "마름모형"),
    ("다이아몬드", "마름모형"),
    ("오각", "오각형"),
    ("육각", "육각형"),
    ("팔각", "팔각형"),
    # 가장 짧은 키는 마지막
    ("원", "원형"),
]


def _normalize_color(raw: str) -> str:
    raw = raw.strip()
    return _COLOR_MAP.get(raw, raw)


def _normalize_shape(raw: str) -> str:
    raw = raw.strip()
    # list[tuple] — 긴 키 우선 순서 보장
    for k, v in _SHAPE_MAP:
        if k in raw:
            return v
    return raw


# 비ASCII 유사 문자 → ASCII 변환 (Λ→A 등 그리스/특수문자 대응)
_UNICODE_TO_ASCII: dict[str, str] = {
    # 그리스 람다
    "Λ": "A",
    "λ": "A",
    # 그리스 알파
    "Α": "A",
    "α": "A",
    "Β": "B",
    "β": "B",
    "Ε": "E",
    "ε": "E",
    "Ζ": "Z",
    "ζ": "Z",
    "Η": "H",
    "η": "H",
    "Ι": "I",
    "ι": "I",
    "Κ": "K",
    "κ": "K",
    "Μ": "M",
    "μ": "M",
    "Ν": "N",
    "ν": "N",
    "Ο": "O",
    "ο": "O",
    "Ρ": "R",
    "ρ": "R",
    "Τ": "T",
    "τ": "T",
    "Υ": "Y",
    "υ": "Y",
    "Χ": "X",
    "χ": "X",
}
_UNICODE_RE = re.compile("|".join(re.escape(k) for k in _UNICODE_TO_ASCII))


# ── 마크 텍스트 집합 ───────────────────────────
MARK_TEXTS: set[str] = {"마크", "로고", "MARK", "LOGO", "mark", "logo", "symbol", "Symbol"}


def is_mark_text(text: str | None) -> bool:
    if not text:
        return False
    t = str(text).strip()
    if t in MARK_TEXTS:
        return True
    return bool("마크" in t or "로고" in t)


def normalize_mark_text(text: str | None) -> str | None:
    if not text:
        return None
    t = str(text).strip()
    if is_mark_text(t):
        return "마크"
    return None


def candidate_side_has_mark(metadata: dict, side: str) -> bool:
    """기존 metadata 구조에서 마크 여부를 판단. DB 구조 변경 없음."""
    if not metadata:
        return False
    imprint = (metadata.get("imprint") or {}).get(side) or {}
    values = [
        imprint.get("raw"),
        imprint.get("text"),
        imprint.get("normalized"),
        metadata.get(f"print_{side}"),
    ]
    values.extend(imprint.get("tokens") or [])
    sk = metadata.get("search_keys") or {}
    values.append(sk.get(f"{side}_norm"))
    return any(is_mark_text(v) for v in values)


def _normalize_imprint(text: str) -> str:
    """각인 텍스트 정규화: 비ASCII→ASCII, 분할선/십자분할선 제거, 대문자화, 공백/특수문자 제거.
    단, '마크'/'로고'는 보존한다."""
    if is_mark_text(text):
        return "마크"
    text = _UNICODE_RE.sub(lambda m: _UNICODE_TO_ASCII[m.group()], text)
    # 십자분할선을 분할선보다 먼저 제거
    text = re.sub(r"십자분할선", "", text)
    text = re.sub(r"분할선", "", text)
    text = re.sub(r"[\s|/\-_\\]", "", text)
    return text.upper().strip()


def _parse_imprint_side(raw: str) -> dict:
    """단면 각인 파싱."""
    has_score = bool(re.search(r"분할선", raw))
    text = re.sub(r"분할선", " ", raw).strip()
    normalized = _normalize_imprint(raw)
    tokens = [t for t in re.split(r"[\s분할선|/\-_\\]+", raw.upper()) if t]
    tokens = [re.sub(r"[^A-Z0-9]", "", t) for t in tokens]
    tokens = [t for t in tokens if t]
    return {
        "raw": raw,
        "text": text,
        "normalized": normalized,
        "has_score_line": has_score,
        "score_line_direction": None,
        "tokens": tokens,
    }


def _parse_size(raw: str) -> dict:
    """크기 파싱: 18x8mm, 18X8mm, 18×8mm 모두 처리. 오타(9..5, 14.2.) 허용."""
    # 숫자 정규화: 연속 점 제거, 끝 점 제거
    cleaned = re.sub(r"\.{2,}", ".", raw)  # 9..5 → 9.5
    cleaned = re.sub(r"\.(\s*mm)", r"\1", cleaned)  # 14.2.mm → 14.2mm
    m = re.search(r"([\d.]+)\s*[xX×]\s*([\d.]+)\s*mm", cleaned)
    if m:
        try:
            a, b = float(m.group(1)), float(m.group(2))
            return {"raw": raw, "long_mm": max(a, b), "short_mm": min(a, b), "unit": "mm"}
        except ValueError:
            pass
    m2 = re.search(r"([\d.]+)\s*mm", cleaned)
    if m2:
        try:
            v = float(m2.group(1))
            return {"raw": raw, "long_mm": v, "short_mm": None, "unit": "mm"}
        except ValueError:
            pass
    return {"raw": raw, "long_mm": None, "short_mm": None, "unit": None}


# ── STEP 1: chunk_text 파서 ────────────────────
def parse_imprint_chunk(chunk_text: str) -> dict | None:
    """
    imprint chunk_text를 파싱해 구조화된 metadata 반환.
    파싱 실패 시 None 반환.

    예시 입력:
      [크라목스정625밀리그람] 각인: 앞면 SCD, 뒷면 C분할선6 | 색상: 하양 | 모양: 장방형 | 크기: 18x8mm
    """
    try:
        raw_text = chunk_text.strip()

        # 각인 파싱
        imprint_m = re.search(r"각인:\s*(.+?)(?:\s*\||\s*$)", raw_text)
        raw_imprint = imprint_m.group(1).strip() if imprint_m else ""

        front_data: dict = {}
        back_data: dict = {}

        if raw_imprint:
            front_m = re.search(r"앞면\s+([^,]+?)(?:,\s*뒷면|$)", raw_imprint)
            back_m = re.search(r"뒷면\s+(.+?)$", raw_imprint)
            if front_m:
                val = front_m.group(1).strip()
                if "십자분할선" in val:
                    front_data = {
                        "raw": val,
                        "text": "",
                        "normalized": "",
                        "has_score_line": True,
                        "is_cross": True,
                        "score_line_direction": "십자",
                        "tokens": [],
                    }
                elif val == "분할선" or val.endswith("분할선"):
                    front_data = {
                        "raw": val,
                        "text": "",
                        "normalized": "",
                        "has_score_line": True,
                        "is_cross": False,
                        "score_line_direction": None,
                        "tokens": [],
                    }
                elif is_mark_text(val):
                    front_data = {
                        "raw": val,
                        "text": "마크",
                        "normalized": "마크",
                        "has_score_line": False,
                        "is_cross": False,
                        "score_line_direction": None,
                        "tokens": [],
                    }
                else:
                    front_data = _parse_imprint_side(val)
            if back_m:
                val = back_m.group(1).strip()
                if "십자분할선" in val:
                    back_data = {
                        "raw": val,
                        "text": "",
                        "normalized": "",
                        "has_score_line": True,
                        "is_cross": True,
                        "score_line_direction": "십자",
                        "tokens": [],
                    }
                elif val == "분할선" or val.endswith("분할선"):
                    back_data = {
                        "raw": val,
                        "text": "",
                        "normalized": "",
                        "has_score_line": True,
                        "is_cross": False,
                        "score_line_direction": None,
                        "tokens": [],
                    }
                elif is_mark_text(val):
                    back_data = {
                        "raw": val,
                        "text": "마크",
                        "normalized": "마크",
                        "has_score_line": False,
                        "is_cross": False,
                        "score_line_direction": None,
                        "tokens": [],
                    }
                else:
                    back_data = _parse_imprint_side(val)
            # 앞뒤 구분 없이 단일 각인인 경우
            if not front_m and not back_m and raw_imprint:
                front_data = _parse_imprint_side(raw_imprint)

        # 색상 파싱
        color_m = re.search(r"색상:\s*([^|]+)", raw_text)
        raw_color = color_m.group(1).strip() if color_m else ""

        # 모양 파싱
        shape_m = re.search(r"모양:\s*([^|]+)", raw_text)
        raw_shape = shape_m.group(1).strip() if shape_m else ""

        # 크기 파싱
        size_m = re.search(r"크기:\s*([^|]+)", raw_text)
        raw_size = size_m.group(1).strip() if size_m else ""

        front_norm = front_data.get("normalized", "")
        back_norm = back_data.get("normalized", "")
        all_norm = f"{front_norm} {back_norm}".strip()
        all_compact = (front_norm + back_norm).strip()

        # 검색 variants
        variants: list[str] = []
        if front_norm and back_norm:
            variants += [
                f"{front_norm} {back_norm}",
                f"{back_norm} {front_norm}",
            ]
            if front_data.get("has_score_line"):
                variants.append(f"{front_data['raw']} {back_norm}")
            if back_data.get("has_score_line"):
                variants.append(f"{front_norm} {back_data['raw']}")
        elif front_norm:
            variants.append(front_norm)

        return {
            "imprint_schema_version": 1,
            "source": {
                "raw_text": raw_text,
                "raw_imprint": raw_imprint,
                "raw_color": raw_color,
                "raw_shape": raw_shape,
                "raw_size": raw_size,
            },
            "imprint": {
                "front": front_data or None,
                "back": back_data or None,
            },
            "appearance": {
                "color_raw": raw_color,
                "color_normalized": _normalize_color(raw_color),
                "shape_raw": raw_shape,
                "shape_normalized": _normalize_shape(raw_shape),
            },
            "size": _parse_size(raw_size) if raw_size else {"raw": "", "long_mm": None, "short_mm": None, "unit": None},
            "search_keys": {
                "front_norm": front_norm or None,
                "back_norm": back_norm or None,
                "all_imprints_norm": all_norm or None,
                "all_imprints_compact": all_compact or None,
                "imprint_variants": variants,
            },
        }
    except Exception as e:
        logger.warning("imprint chunk 파싱 실패: %s | %s", chunk_text[:80], e)
        return None


# ── STEP 4: 이미지 분석 결과 정규화 ───────────


def color_tokens(color: str) -> set[str]:
    """ "반투명" 포함 방어 처리 후 "/" 및 "," 기준 토큰 분리."""
    tokens = set()
    for t in re.split(r"[/,]", color):
        t = t.strip()
        if t == "반투명":
            t = "투명"
        if t:
            tokens.add(t)
    return tokens


def shape_match_score(q_shape: str, c_shape: str) -> float:
    """모양 유사 점수: 정확 일치 8점, 타원형↔장방형 5점, 원형↔타원형 3점."""
    if not q_shape or not c_shape:
        return 0.0
    if q_shape == c_shape:
        return 8.0
    pair = frozenset([q_shape, c_shape])
    if pair == frozenset(["타원형", "장방형"]):
        return 5.0
    if pair == frozenset(["원형", "타원형"]):
        return 3.0
    return 0.0


# suspicious 짧은 문자 — 마크 오인 가능성이 높은 값
_SUSPICIOUS_MARK_CHARS: set[str] = {"5", "S", "JS", "J5", "15", "1S", "I5"}


def mark_match_score(query_value: str | None, candidate_metadata: dict, side: str) -> float:
    """
    마크 매칭 점수.
    - query가 "마크"이고 candidate도 마크: 35점
    - query가 suspicious 문자이고 candidate가 마크: 18점 (약한 점수)
    """
    if not query_value:
        return 0.0
    qv = str(query_value).strip()
    if is_mark_text(qv):
        return 35.0 if candidate_side_has_mark(candidate_metadata, side) else 0.0
    if qv in _SUSPICIOUS_MARK_CHARS and candidate_side_has_mark(candidate_metadata, side):
        return 20.0  # v5.1: 18 -> 20
    return 0.0


def normalize_vision_result(vision: dict) -> dict:
    """
    GPT Vision 분석 결과를 검색용으로 정규화.

    입력:
        {"print_front": "SCD", "print_back": "C 6", "color": "하양", "shape": "장방형", ...}
    출력:
        {"front_norm": "SCD", "back_norm": "C6", "color_norm": "하양", ...}
    """
    raw_front = (vision.get("print_front") or "").strip().upper()
    raw_back = (vision.get("print_back") or "").strip().upper()

    front_norm = _normalize_imprint(raw_front) if raw_front else None
    back_norm = _normalize_imprint(raw_back) if raw_back else None
    color_norm = _normalize_color(vision.get("color") or "")
    shape_norm = _normalize_shape(vision.get("shape") or "")

    variants: list[str] = []
    parts = [p for p in [front_norm, back_norm] if p]
    color_shape = f"{color_norm} {shape_norm}".strip()

    if len(parts) == 2:
        variants.append(f"{parts[0]} {parts[1]} {color_shape}".strip())
        variants.append(f"{parts[1]} {parts[0]} {color_shape}".strip())
        # OCR 혼동 문자 variant (편집거리 1 수준)
        for orig, alts in [("0", "O"), ("1", "I"), ("8", "B"), ("5", "S"), ("H", "N")]:
            for i, p in enumerate(parts):
                if orig in p:
                    alt_p = p.replace(orig, alts, 1)
                    other = parts[1 - i]
                    variants.append(f"{alt_p} {other} {color_shape}".strip())
    elif len(parts) == 1:
        variants.append(f"{parts[0]} {color_shape}".strip())

    # 중복 제거
    seen: set[str] = set()
    unique_variants: list[str] = []
    for v in variants:
        if v not in seen:
            seen.add(v)
            unique_variants.append(v)

    return {
        "front_norm": front_norm,
        "back_norm": back_norm,
        "score_line_front_type": vision.get("score_line_front_type") or "없음",
        "score_line_back_type": vision.get("score_line_back_type") or "없음",
        "color_norm": color_norm,
        "shape_norm": shape_norm,
        "query_variants": unique_variants,
    }
