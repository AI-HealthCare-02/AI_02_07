"""
AI 복약 가이드 생성 서비스 (동기 처리, Celery 없음)

RT_MEDICATION  : e약은요 데이터 + gpt-4o-mini 정리
RT_LIFESTYLE   : e약은요 상호작용·주의사항 + gpt-4o-mini 정리
RT_CAUTION     : DUR 원문 반환, LLM 미사용
RT_DRUG_DETAIL : 약별 상세 AI 가이드 (✅ 신규)
"""

import json
import logging
from typing import Any

from openai import AsyncOpenAI

from app.core.config import settings
from app.services.public_drug_api import DrugApiResult, PublicDrugApiClient

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "⚠️ 본 정보는 공공 의약품 데이터를 AI가 정리한 참고 자료이며, "
    "의사·약사의 진단·처방을 대신하지 않습니다. "
    "복약 관련 문의는 반드시 의료 전문가에게 하시기 바랍니다."
)

# 기본 생성 목록 (RT_DRUG_DETAIL 은 요청 시에만 생성)
ALL_RESULT_TYPES = ["RT_MEDICATION", "RT_LIFESTYLE", "RT_CAUTION"]


class AiGuideService:
    def __init__(self) -> None:
        self._openai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self._drug_api = PublicDrugApiClient()

    async def generate(
        self,
        guide_id: int,
        medications: list[dict],
        patient_age: int,
        patient_gender: str,
        diagnosis_name: str,
        result_types: list[str] | None,
    ) -> dict[str, Any]:
        """
        요청된 result_types 생성 후 결과 반환.
        result_types=None 이면 전체(RT_MEDICATION, RT_LIFESTYLE, RT_CAUTION) 생성.
        RT_DRUG_DETAIL 은 명시적으로 요청해야 생성됨.
        """
        types_to_gen = result_types or ALL_RESULT_TYPES
        med_names = [m["medication_name"] for m in medications]

        # 공공 API 일괄 조회
        drug_results = await self._drug_api.fetch_all(med_names)

        completed: list[str] = []
        failed: list[str] = []
        results: list[dict] = []

        for rt in types_to_gen:
            try:
                content = await self._generate_one(
                    rt, drug_results, patient_age, patient_gender, diagnosis_name, medications
                )
                completed.append(rt)
                results.append({"result_type": rt, "content": content, "status": "COMPLETED"})
            except Exception as e:
                logger.error("AI 생성 실패 [guide_id=%s, type=%s]: %s", guide_id, rt, e)
                failed.append(rt)
                results.append({"result_type": rt, "content": {}, "status": "FAILED"})

        return {"completed": completed, "failed": failed, "results": results}

    # ──────────────────────────────────────────
    # 유형별 생성 라우터
    # ──────────────────────────────────────────
    async def _generate_one(
        self,
        result_type: str,
        drug_results: list[DrugApiResult],
        patient_age: int,
        patient_gender: str,
        diagnosis_name: str,
        medications: list[dict],
    ) -> dict[str, Any]:
        if result_type == "RT_MEDICATION":
            return await self._gen_medication(drug_results, patient_age, patient_gender, diagnosis_name)
        if result_type == "RT_LIFESTYLE":
            return await self._gen_lifestyle(drug_results, patient_age, patient_gender, diagnosis_name)
        if result_type == "RT_CAUTION":
            return self._gen_caution(drug_results)
        if result_type == "RT_DRUG_DETAIL":
            return await self._gen_drug_detail(drug_results, patient_age, patient_gender, diagnosis_name)
        raise ValueError(f"지원하지 않는 result_type: {result_type}")

    # ──────────────────────────────────────────
    # RT_MEDICATION
    # ──────────────────────────────────────────
    async def _gen_medication(
        self,
        drug_results: list[DrugApiResult],
        patient_age: int,
        patient_gender: str,
        diagnosis_name: str,
    ) -> dict[str, Any]:
        """RT_MEDICATION: e약은요 데이터를 LLM이 정리"""
        warnings = [r.warning for r in drug_results if r.warning]
        matched = [r for r in drug_results if r.drug_info]

        if not matched:
            return {"medications": [], "warnings": warnings, "disclaimer": DISCLAIMER}

        drug_data_text = "\n".join(
            f"[{r.drug_info.item_name}]\n"
            f"효능: {r.drug_info.efcy_qesitm}\n"
            f"사용법: {r.drug_info.use_method_qesitm}\n"
            f"주의사항: {r.drug_info.atpn_qesitm}\n"
            f"경고: {r.drug_info.atpn_warn_qesitm}"
            for r in matched
        )

        prompt = f"""
아래는 공공 의약품 데이터베이스(e약은요)에서 가져온 공식 약품 정보입니다.
환자 정보: 나이 {patient_age}세, 성별 {'남성' if patient_gender == 'GD_MALE' else '여성'}, 진단명 {diagnosis_name}

[약품 정보]
{drug_data_text}

위 공식 데이터만을 바탕으로, 환자가 이해하기 쉽도록 복약 안내를 정리해 주세요.
- 제공된 데이터에 없는 내용은 절대 추가하지 마세요.
- 각 약물별로 JSON 배열 형식으로 정리하세요.
- 형식: [{{"name": "약품명", "summary": "간단 설명", "how_to_take": "복용법 요약", "caution": "주의사항 요약"}}]
- JSON만 반환하세요. 설명 문장 없이.
"""
        response = await self._openai.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "당신은 공공 의약품 데이터를 정리하는 도우미입니다. 주어진 데이터 외의 내용을 생성하지 마세요."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=1500,
            temperature=0.1,
        )

        raw = response.choices[0].message.content or "[]"
        try:
            med_list = json.loads(raw.strip())
        except json.JSONDecodeError:
            logger.warning("RT_MEDICATION JSON 파싱 실패, raw: %s", raw[:200])
            med_list = []

        return {"medications": med_list, "warnings": warnings, "disclaimer": DISCLAIMER}

    # ──────────────────────────────────────────
    # RT_LIFESTYLE
    # ──────────────────────────────────────────
    async def _gen_lifestyle(
        self,
        drug_results: list[DrugApiResult],
        patient_age: int,
        patient_gender: str,
        diagnosis_name: str,
    ) -> dict[str, Any]:
        """RT_LIFESTYLE: 상호작용·부작용 데이터를 LLM이 생활습관 가이드로 정리"""
        warnings = [r.warning for r in drug_results if r.warning]
        matched = [r for r in drug_results if r.drug_info]

        if not matched:
            return {"lifestyle": [], "warnings": warnings, "disclaimer": DISCLAIMER}

        interaction_text = "\n".join(
            f"[{r.drug_info.item_name}]\n"
            f"상호작용: {r.drug_info.intrc_qesitm}\n"
            f"부작용: {r.drug_info.se_qesitm}\n"
            f"보관법: {r.drug_info.deposit_method_qesitm}"
            for r in matched
        )

        prompt = f"""
아래는 공공 의약품 데이터베이스(e약은요)의 공식 약품 상호작용·부작용 정보입니다.
환자 정보: 나이 {patient_age}세, 성별 {'남성' if patient_gender == 'GD_MALE' else '여성'}, 진단명 {diagnosis_name}

[약품 상호작용·부작용 정보]
{interaction_text}

위 공식 데이터만 바탕으로 생활습관 주의사항을 카테고리별로 JSON 배열로 정리하세요.
- 제공된 데이터에 없는 내용은 절대 추가하지 마세요.
- 카테고리: diet(식습관), exercise(운동), sleep(수면), alcohol(음주·흡연), interaction(약물-음식 상호작용)
- 형식: [{{"category": "diet", "title": "제목", "content": "내용"}}]
- JSON만 반환하세요.
"""
        response = await self._openai.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "당신은 공공 의약품 데이터를 정리하는 도우미입니다. 주어진 데이터 외의 내용을 생성하지 마세요."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=1500,
            temperature=0.1,
        )

        raw = response.choices[0].message.content or "[]"
        try:
            lifestyle_list = json.loads(raw.strip())
        except json.JSONDecodeError:
            logger.warning("RT_LIFESTYLE JSON 파싱 실패, raw: %s", raw[:200])
            lifestyle_list = []

        return {"lifestyle": lifestyle_list, "warnings": warnings, "disclaimer": DISCLAIMER}

    # ──────────────────────────────────────────
    # RT_CAUTION
    # ──────────────────────────────────────────
    def _gen_caution(self, drug_results: list[DrugApiResult]) -> dict[str, Any]:
        """
        RT_CAUTION: DUR 원문 그대로 반환, LLM 미사용
        법적 문제 방지 목적
        """
        warnings = [r.warning for r in drug_results if r.warning]

        combination: list[dict] = []
        age: list[dict] = []
        pregnancy: list[dict] = []

        for r in drug_results:
            for dur in r.dur_items:
                item = {
                    "medication_name": dur.item_name,
                    "prohbt_content": dur.prohbt_content,
                    "remark": dur.remark,
                }
                if dur.dur_type == "COMBINATION":
                    combination.append(item)
                elif dur.dur_type == "AGE":
                    age.append(item)
                elif dur.dur_type == "PREGNANCY":
                    pregnancy.append(item)

        return {
            "source": "식품의약품안전처 DUR (Drug Utilization Review)",
            "combination_contraindication": combination,
            "age_contraindication": age,
            "pregnancy_contraindication": pregnancy,
            "warnings": warnings,
            "disclaimer": DISCLAIMER,
        }

    # ──────────────────────────────────────────
    # RT_DRUG_DETAIL ✅ 신규
    # ──────────────────────────────────────────
    async def _gen_drug_detail(
        self,
        drug_results: list[DrugApiResult],
        patient_age: int,
        patient_gender: str,
        diagnosis_name: str,
    ) -> dict[str, Any]:
        """
        RT_DRUG_DETAIL: 약물별 상세 AI 가이드 생성.
        RT_MEDICATION 이 전체 요약이라면, RT_DRUG_DETAIL 은 약물 하나하나에 대한
        심층 정보(효능 메커니즘 요약, 부작용 대처법, Q&A 형식 안내)를 제공합니다.

        - e약은요의 모든 필드를 LLM에 공급해 더 풍부한 설명 생성
        - 약물별로 독립 JSON 객체 → 앱에서 약물 상세 페이지에 사용 가능
        """
        warnings = [r.warning for r in drug_results if r.warning]
        matched = [r for r in drug_results if r.drug_info]

        if not matched:
            return {"drugs": [], "warnings": warnings, "disclaimer": DISCLAIMER}

        drugs: list[dict] = []

        for r in matched:
            d = r.drug_info

            # DUR 정보가 있으면 함께 공급
            dur_text = ""
            drug_dur = [item for item in r.dur_items]
            if drug_dur:
                dur_lines = [
                    f"  - [{item.dur_type}] {item.prohbt_content} / 비고: {item.remark}"
                    for item in drug_dur
                ]
                dur_text = "DUR 금기 정보:\n" + "\n".join(dur_lines)

            prompt = f"""
아래는 공공 의약품 데이터베이스(e약은요·DUR)에서 가져온 공식 약품 정보입니다.
환자 정보: 나이 {patient_age}세, 성별 {'남성' if patient_gender == 'GD_MALE' else '여성'}, 진단명 {diagnosis_name}

[약품명] {d.item_name}
효능·효과: {d.efcy_qesitm}
사용법·용량: {d.use_method_qesitm}
경고: {d.atpn_warn_qesitm}
주의사항: {d.atpn_qesitm}
상호작용: {d.intrc_qesitm}
부작용: {d.se_qesitm}
보관법: {d.deposit_method_qesitm}
{dur_text}

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
  "storage": "보관법",
  "warnings": ["주의사항1", "주의사항2"],
  "dur_flags": {{"combination": true/false, "age": true/false, "pregnancy": true/false}},
  "faq": [
    {{"q": "질문", "a": "답변"}}
  ]
}}
- JSON 객체 하나만 반환하세요. 마크다운·설명 없이.
"""
            try:
                response = await self._openai.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "당신은 공공 의약품 데이터를 정리하는 도우미입니다. "
                                "반드시 제공된 공식 데이터만 사용하고, 없는 내용은 추측하지 마세요."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=2000,
                    temperature=0.1,
                )
                raw = response.choices[0].message.content or "{}"
                # JSON 파싱
                detail = json.loads(raw.strip())
            except json.JSONDecodeError:
                logger.warning("RT_DRUG_DETAIL JSON 파싱 실패 [%s]: %s", d.item_name, raw[:200])
                detail = {"name": d.item_name, "error": "파싱 실패"}
            except Exception as e:
                logger.error("RT_DRUG_DETAIL LLM 호출 실패 [%s]: %s", d.item_name, e)
                detail = {"name": d.item_name, "error": str(e)}

            drugs.append(detail)

        return {
            "drugs": drugs,
            "warnings": warnings,
            "disclaimer": DISCLAIMER,
        }
