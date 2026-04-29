"""
AI 복약 가이드 생성 서비스 (동기 처리, Celery 없음)

RT_MEDICATION  : RAG 약품 DB + gpt-4o-mini 복약 안내 정리
RT_LIFESTYLE   : RAG 약품 DB + gpt-4o-mini 생활습관 가이드 정리
RT_CAUTION     : RAG 약품 DB 주의사항 반환
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


class AiGuideService:
    def __init__(self) -> None:
        self._openai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self._rag = get_rag_service()

    # ──────────────────────────────────────────
    # ✅ 추가: 마크다운 코드블록 제거 유틸
    # ──────────────────────────────────────────
    def _strip_markdown(self, raw: str) -> str:
        """GPT가 ```json ... ``` 으로 감쌀 때 제거"""
        raw = raw.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:])  # 첫 줄(```json) 제거
            raw = raw.strip()
            if raw.endswith("```"):
                raw = raw[:-3].strip()  # 마지막 줄(```) 제거
        return raw

    async def generate(
        self,
        guide_id: int,
        medications: list[dict],
        patient_age: int,
        patient_gender: str,
        diagnosis_name: str,
        result_types: list[str] | None,
    ) -> dict[str, Any]:
        types_to_gen = result_types or ALL_RESULT_TYPES
        med_names = [m["medication_name"] for m in medications]

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
                    rt, rag_chunks_by_name, med_names, patient_age, patient_gender, diagnosis_name
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
    ) -> dict[str, Any]:
        if result_type == "RT_MEDICATION":
            return await self._gen_medication(
                rag_chunks_by_name, med_names, patient_age, patient_gender, diagnosis_name
            )
        if result_type == "RT_LIFESTYLE":
            return await self._gen_lifestyle(rag_chunks_by_name, med_names, patient_age, patient_gender, diagnosis_name)
        if result_type == "RT_CAUTION":
            return await self._gen_caution(rag_chunks_by_name, med_names)
        if result_type == "RT_DRUG_DETAIL":
            return await self._gen_drug_detail(
                rag_chunks_by_name, med_names, patient_age, patient_gender, diagnosis_name
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

        prompt = f"""아래는 약품 DB에서 가져온 공식 약품 정보입니다.
환자 정보: 나이 {patient_age}세, 성별 {"남성" if patient_gender == "GD_MALE" else "여성"}, 진단명 {diagnosis_name or "미상"}

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
        raw = self._strip_markdown(raw)  # ✅ 마크다운 제거
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
    ) -> dict[str, Any]:
        drug_context = self._build_drug_context(rag_chunks_by_name, med_names, ["caution"])

        warnings: list[str] = []
        no_data_meds = [name for name in med_names if not rag_chunks_by_name.get(name, {}).get("caution")]
        for name in no_data_meds:
            warnings.append(f"'{name}' — 약품 DB 정보를 찾을 수 없습니다.")

        if not drug_context:
            return {"lifestyle": [], "warnings": warnings, "disclaimer": DISCLAIMER}

        prompt = f"""아래는 약품 DB의 공식 약품 주의사항 정보입니다.
환자 정보: 나이 {patient_age}세, 성별 {"남성" if patient_gender == "GD_MALE" else "여성"}, 진단명 {diagnosis_name or "미상"}

[약품 주의사항 정보]
{drug_context}

위 공식 데이터만 바탕으로 생활습관 주의사항을 카테고리별로 JSON 배열로 정리하세요.
- 제공된 데이터에 없는 내용은 절대 추가하지 마세요.
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
        raw = self._strip_markdown(raw)  # ✅ 마크다운 제거
        try:
            lifestyle_list = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("RT_LIFESTYLE JSON 파싱 실패, raw: %s", raw[:200])
            lifestyle_list = []

        return {"lifestyle": lifestyle_list, "warnings": warnings, "disclaimer": DISCLAIMER}

    # ──────────────────────────────────────────
    # RT_CAUTION
    # ──────────────────────────────────────────
    async def _gen_caution(
        self,
        rag_chunks_by_name: dict[str, dict],
        med_names: list[str],
    ) -> dict[str, Any]:
        warnings: list[str] = []
        caution_list: list[dict] = []

        for name in med_names:
            chunks = rag_chunks_by_name.get(name, {}).get("caution", [])
            if not chunks:
                warnings.append(f"'{name}' — 약품 DB 정보를 찾을 수 없습니다.")
                continue
            for chunk in chunks:
                caution_list.append(
                    {
                        "medication_name": name,
                        "caution_text": chunk.chunk_text,
                        "similarity": round(chunk.similarity, 3),
                    }
                )

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
    ) -> dict[str, Any]:
        warnings: list[str] = []
        drugs: list[dict] = []

        for name in med_names:
            chunks = rag_chunks_by_name.get(name, {})
            all_chunks = chunks.get("efficacy", []) + chunks.get("caution", []) + chunks.get("ingredient", [])

            if not all_chunks:
                warnings.append(f"'{name}' — 약품 DB 정보를 찾을 수 없습니다.")
                drugs.append({"name": name, "error": "약품 DB 정보 없음"})
                continue

            drug_text = "\n".join(f"  - [{c.chunk_type}] {c.chunk_text}" for c in all_chunks)

            prompt = f"""아래는 약품 DB에서 가져온 [{name}]의 공식 정보입니다.
환자 정보: 나이 {patient_age}세, 성별 {"남성" if patient_gender == "GD_MALE" else "여성"}, 진단명 {diagnosis_name or "미상"}

[약품 정보]
{drug_text}

위 공식 데이터만 바탕으로 이 약물 하나에 대한 상세 복약 가이드를 JSON으로 작성하세요.
- 반드시 제공된 데이터에 기반해야 하며, 없는 내용은 빈 문자열로 두세요.
- 형식:
{{
  "name": "약품명",
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
                raw = self._strip_markdown(raw)  # ✅ 마크다운 제거
                detail = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("RT_DRUG_DETAIL JSON 파싱 실패 [%s]", name)
                detail = {"name": name, "error": "파싱 실패"}
            except Exception as e:
                logger.error("RT_DRUG_DETAIL LLM 호출 실패 [%s]: %s", name, e)
                detail = {"name": name, "error": str(e)}

            drugs.append(detail)

        return {"drugs": drugs, "warnings": warnings, "disclaimer": DISCLAIMER}
