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
    d_day: int | None
    medication_count: int
    guide_status: str
    input_method: str
    hospital_name: str | None = None
    weekly_compliance_rate: float | None = None
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
    diagnosis_name: str | None = Field(None, min_length=1, max_length=200)
    med_start_date: date
    patient_age: int | None = Field(None, gt=0, lt=150)
    patient_gender: str | None = Field(None, pattern="^(GD_MALE|GD_FEMALE)$")
    hospital_name: str | None = None
    visit_date: date | None = None
    med_end_date: date | None = None
    title: str | None = None
    conditions: list[ConditionCreateItem] = []
    medications: list[MedicationCreateItem] = Field(..., min_length=1)


class GuideCreateFromDocRequest(BaseModel):
    doc_result_id: int
    med_start_date: date
    med_end_date: date | None = None
    title: str | None = None


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
    # ✅ 추가: 사용자가 선택한 복약 시간대 (아침/점심/저녁/취침전)
    daily_slots: list[str] | None = None


class GuideDetailResponse(BaseModel):
    guide_id: int
    title: str
    hospital_name: str | None
    diagnosis_name: str | None
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
    result_types: list[str] | None = None


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
    timing_slot: str  # ✅ 추가: SLOT_1 / SLOT_2 / SLOT_3 (몇 번째 복약인지)
    slot_label: str  # ✅ 추가: "아침" / "저녁" 또는 "1회차" / "2회차" (화면 표시용)
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
    timing_slot: str = "SLOT_1"  # ✅ 추가: 기본값 SLOT_1
    taken_at: datetime | None = None


class MedCheckCreateResponse(BaseModel):
    check_id: int
    guide_medication_id: int
    timing_slot: str  # ✅ 추가
    is_taken: bool
    taken_at: datetime


# ──────────────────────────────────────────
# ✅ 추가: 복약 기록 히스토리 (페이징)
# ──────────────────────────────────────────
class MedCheckHistoryItem(BaseModel):
    check_id: int
    guide_medication_id: int
    medication_name: str
    timing_slot: str  # SLOT_1 / SLOT_2 / SLOT_3
    slot_label: str  # "아침" / "저녁" 또는 "1회차" / "2회차"
    check_date: date
    is_taken: bool
    taken_at: datetime | None


class MedCheckHistoryResponse(BaseModel):
    total_count: int
    page: int
    size: int
    items: list[MedCheckHistoryItem]


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
    # ✅ 추가: 카카오 나에게 보내기 알림 여부
    is_kakao_noti: bool
    is_active: bool


class ReminderCreateRequest(BaseModel):
    reminder_time: time
    repeat_type: str = Field("RPT_DAILY", pattern="^(RPT_DAILY|RPT_WEEKDAY|RPT_CUSTOM)$")
    custom_days: list[int] | None = None
    is_browser_noti: bool = False
    is_email_noti: bool = False
    # ✅ 추가: 카카오 나에게 보내기 (카카오 로그인 사용자만 True 가능 — 서비스 레이어에서 검증)
    is_kakao_noti: bool = False


class ReminderPatchRequest(BaseModel):
    reminder_time: time | None = None
    repeat_type: str | None = Field(None, pattern="^(RPT_DAILY|RPT_WEEKDAY|RPT_CUSTOM)$")
    custom_days: list[int] | None = None
    is_browser_noti: bool | None = None
    is_email_noti: bool | None = None
    # ✅ 추가: 카카오 알림 수정 가능
    is_kakao_noti: bool | None = None
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
