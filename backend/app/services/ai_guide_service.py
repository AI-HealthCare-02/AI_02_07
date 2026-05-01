"""
AI 복약 가이드 생성 서비스 (동기 처리, Celery 없음)

RT_MEDICATION  : RAG 약품 DB + gpt-4o-mini 복약 안내 정리
RT_LIFESTYLE   : RAG 약품 DB + gpt-4o-mini 생활습관 가이드 정리
RT_CAUTION     : RAG 약품 DB + gpt-4o-mini 주의사항 요약 (✅ GPT 요약으로 개선)
RT_DRUG_DETAIL : 약별 상세 AI 가이드
"""

import json
import logging
from typing import Any

from openai import AsyncOpenAI

from app.core.config import settings
from app.services.rag_service import get_rag_service

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "⚠️ 본 정보는 공공 의약품 데이터를 AI가 정리한 참고 자료이며, "
    "의사·약사의 진단·처방을 대신하지 않습니다. "
    "복약 관련 문의는 반드시 의료 전문가에게 하시기 바랍니다."
)

ALL_RESULT_TYPES = ["RT_MEDICATION", "RT_LIFESTYLE", "RT_CAUTION"]

# ✅ 추가: 헬스 정보 코드 → 한글 매핑
SMOKING_DISPLAY = {
    "NON_SMOKER": "비흡연",
    "SMOKER": "흡연",
    "EX_SMOKER": "금연 중",
}
DRINKING_DISPLAY = {
    "NON_DRINKER": "비음주",
    "LIGHT": "가끔 음주",
    "MODERATE": "주 1~2회",
    "HEAVY": "주 3회 이상",
}
EXERCISE_DISPLAY = {
    "NONE": "운동 안 함",
    "LIGHT": "가벼운 운동 (주 1~2회)",
    "MODERATE": "보통 운동 (주 3~4회)",
    "HEAVY": "활발한 운동 (주 5회 이상)",
}


class AiGuideService:
    def __init__(self) -> None:
        self._openai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self._rag = get_rag_service()

    def _strip_markdown(self, raw: str) -> str:
        """GPT가 ```json ... ``` 으로 감쌀 때 제거"""
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:])
            raw = raw.strip()
            if raw.endswith("```"):
                raw = raw[:-3].strip()
        return raw

    # ✅ 추가: 헬스 정보 → 프롬프트용 문자열 변환
    def _format_health_info(self, user_health_info: dict) -> str:
        if not user_health_info:
            return ""
        lines = []
        if user_health_info.get("diseases"):
            lines.append(f"- 기저질환: {', '.join(user_health_info['diseases'])}")
        if user_health_info.get("allergies"):
            lines.append(f"- 알레르기: {', '.join(user_health_info['allergies'])}")
        if user_health_info.get("smoking"):
            lines.append(f"- 흡연: {SMOKING_DISPLAY.get(user_health_info['smoking'], user_health_info['smoking'])}")
        if user_health_info.get("drinking"):
            lines.append(f"- 음주: {DRINKING_DISPLAY.get(user_health_info['drinking'], user_health_info['drinking'])}")
        if user_health_info.get("exercise"):
            lines.append(f"- 운동: {EXERCISE_DISPLAY.get(user_health_info['exercise'], user_health_info['exercise'])}")
        return "\n".join(lines) if lines else ""

    async def generate(
        self,
        guide_id: int,
        medications: list[dict],
        patient_age: int,
        patient_gender: str,
        diagnosis_name: str,
        result_types: list[str] | None,
        user_health_info: dict | None = None,  # ✅ 추가: 사용자 헬스 정보
    ) -> dict[str, Any]:
        types_to_gen = result_types or ALL_RESULT_TYPES
        med_names = [m["medication_name"] for m in medications]
        health_info = user_health_info or {}  # ✅ 추가

        rag_chunks_by_name: dict[str, dict] = {}
        for name in med_names:
            try:
                efficacy = await self._rag.search_by_name(name, chunk_type="efficacy", similarity_threshold=0.3)
                caution = await self._rag.search_by_name(name, chunk_type="caution", similarity_threshold=0.3)
                ingredient = await self._rag.search_by_name(name, chunk_type="ingredient", similarity_threshold=0.3)
                rag_chunks_by_name[name] = {
                    "efficacy": efficacy[:3],
                    "caution": caution[:3],
                    "ingredient": ingredient[:2],
                }
            except Exception as e:
                logger.warning(f"RAG 검색 실패 [{name}]: {e}")
                rag_chunks_by_name[name] = {"efficacy": [], "caution": [], "ingredient": []}

        completed: list[str] = []
        failed: list[str] = []
        results: list[dict] = []

        for rt in types_to_gen:
            try:
                content = await self._generate_one(
                    rt,
                    rag_chunks_by_name,
                    med_names,
                    patient_age,
                    patient_gender,
                    diagnosis_name,
                    health_info,  # ✅ 추가
                )
                completed.append(rt)
                results.append({"result_type": rt, "content": content, "status": "COMPLETED"})
            except Exception as e:
                logger.error("AI 생성 실패 [guide_id=%s, type=%s]: %s", guide_id, rt, e)
                failed.append(rt)
                results.append({"result_type": rt, "content": {}, "status": "FAILED"})

        return {"completed": completed, "failed": failed, "results": results}

    async def _generate_one(
        self,
        result_type: str,
        rag_chunks_by_name: dict[str, dict],
        med_names: list[str],
        patient_age: int,
        patient_gender: str,
        diagnosis_name: str,
        user_health_info: dict,  # ✅ 추가
    ) -> dict[str, Any]:
        if result_type == "RT_MEDICATION":
            return await self._gen_medication(
                rag_chunks_by_name,
                med_names,
                patient_age,
                patient_gender,
                diagnosis_name,
                user_health_info,  # ✅ 추가
            )
        if result_type == "RT_LIFESTYLE":
            return await self._gen_lifestyle(
                rag_chunks_by_name,
                med_names,
                patient_age,
                patient_gender,
                diagnosis_name,
                user_health_info,  # ✅ 추가
            )
        if result_type == "RT_CAUTION":
            return await self._gen_caution(rag_chunks_by_name, med_names)
        if result_type == "RT_DRUG_DETAIL":
            return await self._gen_drug_detail(
                rag_chunks_by_name,
                med_names,
                patient_age,
                patient_gender,
                diagnosis_name,
                user_health_info,  # ✅ 추가
            )
        raise ValueError(f"지원하지 않는 result_type: {result_type}")

    def _build_drug_context(
        self,
        rag_chunks_by_name: dict[str, dict],
        med_names: list[str],
        chunk_types: list[str],
    ) -> str:
        lines = []
        for name in med_names:
            chunks = rag_chunks_by_name.get(name, {})
            drug_lines = []
            for ct in chunk_types:
                for chunk in chunks.get(ct, []):
                    drug_lines.append(f"  - {chunk.chunk_text}")
            if drug_lines:
                lines.append(f"[{name}]")
                lines.extend(drug_lines)
        return "\n".join(lines)

    # ──────────────────────────────────────────
    # RT_MEDICATION
    # ──────────────────────────────────────────
    async def _gen_medication(
        self,
        rag_chunks_by_name: dict[str, dict],
        med_names: list[str],
        patient_age: int,
        patient_gender: str,
        diagnosis_name: str,
        user_health_info: dict,  # ✅ 추가
    ) -> dict[str, Any]:
        drug_context = self._build_drug_context(rag_chunks_by_name, med_names, ["efficacy", "caution"])

        warnings: list[str] = []
        no_data_meds = [
            name
            for name in med_names
            if not rag_chunks_by_name.get(name, {}).get("efficacy")
            and not rag_chunks_by_name.get(name, {}).get("caution")
        ]
        for name in no_data_meds:
            warnings.append(f"'{name}' — 약품 DB 정보를 찾을 수 없습니다.")

        if not drug_context:
            return {"medications": [], "warnings": warnings, "disclaimer": DISCLAIMER}

        # ✅ 추가: 헬스 정보 포함
        health_str = self._format_health_info(user_health_info)
        health_section = f"\n환자 생활습관 및 건강 정보:\n{health_str}" if health_str else ""

        prompt = f"""아래는 약품 DB에서 가져온 공식 약품 정보입니다.
환자 정보: 나이 {patient_age}세, 성별 {"남성" if patient_gender == "GD_MALE" else "여성"}, 진단명 {diagnosis_name or "미상"}{health_section}

[약품 정보]
{drug_context}

위 공식 데이터만을 바탕으로, 환자가 이해하기 쉽도록 복약 안내를 정리해 주세요.
- 제공된 데이터에 없는 내용은 절대 추가하지 마세요.
- 각 약물별로 JSON 배열 형식으로 정리하세요.
- 형식: [{{"name": "약품명", "summary": "간단 설명", "how_to_take": "복용법 요약", "caution": "주의사항 요약"}}]
- 마크다운 코드블록(```) 없이 순수 JSON만 반환하세요."""

        response = await self._openai.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "당신은 공공 의약품 데이터를 정리하는 도우미입니다. 주어진 데이터 외의 내용을 생성하지 마세요. 마크다운 코드블록(```) 없이 순수 JSON만 반환하세요.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=1500,
            temperature=0.1,
        )

        raw = response.choices[0].message.content or "[]"
        raw = self._strip_markdown(raw)
        try:
            med_list = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("RT_MEDICATION JSON 파싱 실패, raw: %s", raw[:200])
            med_list = []

        return {"medications": med_list, "warnings": warnings, "disclaimer": DISCLAIMER}

    # ──────────────────────────────────────────
    # RT_LIFESTYLE
    # ──────────────────────────────────────────
    async def _gen_lifestyle(
        self,
        rag_chunks_by_name: dict[str, dict],
        med_names: list[str],
        patient_age: int,
        patient_gender: str,
        diagnosis_name: str,
        user_health_info: dict,  # ✅ 추가
    ) -> dict[str, Any]:
        drug_context = self._build_drug_context(rag_chunks_by_name, med_names, ["caution"])

        warnings: list[str] = []
        no_data_meds = [name for name in med_names if not rag_chunks_by_name.get(name, {}).get("caution")]
        for name in no_data_meds:
            warnings.append(f"'{name}' — 약품 DB 정보를 찾을 수 없습니다.")

        if not drug_context:
            return {"lifestyle": [], "warnings": warnings, "disclaimer": DISCLAIMER}

        # ✅ 추가: 헬스 정보 포함
        health_str = self._format_health_info(user_health_info)
        health_section = f"\n환자 생활습관 및 건강 정보:\n{health_str}" if health_str else ""

        prompt = f"""아래는 약품 DB의 공식 약품 주의사항 정보입니다.
환자 정보: 나이 {patient_age}세, 성별 {"남성" if patient_gender == "GD_MALE" else "여성"}, 진단명 {diagnosis_name or "미상"}{health_section}

[약품 주의사항 정보]
{drug_context}

위 공식 데이터만 바탕으로 생활습관 주의사항을 카테고리별로 JSON 배열로 정리하세요.
- 제공된 데이터에 없는 내용은 절대 추가하지 마세요.
- 환자의 생활습관 정보(흡연, 음주, 운동 등)가 있다면 해당 항목을 우선적으로 강조해 주세요.
- 카테고리: diet(식습관), exercise(운동), sleep(수면), alcohol(음주·흡연), interaction(약물-음식 상호작용)
- 형식: [{{"category": "diet", "title": "제목", "content": "내용"}}]
- 마크다운 코드블록(```) 없이 순수 JSON만 반환하세요."""

        response = await self._openai.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "당신은 공공 의약품 데이터를 정리하는 도우미입니다. 주어진 데이터 외의 내용을 생성하지 마세요. 마크다운 코드블록(```) 없이 순수 JSON만 반환하세요.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=1500,
            temperature=0.1,
        )

        raw = response.choices[0].message.content or "[]"
        raw = self._strip_markdown(raw)
        try:
            lifestyle_list = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("RT_LIFESTYLE JSON 파싱 실패, raw: %s", raw[:200])
            lifestyle_list = []

        return {"lifestyle": lifestyle_list, "warnings": warnings, "disclaimer": DISCLAIMER}

    # ──────────────────────────────────────────
    # RT_CAUTION — ✅ GPT 요약으로 개선
    # ──────────────────────────────────────────
    async def _gen_caution(
        self,
        rag_chunks_by_name: dict[str, dict],
        med_names: list[str],
    ) -> dict[str, Any]:
        warnings: list[str] = []
        drug_context_lines = []

        # ✅ 추가: item_seq 기준 중복 청크 제거 (같은 성분 다른 브랜드 중복 방지)
        seen_item_seqs: set[str] = set()

        for name in med_names:
            chunks = rag_chunks_by_name.get(name, {}).get("caution", [])
            if not chunks:
                warnings.append(f"'{name}' — 약품 DB 정보를 찾을 수 없습니다.")
                continue

            # ✅ 중복 item_seq 건너뜀
            unique_chunks = []
            for chunk in chunks:
                if chunk.item_seq not in seen_item_seqs:
                    seen_item_seqs.add(chunk.item_seq)
                    unique_chunks.append(chunk)

            if not unique_chunks:
                logger.info(f"[{name}] 모든 caution 청크가 중복으로 제거됨")
                continue

            drug_context_lines.append(f"[{name}]")
            for chunk in unique_chunks:
                drug_context_lines.append(f"  - {chunk.chunk_text}")

        if not drug_context_lines:
            return {"cautions": [], "warnings": warnings, "disclaimer": DISCLAIMER}

        drug_context = "\n".join(drug_context_lines)

        # ✅ 수정: GPT가 chunk_text 내 타 약품명을 medication_name으로 쓰지 않도록
        # 처방 약품명 목록을 명시하고 섹션 헤더 이름만 사용하도록 지시
        prescribed_names = ", ".join(f"[{n}]" for n in med_names)

        prompt = f"""아래는 약품 DB에서 가져온 공식 주의사항 원문입니다.
처방된 약물 목록 (이 목록에 있는 약물만 결과에 포함하세요): {prescribed_names}

[약품 주의사항 원문]
{drug_context}

위 원문을 바탕으로 환자가 읽기 쉽게 약물별 핵심 주의사항을 JSON 배열로 요약하세요.
- 반드시 처방된 약물 목록에 있는 약물만 결과에 포함하세요. 목록에 없는 약품은 절대 추가하지 마세요.
- medication_name은 반드시 처방된 약물 목록의 이름을 그대로 사용하세요. 원문 텍스트에 다른 약품명이 나와도 무시하세요.
- 원문에 없는 내용은 절대 추가하지 마세요.
- 각 약물별로 핵심 내용만 3~5개 항목으로 요약하세요.
- 형식:
[
  {{
    "medication_name": "처방된 약물 목록의 이름 그대로",
    "emergency_signs": ["즉시 병원을 가야 하는 증상1", "증상2"],
    "drug_interactions": ["병용 주의 약물 또는 음식1", "주의사항2"],
    "age_restrictions": "연령 제한 또는 특수 환자 주의사항 (없으면 빈 문자열)",
    "key_cautions": ["핵심 주의사항1", "핵심 주의사항2"]
  }}
]
- 마크다운 코드블록(```) 없이 순수 JSON만 반환하세요."""

        try:
            response = await self._openai.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "당신은 공공 의약품 주의사항을 환자 눈높이에 맞게 요약하는 도우미입니다. 반드시 제공된 원문 데이터만 사용하고, 없는 내용은 추측하지 마세요. 마크다운 코드블록(```) 없이 순수 JSON만 반환하세요.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=2000,
                temperature=0.1,
            )
            raw = response.choices[0].message.content or "[]"
            raw = self._strip_markdown(raw)
            caution_list = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("RT_CAUTION JSON 파싱 실패, raw: %s", raw[:200])
            caution_list = []
        except Exception as e:
            logger.error("RT_CAUTION LLM 호출 실패: %s", e)
            caution_list = []

        return {
            "source": "약품 DB (RAG)",
            "cautions": caution_list,
            "warnings": warnings,
            "disclaimer": DISCLAIMER,
        }

    # ──────────────────────────────────────────
    # RT_DRUG_DETAIL
    # ──────────────────────────────────────────
    async def _gen_drug_detail(
        self,
        rag_chunks_by_name: dict[str, dict],
        med_names: list[str],
        patient_age: int,
        patient_gender: str,
        diagnosis_name: str,
        user_health_info: dict,  # ✅ 추가
    ) -> dict[str, Any]:
        warnings: list[str] = []
        drugs: list[dict] = []

        # ✅ 추가: 헬스 정보 포함
        health_str = self._format_health_info(user_health_info)
        health_section = f"\n환자 생활습관 및 건강 정보:\n{health_str}" if health_str else ""

        for name in med_names:
            chunks = rag_chunks_by_name.get(name, {})
            all_chunks = chunks.get("efficacy", []) + chunks.get("caution", []) + chunks.get("ingredient", [])

            if not all_chunks:
                warnings.append(f"'{name}' — 약품 DB 정보를 찾을 수 없습니다.")
                drugs.append({"name": name, "error": "약품 DB 정보 없음"})
                continue

            drug_text = "\n".join(f"  - [{c.chunk_type}] {c.chunk_text}" for c in all_chunks)

            prompt = f"""아래는 약품 DB에서 가져온 [{name}]의 공식 정보입니다.
환자 정보: 나이 {patient_age}세, 성별 {"남성" if patient_gender == "GD_MALE" else "여성"}, 진단명 {diagnosis_name or "미상"}{health_section}

[약품 정보]
{drug_text}

위 공식 데이터만 바탕으로 이 약물 하나에 대한 상세 복약 가이드를 JSON으로 작성하세요.
- 반드시 제공된 데이터에 기반해야 하며, 없는 내용은 빈 문자열로 두세요.
- 형식:
{{
  "name": "약품명",
  "category": "약물 분류 (예: 혈압채널차단제, 항생제, 소염진통제 등. 데이터에 없으면 빈 문자열)",
  "mechanism_summary": "작용 원리를 환자 눈높이로 1~2문장 요약 (데이터에 없으면 빈 문자열)",
  "how_to_take": "복용법 상세",
  "side_effects": ["부작용1", "부작용2"],
  "side_effect_tips": "부작용 발생 시 대처 방법 요약",
  "food_interactions": "음식·음료와 상호작용 요약",
  "warnings": ["주의사항1", "주의사항2"],
  "faq": [{{"q": "질문", "a": "답변"}}]
}}
- 마크다운 코드블록(```) 없이 순수 JSON만 반환하세요."""

            try:
                response = await self._openai.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=[
                        {
                            "role": "system",
                            "content": "당신은 공공 의약품 데이터를 정리하는 도우미입니다. 반드시 제공된 공식 데이터만 사용하고, 없는 내용은 추측하지 마세요. 마크다운 코드블록(```) 없이 순수 JSON만 반환하세요.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=2000,
                    temperature=0.1,
                )
                raw = response.choices[0].message.content or "{}"
                raw = self._strip_markdown(raw)
                detail = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("RT_DRUG_DETAIL JSON 파싱 실패 [%s]", name)
                detail = {"name": name, "error": "파싱 실패"}
            except Exception as e:
                logger.error("RT_DRUG_DETAIL LLM 호출 실패 [%s]: %s", name, e)
                detail = {"name": name, "error": str(e)}

            drugs.append(detail)

        return {"drugs": drugs, "warnings": warnings, "disclaimer": DISCLAIMER}
