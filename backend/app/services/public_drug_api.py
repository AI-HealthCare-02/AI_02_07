"""
공공 의약품 API 클라이언트
- e약은요 API : 복약 안내 데이터 (RT_MEDICATION · RT_LIFESTYLE 원본)
- DUR API     : 병용금기·연령금기·임부금기 (RT_CAUTION 원본)

✅ 2차 개선사항:
  - 약품명 정규화 (괄호·용량 표기 제거, 공백 정규화)
  - 수동 매핑 테이블 (MANUAL_DRUG_MAP): 자주 매칭 실패하는 성분명 → 공식 약품명
  - 1차 exact 검색 실패 시 정규화명으로 재시도 (2-step 검색)
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

EDRUGINFO_BASE = "https://apis.data.go.kr/1471000/DrbEasyDrugInfoService"
DUR_BASE = "https://apis.data.go.kr/1471000/DURPrdlstInfoService03"

# ──────────────────────────────────────────────────────────────
# 수동 매핑 테이블
# 처방전에 자주 등장하는 성분명/축약명 → e약은요·DUR API 검색 키워드
# 실제 운영 중 매칭 실패 로그를 보며 지속 보완 필요
# ──────────────────────────────────────────────────────────────
MANUAL_DRUG_MAP: dict[str, str] = {
    # 아세트아미노펜 계열
    "타이레놀": "아세트아미노펜",
    "타이레놀이알서방정": "아세트아미노펜",
    "acetaminophen": "아세트아미노펜",
    "paracetamol": "아세트아미노펜",

    # 이부프로펜 계열
    "애드빌": "이부프로펜",
    "부루펜": "이부프로펜",
    "ibuprofen": "이부프로펜",

    # 아스피린
    "아스피린프로텍트": "아스피린",
    "아스피린장용정": "아스피린",
    "aspirin": "아스피린",

    # 항생제
    "아목시실린": "아목시실린",
    "amoxicillin": "아목시실린",
    "아목시클라브": "아목시실린/클라불란산",
    "오구멘틴": "아목시실린/클라불란산",
    "augmentin": "아목시실린/클라불란산",
    "세팔렉신": "세팔렉신",
    "cephalexin": "세팔렉신",

    # 위장약
    "오메프라졸": "오메프라졸",
    "omeprazole": "오메프라졸",
    "판토프라졸": "판토프라졸",
    "pantoprazole": "판토프라졸",
    "란소프라졸": "란소프라졸",
    "lansoprazole": "란소프라졸",

    # 혈압약
    "암로디핀": "암로디핀",
    "amlodipine": "암로디핀",
    "로사르탄": "로사르탄",
    "losartan": "로사르탄",
    "발사르탄": "발사르탄",
    "valsartan": "발사르탄",

    # 당뇨약
    "메트포르민": "메트포르민",
    "metformin": "메트포르민",
    "글리메피리드": "글리메피리드",
    "glimepiride": "글리메피리드",

    # 고지혈증
    "아토르바스타틴": "아토르바스타틴",
    "atorvastatin": "아토르바스타틴",
    "로수바스타틴": "로수바스타틴",
    "rosuvastatin": "로수바스타틴",

    # 항히스타민
    "세티리진": "세티리진",
    "cetirizine": "세티리진",
    "로라타딘": "로라타딘",
    "loratadine": "로라타딘",
    "펙소페나딘": "펙소페나딘",
    "fexofenadine": "펙소페나딘",

    # 진통소염제
    "나프록센": "나프록센",
    "naproxen": "나프록센",
    "디클로페낙": "디클로페낙",
    "diclofenac": "디클로페낙",
    "세레콕시브": "세레콕시브",
    "celecoxib": "세레콕시브",
}


# ──────────────────────────────────────────────────────────────
# 약품명 정규화
# ──────────────────────────────────────────────────────────────
_DOSE_PATTERN = re.compile(
    r"\s*\d+\.?\d*\s*(?:mg|mcg|μg|ug|g|ml|mL|IU|단위|정|캡슐|포|패치|앰플)\b",
    re.IGNORECASE,
)
_BRACKET_PATTERN = re.compile(r"\([^)]*\)|\[[^\]]*\]")
_SPACE_PATTERN = re.compile(r"\s+")


def normalize_drug_name(name: str) -> str:
    """
    처방전 약품명을 API 검색에 적합하게 정규화.
    예) '아세트아미노펜정 500mg (타이레놀)' → '아세트아미노펜정'
    """
    name = _BRACKET_PATTERN.sub("", name)   # 괄호 제거
    name = _DOSE_PATTERN.sub("", name)       # 용량 표기 제거
    name = _SPACE_PATTERN.sub(" ", name)     # 중복 공백 정리
    return name.strip()


def resolve_drug_name(original: str) -> list[str]:
    """
    검색 시도 순서를 반환:
    1) 원본
    2) 정규화된 이름
    3) 수동 매핑된 이름
    중복 제거 + 순서 유지.
    """
    candidates: list[str] = []

    # 1. 원본
    candidates.append(original.strip())

    # 2. 수동 매핑 (대소문자 무시)
    lower = original.strip().lower()
    for key, mapped in MANUAL_DRUG_MAP.items():
        if key.lower() == lower or key.lower() in lower:
            if mapped not in candidates:
                candidates.append(mapped)

    # 3. 정규화
    normalized = normalize_drug_name(original)
    if normalized and normalized not in candidates:
        candidates.append(normalized)

    # 4. 정규화된 이름으로도 수동 매핑 시도
    norm_lower = normalized.lower()
    for key, mapped in MANUAL_DRUG_MAP.items():
        if key.lower() == norm_lower or key.lower() in norm_lower:
            if mapped not in candidates:
                candidates.append(mapped)

    return candidates


# ──────────────────────────────────────────────────────────────
# 데이터 클래스
# ──────────────────────────────────────────────────────────────
@dataclass
class DrugInfo:
    """e약은요 응답 파싱 결과"""
    item_name: str
    efcy_qesitm: str = ""
    use_method_qesitm: str = ""
    atpn_warn_qesitm: str = ""
    atpn_qesitm: str = ""
    intrc_qesitm: str = ""
    se_qesitm: str = ""
    deposit_method_qesitm: str = ""


@dataclass
class DurItem:
    """DUR API 파싱 결과"""
    item_name: str
    dur_type: str           # COMBINATION | AGE | PREGNANCY
    prohbt_content: str = ""
    remark: str = ""


@dataclass
class DrugApiResult:
    """약품명별 API 조회 결과"""
    medication_name: str
    drug_info: DrugInfo | None = None
    dur_items: list[DurItem] = field(default_factory=list)
    matched: bool = False
    matched_name: str | None = None     # ✅ 실제 매칭된 API 검색어 기록
    warning: str | None = None


# ──────────────────────────────────────────────────────────────
# API 클라이언트
# ──────────────────────────────────────────────────────────────
class PublicDrugApiClient:
    def __init__(self) -> None:
        self._api_key = settings.PUBLIC_DATA_API_KEY

    # ── e약은요 ──────────────────────────────────
    async def fetch_drug_info(self, medication_name: str) -> DrugApiResult:
        """
        e약은요 API에서 복약 안내 조회.
        매칭 실패 시 유사어 후보로 순서대로 재시도 (2-step).
        """
        result = DrugApiResult(medication_name=medication_name)
        candidates = resolve_drug_name(medication_name)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                for candidate in candidates:
                    resp = await client.get(
                        f"{EDRUGINFO_BASE}/getDrbEasyDrugList",
                        params={
                            "serviceKey": self._api_key,
                            "itemName": candidate,
                            "type": "json",
                            "numOfRows": 1,
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    items = data.get("body", {}).get("items", [])

                    if items:
                        item = items[0]
                        result.matched = True
                        result.matched_name = candidate
                        result.drug_info = DrugInfo(
                            item_name=item.get("itemName", candidate),
                            efcy_qesitm=item.get("efcyQesitm", ""),
                            use_method_qesitm=item.get("useMethodQesitm", ""),
                            atpn_warn_qesitm=item.get("atpnWarnQesitm", ""),
                            atpn_qesitm=item.get("atpnQesitm", ""),
                            intrc_qesitm=item.get("intrcQesitm", ""),
                            se_qesitm=item.get("seQesitm", ""),
                            deposit_method_qesitm=item.get("depositMethodQesitm", ""),
                        )
                        # 원본과 다른 후보로 매칭됐다면 안내 로그
                        if candidate != medication_name:
                            logger.info(
                                "e약은요 유사어 매칭 성공: '%s' → '%s'",
                                medication_name,
                                candidate,
                            )
                        return result

                # 모든 후보 실패
                result.warning = (
                    f"'{medication_name}' — e약은요 매칭 결과 없음 "
                    f"(시도한 검색어: {candidates}). 복약 안내를 건너뜁니다."
                )

        except httpx.HTTPError as e:
            logger.warning("e약은요 API 오류 [%s]: %s", medication_name, e)
            result.warning = f"'{medication_name}' — e약은요 API 호출 실패. 복약 안내를 건너뜁니다."

        return result

    # ── DUR ──────────────────────────────────────
    async def fetch_dur_info(self, medication_name: str) -> DrugApiResult:
        """
        DUR API에서 병용금기·연령금기·임부금기 조회.
        매칭 실패 시 유사어 후보로 재시도.
        """
        result = DrugApiResult(medication_name=medication_name)
        candidates = resolve_drug_name(medication_name)

        endpoints = [
            ("COMBINATION", "getUsjntTabooInfoList03"),
            ("AGE", "getSpcifyAgrdeTabooInfoList03"),
            ("PREGNANCY", "getPwnmTabooInfoList03"),
        ]

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                for candidate in candidates:
                    dur_items: list[DurItem] = []

                    for dur_type, endpoint in endpoints:
                        resp = await client.get(
                            f"{DUR_BASE}/{endpoint}",
                            params={
                                "serviceKey": self._api_key,
                                "itemName": candidate,
                                "type": "json",
                                "numOfRows": 10,
                            },
                        )
                        resp.raise_for_status()
                        data = resp.json()
                        items = data.get("body", {}).get("items", []) or []

                        for item in items:
                            dur_items.append(
                                DurItem(
                                    item_name=item.get("ITEM_NAME", candidate),
                                    dur_type=dur_type,
                                    prohbt_content=item.get("PROHBT_CONTENT", ""),
                                    remark=item.get("REMARK", ""),
                                )
                            )

                    if dur_items:
                        result.matched = True
                        result.matched_name = candidate
                        result.dur_items = dur_items
                        if candidate != medication_name:
                            logger.info(
                                "DUR 유사어 매칭 성공: '%s' → '%s'",
                                medication_name,
                                candidate,
                            )
                        return result

                # 모든 후보 실패
                result.warning = (
                    f"'{medication_name}' — DUR 데이터베이스에서 일치하는 약품을 찾지 못했습니다. "
                    f"(시도한 검색어: {candidates}). 주의사항 항목에서 해당 약물이 제외됩니다."
                )

        except httpx.HTTPError as e:
            logger.warning("DUR API 오류 [%s]: %s", medication_name, e)
            result.warning = f"'{medication_name}' — DUR API 호출 실패. 주의사항을 건너뜁니다."

        return result

    async def fetch_all(self, medication_names: list[str]) -> list[DrugApiResult]:
        """약품 목록 전체 조회 (e약은요 + DUR 병합)"""
        drug_tasks = [self.fetch_drug_info(name) for name in medication_names]
        dur_tasks = [self.fetch_dur_info(name) for name in medication_names]

        drug_results, dur_results = await asyncio.gather(
            asyncio.gather(*drug_tasks),
            asyncio.gather(*dur_tasks),
        )

        # 약품명 기준으로 병합
        merged: dict[str, DrugApiResult] = {}
        for r in drug_results:
            merged[r.medication_name] = r
        for r in dur_results:
            if r.medication_name in merged:
                merged[r.medication_name].dur_items = r.dur_items
                if r.warning and not merged[r.medication_name].warning:
                    merged[r.medication_name].warning = r.warning
            else:
                merged[r.medication_name] = r

        return list(merged.values())
