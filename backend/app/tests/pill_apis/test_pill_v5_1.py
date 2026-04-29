# tests/pill_apis/test_pill_v5_1.py
"""v5.1 회귀 테스트"""

import pytest

from ai_worker.tasks.imprint_parser import candidate_side_has_mark
from ai_worker.tasks.pill_analysis import (
    MARK_CONFUSABLE_IMPRINTS,
    build_rag_query_variants,
    is_mark_confusable_imprint,
    mark_match_score,
    normalize_color_name,
)


# ── 테스트 1. 색상 정규화 ──────────────────────────────────────────────────────
def test_normalize_color_name():
    assert normalize_color_name("녹색") == "초록"
    assert normalize_color_name("초록색") == "초록"
    assert normalize_color_name("흰색") == "하양"
    assert normalize_color_name("초록") == "초록"  # 이미 정규화된 값은 그대로
    assert normalize_color_name(None) is None


# ── 테스트 2. 마크 오인 문자 감지 ─────────────────────────────────────────────
def test_is_mark_confusable_imprint():
    assert is_mark_confusable_imprint("JS")
    assert is_mark_confusable_imprint("5")
    assert is_mark_confusable_imprint("15")
    assert is_mark_confusable_imprint("S")
    assert not is_mark_confusable_imprint("10")
    assert not is_mark_confusable_imprint("KB")
    assert not is_mark_confusable_imprint(None)
    assert not is_mark_confusable_imprint("")


# ── 테스트 3. 마크 hypothesis variant ─────────────────────────────────────────
def test_build_rag_query_variants_mark_hypothesis():
    vlm = {
        "print_front": "JS",
        "print_back": "10",
        "color": "녹색",
        "shape": "원형",
    }
    variants = build_rag_query_variants(vlm)

    # 기본 variants
    assert any("JS" in v and "10" in v for v in variants)
    # 마크 hypothesis variants
    assert any("마크" in v and "10" in v for v in variants), f"마크 10 variant 없음: {variants}"
    assert any("10" in v and "마크" in v for v in variants), f"10 마크 variant 없음: {variants}"
    assert any("마크" in v and "초록" in v for v in variants), f"마크 초록 variant 없음: {variants}"


# ── 테스트 4. candidate mark detection ────────────────────────────────────────
def test_candidate_side_has_mark():
    metadata = {
        "print_front": "마크",
        "print_back": "10",
        "imprint": {
            "front": {
                "raw": "마크",
                "text": "마크",
                "normalized": "마크",
                "tokens": [],
            },
            "back": {
                "raw": "10",
                "text": "10",
                "normalized": "10",
                "tokens": ["10"],
            },
        },
        "search_keys": {
            "front_norm": "마크",
            "back_norm": "10",
        },
    }
    assert candidate_side_has_mark(metadata, "front")
    assert not candidate_side_has_mark(metadata, "back")


# ── 테스트 5. JS vs 마크 점수 ─────────────────────────────────────────────────
def test_mark_match_score_confusable():
    metadata = {
        "print_front": "마크",
        "imprint": {
            "front": {"raw": "마크", "text": "마크", "normalized": "마크", "tokens": []},
        },
        "search_keys": {"front_norm": "마크"},
    }
    score = mark_match_score("JS", metadata, "front")
    assert score >= 20, f"JS vs 마크 점수가 20 미만: {score}"

    score_exact = mark_match_score("마크", metadata, "front")
    assert score_exact == 35.0, f"마크 vs 마크 점수가 35 아님: {score_exact}"
