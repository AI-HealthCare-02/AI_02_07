from datetime import date, datetime, time
from typing import Any

from pydantic import BaseModel, Field


# ──────────────────────────────────────────
# 공통
# ──────────────────────────────────────────
class MessageResponse(BaseModel):
    message: str


# ──────────────────────────────────────────
# 가이드 목록 조회
# ──────────────────────────────────────────
class GuideListItem(BaseModel):
    guide_id: int
    title: str
    visit_date: date | None
    med_start_date: date
    med_end_date: date | None
    d_day: int | None  # 오늘 기준 남은 복약일 (완료 시 None)
    medication_count: int
    guide_status: str  # GS_ACTIVE | GS_COMPLETED
    input_method: str  # IM_MANUAL | IM_DOCUMENT
    hospital_name: str | None = None
    weekly_compliance_rate: float | None = None  # 최근 7일 복약 이행률 (0.0 ~ 1.0)
    today_progress_done: int = 0
    today_progress_total: int = 0


class GuideListResponse(BaseModel):
    total_count: int
    page: int
    size: int
    guides: list[GuideListItem]


# ──────────────────────────────────────────
# 가이드 생성 (직접 입력)
# ──────────────────────────────────────────
class MedicationCreateItem(BaseModel):
    medication_name: str = Field(..., min_length=1, max_length=200)
    dosage: str | None = None
    frequency: str | None = None
    timing: str | None = None
    duration_days: int | None = None


class ConditionCreateItem(BaseModel):
    type: str = Field(..., pattern="^(CT_DISEASE|CT_CURRENT_MED|CT_ALLERGY)$")
    name: str = Field(..., min_length=1, max_length=200)


class GuideCreateRequest(BaseModel):
    diagnosis_name: str | None = Field(None, min_length=1, max_length=200)  # 약봉투 등 null 허용
    med_start_date: date
    patient_age: int | None = Field(None, gt=0, lt=150)  # Optional: 프론트 폼 미포함
    patient_gender: str | None = Field(None, pattern="^(GD_MALE|GD_FEMALE)$")  # Optional
    hospital_name: str | None = None
    visit_date: date | None = None
    med_end_date: date | None = None
    title: str | None = None  # 미입력 시 서버에서 자동 생성
    conditions: list[ConditionCreateItem] = []
    medications: list[MedicationCreateItem] = Field(..., min_length=1)


class GuideCreateFromDocRequest(BaseModel):
    """의료 문서 분석 결과(doc_result_id)로 가이드 생성 — 승원 파트 연동"""

    doc_result_id: int
    med_start_date: date
    med_end_date: date | None = None
    title: str | None = None  # 미입력 시 진단명 or 병원명으로 자동 생성


class GuideCreateResponse(BaseModel):
    guide_id: int
    title: str
    guide_status: str
    input_method: str


# ──────────────────────────────────────────
# 가이드 상세 조회
# ──────────────────────────────────────────
class MedicationDetailItem(BaseModel):
    guide_medication_id: int
    medication_name: str
    dosage: str | None
    frequency: str | None
    timing: str | None
    duration_days: int | None


class GuideDetailResponse(BaseModel):
    guide_id: int
    title: str
    hospital_name: str | None
    diagnosis_name: str
    med_start_date: date
    med_end_date: date | None
    guide_status: str
    input_method: str
    medications: list[MedicationDetailItem]
    created_at: datetime


# ──────────────────────────────────────────
# 가이드 수정
# ──────────────────────────────────────────
class GuidePatchRequest(BaseModel):
    title: str | None = None
    hospital_name: str | None = None
    visit_date: date | None = None
    med_start_date: date | None = None
    med_end_date: date | None = None
    guide_status: str | None = Field(None, pattern="^(GS_ACTIVE|GS_COMPLETED)$")


class GuidePatchResponse(BaseModel):
    guide_id: int
    title: str
    guide_status: str


# ──────────────────────────────────────────
# 기저질환·복용약·알레르기 (Conditions)
# ──────────────────────────────────────────
class ConditionItem(BaseModel):
    condition_id: int
    name: str


class ConditionsResponse(BaseModel):
    diseases: list[ConditionItem]
    current_meds: list[ConditionItem]
    allergies: list[ConditionItem]


class ConditionsPutRequest(BaseModel):
    conditions: list[ConditionCreateItem]


# ──────────────────────────────────────────
# AI 가이드 생성
# ──────────────────────────────────────────
class AiGenerateRequest(BaseModel):
    result_types: list[str] | None = None  # None이면 전체 생성


class AiResultItem(BaseModel):
    ai_result_id: int
    result_type: str
    content: dict[str, Any]
    status: str


class AiGenerateResponse(BaseModel):
    completed: list[str]
    failed: list[str]
    results: list[AiResultItem]


# ──────────────────────────────────────────
# AI 결과 조회
# ──────────────────────────────────────────
class AiResultDetailItem(BaseModel):
    ai_result_id: int
    result_type: str
    content: dict[str, Any]
    status: str
    version: int
    created_at: datetime


# ──────────────────────────────────────────
# 복약 체크
# ──────────────────────────────────────────
class MedCheckItem(BaseModel):
    check_id: int | None
    guide_medication_id: int
    medication_name: str
    timing: str | None
    is_taken: bool
    taken_at: datetime | None


class MedCheckResponse(BaseModel):
    date: date
    day_count: int
    progress_percent: int
    items: list[MedCheckItem]


class MedCheckCreateRequest(BaseModel):
    guide_medication_id: int
    check_date: date
    taken_at: datetime | None = None  # None이면 서버 현재 시각


class MedCheckCreateResponse(BaseModel):
    check_id: int
    guide_medication_id: int
    is_taken: bool
    taken_at: datetime


# ──────────────────────────────────────────
# 복약 알림
# ──────────────────────────────────────────
class ReminderResponse(BaseModel):
    reminder_id: int
    reminder_time: time
    repeat_type: str
    custom_days: list[int] | None
    is_browser_noti: bool
    is_email_noti: bool
    is_active: bool


class ReminderCreateRequest(BaseModel):
    reminder_time: time
    repeat_type: str = Field("RPT_DAILY", pattern="^(RPT_DAILY|RPT_WEEKDAY|RPT_CUSTOM)$")
    custom_days: list[int] | None = None  # [0~6], 0=월
    is_browser_noti: bool = False
    is_email_noti: bool = False


class ReminderPatchRequest(BaseModel):
    reminder_time: time | None = None
    repeat_type: str | None = Field(None, pattern="^(RPT_DAILY|RPT_WEEKDAY|RPT_CUSTOM)$")
    custom_days: list[int] | None = None
    is_browser_noti: bool | None = None
    is_email_noti: bool | None = None
    is_active: bool | None = None


class ReminderSimpleResponse(BaseModel):
    reminder_id: int
    reminder_time: time
    is_active: bool


# ──────────────────────────────────────────
# 복약 달력 — 월별 조회
# ──────────────────────────────────────────
class MedCheckDayItem(BaseModel):
    date: date
    status: str  # done | partial | missed | future


class MedCheckMonthlyResponse(BaseModel):
    year: int
    month: int
    days: list[MedCheckDayItem]


# ──────────────────────────────────────────
# AI 생성 진행 상태
# ──────────────────────────────────────────
class AiGenerateStatusResponse(BaseModel):
    status: str  # pending | processing | done | failed
    completed_types: list[str]
