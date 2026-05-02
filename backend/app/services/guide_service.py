import calendar
import json
import logging
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException, status

from app.dtos.guide_dto import (
    AiGenerateRequest,
    AiGenerateResponse,
    AiGenerateStatusResponse,
    AiResultDetailItem,
    ConditionItem,
    ConditionsPutRequest,
    ConditionsResponse,
    GuideCreateFromDocRequest,
    GuideCreateRequest,
    GuideCreateResponse,
    GuideDetailResponse,
    GuideListItem,
    GuideListResponse,
    GuidePatchRequest,
    GuidePatchResponse,
    MedCheckCreateRequest,
    MedCheckCreateResponse,
    MedCheckDayItem,
    MedCheckHistoryItem,  # ✅ 추가
    MedCheckHistoryResponse,  # ✅ 추가
    MedCheckItem,
    MedCheckMonthlyResponse,
    MedCheckResponse,
    MedicationDetailItem,
    MessageResponse,
    ReminderCreateRequest,
    ReminderPatchRequest,
    ReminderResponse,
    ReminderSimpleResponse,
)
from app.repositories.guide_repository import GuideRepository
from app.services.ai_guide_service import AiGuideService

logger = logging.getLogger(__name__)

# ── timing 한글 → DB 코드 변환 매핑 ──
TIMING_MAP = {
    "식후": "AFTER_MEAL",
    "밥 먹고": "AFTER_MEAL",
    "식후 즉시": "AFTER_MEAL_IMMEDIATE",
    "식후즉시": "AFTER_MEAL_IMMEDIATE",
    "식후 30분": "AFTER_MEAL_30",
    "식후30분": "AFTER_MEAL_30",
    "식전": "BEFORE_MEAL",
    "밥 먹기 전": "BEFORE_MEAL",
    "식전 30분": "BEFORE_MEAL_30",
    "식전30분": "BEFORE_MEAL_30",
    "식사 중": "WITH_MEAL",
    "식사중": "WITH_MEAL",
    "식사와 함께": "WITH_MEAL",
    "취침 전": "BEFORE_SLEEP",
    "취침전": "BEFORE_SLEEP",
    "자기 전": "BEFORE_SLEEP",
    "자기전": "BEFORE_SLEEP",
    "아침": "MORNING",
    "기상 후": "MORNING",
    "기상후": "MORNING",
    "필요 시": "AS_NEEDED",
    "필요시": "AS_NEEDED",
    "필요할 때": "AS_NEEDED",
}

# ── DB 코드 → 한글 역방향 매핑 ──
TIMING_DISPLAY_MAP = {
    "BEFORE_MEAL": "식전",
    "BEFORE_MEAL_30": "식전 30분",
    "AFTER_MEAL": "식후",
    "AFTER_MEAL_IMMEDIATE": "식후 즉시",
    "AFTER_MEAL_30": "식후 30분",
    "WITH_MEAL": "식사 중",
    "BEFORE_SLEEP": "취침 전",
    "MORNING": "기상 직후",
    "AS_NEEDED": "필요 시",
}

# ── RT_ 코드 → DB 코드 변환 매핑 ──
RESULT_TYPE_MAP = {
    "RT_MEDICATION": "SUMMARY",
    "RT_LIFESTYLE": "LIFESTYLE_TIP",
    "RT_CAUTION": "SIDE_EFFECT",
    "RT_DRUG_DETAIL": "EMERGENCY_SIGN",
}
RESULT_TYPE_REVERSE_MAP = {v: k for k, v in RESULT_TYPE_MAP.items()}

# ── 슬롯 폴백 레이블 (daily_slots 미설정 시 사용) ──
SLOT_LABELS = {
    "SLOT_1": "1회차",
    "SLOT_2": "2회차",
    "SLOT_3": "3회차",
}


def _parse_frequency(frequency: str | None) -> int:
    """frequency 문자열에서 1일 복약 횟수 파싱. 파싱 실패 시 1 반환."""
    if not frequency:
        return 1
    if "3회" in frequency:
        return 3
    if "2회" in frequency:
        return 2
    return 1


def _get_slots(count: int) -> list[str]:
    """복약 횟수에 따른 슬롯 목록 반환."""
    slots = ["SLOT_1", "SLOT_2", "SLOT_3"]
    return slots[:count]


def _get_slot_label(slot: str, daily_slots: list[str] | None) -> str:
    """
    ✅ 추가: 슬롯 라벨 결정.
    daily_slots가 설정된 경우 → 아침/점심/저녁/취침전 등 사용자 선택값 반환
    미설정 시 → 1회차/2회차/3회차 폴백
    """
    if daily_slots:
        idx = int(slot.replace("SLOT_", "")) - 1  # SLOT_1 → 0, SLOT_2 → 1
        if idx < len(daily_slots):
            return daily_slots[idx]
    return SLOT_LABELS.get(slot, slot)


class GuideService:
    def __init__(self) -> None:
        self._repo = GuideRepository()
        self._ai = AiGuideService()

    # ──────────────────────────────────────────
    # 가이드 목록 조회
    # ──────────────────────────────────────────
    async def list_guides(
        self,
        user_id: int,
        period: str | None,
        status: str | None,
        page: int,
        size: int,
        search: str | None = None,
    ) -> GuideListResponse:
        total, guides = await self._repo.get_guides_by_user(user_id, period, status, page, size, search=search)

        today = date.today()
        week_ago = today - timedelta(days=6)

        items: list[GuideListItem] = []
        for g in guides:
            meds = await self._repo.get_medications(g.guide_id)
            # ✅ 전체 슬롯 수 = 각 약물의 frequency 합산
            total_slots = sum(_parse_frequency(m.frequency) for m in meds)

            d_day: int | None = None
            if g.med_end_date and g.guide_status_code == "ACTIVE":
                d_day = (g.med_end_date - today).days

            today_checks = await self._repo.get_med_checks_by_date(g.guide_id, today)
            today_done = sum(1 for c in today_checks if c.is_taken)

            weekly_rate: float | None = None
            if total_slots > 0:
                week_checks = await self._repo.get_med_checks_by_period(g.guide_id, week_ago, today)
                days_elapsed = (today - max(week_ago, g.med_start_date)).days + 1 if g.med_start_date else 0
                if days_elapsed > 0:
                    possible = days_elapsed * total_slots
                    taken = sum(1 for c in week_checks if c.is_taken)
                    weekly_rate = round(taken / possible, 2)

            items.append(
                GuideListItem(
                    guide_id=g.guide_id,
                    title=g.title,
                    visit_date=g.visit_date,
                    med_start_date=g.med_start_date,
                    med_end_date=g.med_end_date,
                    d_day=d_day,
                    medication_count=len(meds),
                    guide_status=g.guide_status_code,
                    input_method=g.input_method_code,
                    hospital_name=g.hospital_name,
                    weekly_compliance_rate=weekly_rate,
                    today_progress_done=today_done,
                    today_progress_total=total_slots,
                )
            )
        return GuideListResponse(total_count=total, page=page, size=size, guides=items)

    # ──────────────────────────────────────────
    # 가이드 생성 (직접 입력)
    # ──────────────────────────────────────────
    async def create_guide(self, user_id: int, req: GuideCreateRequest) -> GuideCreateResponse:
        title = req.title or (f"{req.diagnosis_name} 가이드" if req.diagnosis_name else "건강 가이드")

        guide = await self._repo.create_guide(
            user_id=user_id,
            data={
                "title": title,
                "diagnosis_name": req.diagnosis_name,
                "hospital_name": req.hospital_name,
                "visit_date": req.visit_date,
                "med_start_date": req.med_start_date,
                "med_end_date": req.med_end_date,
                "patient_age": req.patient_age,
                "patient_gender_code": req.patient_gender,
                "guide_status_code": "ACTIVE",
                "input_method_code": "MANUAL",
            },
        )

        med_dicts = [m.model_dump() for m in req.medications]
        await self._repo.create_medications(guide.guide_id, med_dicts)

        if req.conditions:
            cond_dicts = [{"condition_type": c.type, "name": c.name} for c in req.conditions]
            await self._repo.replace_conditions(guide.guide_id, cond_dicts)

        return GuideCreateResponse(
            guide_id=guide.guide_id,
            title=guide.title,
            guide_status=guide.guide_status_code,
            input_method=guide.input_method_code,
        )

    # ──────────────────────────────────────────
    # 가이드 상세 조회
    # ──────────────────────────────────────────
    async def get_guide(self, guide_id: int, user_id: int) -> GuideDetailResponse:
        guide = await self._get_guide_or_404(guide_id, user_id)
        meds = await self._repo.get_medications(guide_id)

        return GuideDetailResponse(
            guide_id=guide.guide_id,
            title=guide.title,
            hospital_name=guide.hospital_name,
            diagnosis_name=guide.diagnosis_name,
            med_start_date=guide.med_start_date,
            med_end_date=guide.med_end_date,
            guide_status=guide.guide_status_code,
            input_method=guide.input_method_code,
            medications=[
                MedicationDetailItem(
                    guide_medication_id=m.guide_medication_id,
                    medication_name=m.medication_name,
                    dosage=m.dosage,
                    frequency=m.frequency,
                    timing=TIMING_DISPLAY_MAP.get(m.timing_code, m.timing_code),
                    duration_days=m.duration_days,
                    daily_slots=m.daily_slots,  # ✅ 추가
                )
                for m in meds
            ],
            created_at=guide.created_at,
        )

    # ──────────────────────────────────────────
    # 가이드 수정
    # ──────────────────────────────────────────
    async def patch_guide(self, guide_id: int, user_id: int, req: GuidePatchRequest) -> GuidePatchResponse:
        guide = await self._get_guide_or_404(guide_id, user_id)
        update_data = req.model_dump(exclude_none=True)
        guide = await self._repo.update_guide(guide, update_data)
        return GuidePatchResponse(
            guide_id=guide.guide_id,
            title=guide.title,
            guide_status=guide.guide_status_code,
        )

    # ──────────────────────────────────────────
    # 가이드 삭제 (소프트)
    # ──────────────────────────────────────────
    async def delete_guide(self, guide_id: int, user_id: int) -> MessageResponse:
        guide = await self._get_guide_or_404(guide_id, user_id)
        await self._repo.soft_delete_guide(guide)
        return MessageResponse(message="가이드가 삭제되었습니다.")

    # ──────────────────────────────────────────
    # Conditions (기저질환·복용약·알레르기)
    # ──────────────────────────────────────────
    async def get_conditions(self, guide_id: int, user_id: int) -> ConditionsResponse:
        await self._get_guide_or_404(guide_id, user_id)
        conditions = await self._repo.get_conditions(guide_id)

        diseases = [
            ConditionItem(condition_id=c.condition_id, name=c.name)
            for c in conditions
            if c.condition_type == "CT_DISEASE"
        ]
        current_meds = [
            ConditionItem(condition_id=c.condition_id, name=c.name)
            for c in conditions
            if c.condition_type == "CT_CURRENT_MED"
        ]
        allergies = [
            ConditionItem(condition_id=c.condition_id, name=c.name)
            for c in conditions
            if c.condition_type == "CT_ALLERGY"
        ]

        return ConditionsResponse(diseases=diseases, current_meds=current_meds, allergies=allergies)

    async def replace_conditions(self, guide_id: int, user_id: int, req: ConditionsPutRequest) -> MessageResponse:
        await self._get_guide_or_404(guide_id, user_id)
        cond_dicts = [{"condition_type": c.type, "name": c.name} for c in req.conditions]
        await self._repo.replace_conditions(guide_id, cond_dicts)
        return MessageResponse(message="기저질환 정보가 업데이트되었습니다.")

    # ──────────────────────────────────────────
    # AI 가이드 생성
    # ──────────────────────────────────────────
    async def generate_ai_guide(self, guide_id: int, user_id: int, req: AiGenerateRequest) -> AiGenerateResponse:
        guide = await self._get_guide_or_404(guide_id, user_id)
        meds = await self._repo.get_medications(guide_id)
        if not meds:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="처방 약물이 없습니다.")

        # ✅ 추가: 사용자 헬스 정보 조회 후 AI에 전달
        user_health_info = await self._get_user_health_info(user_id)

        med_dicts = [{"medication_name": m.medication_name} for m in meds]
        result = await self._ai.generate(
            guide_id=guide_id,
            medications=med_dicts,
            patient_age=guide.patient_age,
            patient_gender=guide.patient_gender_code,
            diagnosis_name=guide.diagnosis_name,
            result_types=req.result_types,
            user_health_info=user_health_info,  # ✅ 추가
        )

        saved_results = []
        for r in result["results"]:
            db_result_type = RESULT_TYPE_MAP.get(r["result_type"], r["result_type"])
            saved = await self._repo.create_ai_result(
                guide_id=guide_id,
                result_type=db_result_type,
                content=r["content"],
                status=r.get("status", "COMPLETED"),
            )
            content_raw = saved.content
            if isinstance(content_raw, dict):
                content = content_raw
            elif isinstance(content_raw, str):
                try:
                    content = json.loads(content_raw)
                except Exception:
                    content = {}
            else:
                content = {}

            saved_results.append(
                {
                    "ai_result_id": saved.ai_result_id,
                    "result_type": RESULT_TYPE_REVERSE_MAP.get(saved.result_type_code, saved.result_type_code),
                    "content": content,
                    "status": "COMPLETED",
                }
            )

        return AiGenerateResponse(
            completed=result["completed"],
            failed=result["failed"],
            results=saved_results,
        )

    async def get_ai_results(self, guide_id: int, user_id: int, result_type: str | None) -> list[AiResultDetailItem]:
        await self._get_guide_or_404(guide_id, user_id)
        db_result_type = RESULT_TYPE_MAP.get(result_type, result_type) if result_type else None
        results = await self._repo.get_latest_ai_results(guide_id, db_result_type)

        def _parse_content(raw):
            if isinstance(raw, dict):
                return raw
            if isinstance(raw, str):
                try:
                    return json.loads(raw)
                except Exception:
                    return {}
            return {}

        return [
            AiResultDetailItem(
                ai_result_id=r.ai_result_id,
                result_type=RESULT_TYPE_REVERSE_MAP.get(r.result_type_code, r.result_type_code),
                content=_parse_content(r.content),
                status="COMPLETED" if r.is_latest else "OLD",
                version=r.version,
                created_at=r.created_at,
            )
            for r in results
        ]

    # ──────────────────────────────────────────
    # 복약 체크
    # ──────────────────────────────────────────
    async def get_med_check(self, guide_id: int, user_id: int, check_date: date | None) -> MedCheckResponse:
        guide = await self._get_guide_or_404(guide_id, user_id)
        target_date = check_date or date.today()
        meds = await self._repo.get_medications(guide_id)
        checks = await self._repo.get_med_checks_by_date(guide_id, target_date)

        # ✅ 수정: (guide_medication_id, timing_slot) 복합 키로 체크 맵 구성
        check_map: dict[tuple[int, str], object] = {(c.guide_medication_id, c.timing_slot): c for c in checks}

        day_count = (target_date - guide.med_start_date).days + 1 if guide.med_start_date else 1
        taken_count = sum(1 for c in checks if c.is_taken)

        # ✅ 수정: 전체 슬롯 수 = 각 약물의 frequency 합산
        total_slots = sum(_parse_frequency(m.frequency) for m in meds)
        progress = int(taken_count / total_slots * 100) if total_slots > 0 else 0

        items: list[MedCheckItem] = []
        for m in meds:
            freq_count = _parse_frequency(m.frequency)
            slots = _get_slots(freq_count)
            daily_slots = m.daily_slots or []
            for slot in slots:
                c = check_map.get((m.guide_medication_id, slot))
                items.append(
                    MedCheckItem(
                        check_id=c.check_id if c else None,
                        guide_medication_id=m.guide_medication_id,
                        medication_name=m.medication_name,
                        timing=TIMING_DISPLAY_MAP.get(m.timing_code, m.timing_code),
                        timing_slot=slot,
                        # ✅ 수정: daily_slots 있으면 아침/점심/저녁/취침전, 없으면 1회차/2회차/3회차
                        slot_label=_get_slot_label(slot, daily_slots),
                        is_taken=bool(c and c.is_taken),
                        taken_at=c.taken_at if c else None,
                    )
                )

        return MedCheckResponse(
            date=target_date,
            day_count=day_count,
            progress_percent=progress,
            items=items,
        )

    async def create_med_check(self, guide_id: int, user_id: int, req: MedCheckCreateRequest) -> MedCheckCreateResponse:
        await self._get_guide_or_404(guide_id, user_id)

        # ✅ 수정: timing_slot 포함한 중복 체크
        if await self._repo.check_duplicate(req.guide_medication_id, req.check_date, req.timing_slot):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="이미 해당 날짜·회차에 복약 완료가 기록되어 있습니다.",
            )

        taken_at = req.taken_at or datetime.now(timezone.utc)
        check = await self._repo.create_med_check(
            guide_id=guide_id,
            guide_medication_id=req.guide_medication_id,
            check_date=req.check_date,
            timing_slot=req.timing_slot,
            taken_at=taken_at,
        )
        return MedCheckCreateResponse(
            check_id=check.check_id,
            guide_medication_id=check.guide_medication_id,
            timing_slot=check.timing_slot,
            is_taken=check.is_taken,
            taken_at=check.taken_at,
        )

    async def delete_med_check(self, guide_id: int, check_id: int, user_id: int) -> MessageResponse:
        await self._get_guide_or_404(guide_id, user_id)
        check = await self._repo.get_med_check(check_id, guide_id)
        if not check:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="복약 기록을 찾을 수 없습니다.")

        if check.check_date != date.today():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="복약 취소는 당일만 가능합니다.",
            )

        await self._repo.delete_med_check(check)
        return MessageResponse(message="복약 기록이 취소되었습니다.")

    # ──────────────────────────────────────────
    # ✅ 추가: 복약 기록 히스토리 페이징 조회
    # ──────────────────────────────────────────
    async def get_med_check_history(self, guide_id: int, user_id: int, page: int, size: int) -> MedCheckHistoryResponse:
        """복약 완료 기록을 날짜 최신순으로 페이징 조회."""
        await self._get_guide_or_404(guide_id, user_id)
        meds = await self._repo.get_medications(guide_id)
        # guide_medication_id → 약물 정보 맵
        med_map = {m.guide_medication_id: m for m in meds}

        total, checks = await self._repo.get_med_checks_paginated(guide_id, page, size)

        items: list[MedCheckHistoryItem] = []
        for c in checks:
            med = med_map.get(c.guide_medication_id)
            medication_name = med.medication_name if med else "알 수 없음"
            daily_slots = (med.daily_slots or []) if med else []
            slot_label = _get_slot_label(c.timing_slot, daily_slots)

            items.append(
                MedCheckHistoryItem(
                    check_id=c.check_id,
                    guide_medication_id=c.guide_medication_id,
                    medication_name=medication_name,
                    timing_slot=c.timing_slot,
                    slot_label=slot_label,
                    check_date=c.check_date,
                    is_taken=c.is_taken,
                    taken_at=c.taken_at,
                )
            )

        return MedCheckHistoryResponse(
            total_count=total,
            page=page,
            size=size,
            items=items,
        )

    # ──────────────────────────────────────────
    # 복약 알림
    # ──────────────────────────────────────────
    async def get_reminder(self, guide_id: int, user_id: int) -> ReminderResponse:
        await self._get_guide_or_404(guide_id, user_id)
        reminders = await self._repo.get_reminders(guide_id)
        if not reminders:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="등록된 알림이 없습니다.")
        r = reminders[0]
        return ReminderResponse(
            reminder_id=r.reminder_id,
            reminder_time=r.reminder_time,
            repeat_type=r.repeat_type,
            custom_days=r.custom_days,
            is_browser_noti=r.is_browser_noti,
            is_email_noti=r.is_email_noti,
            is_active=r.is_active,
        )

    async def create_reminder(self, guide_id: int, user_id: int, req: ReminderCreateRequest) -> ReminderSimpleResponse:
        await self._get_guide_or_404(guide_id, user_id)
        reminder = await self._repo.create_reminder(
            guide_id=guide_id,
            data={
                "reminder_time": req.reminder_time,
                "repeat_type": req.repeat_type,
                "custom_days": req.custom_days,
                "is_browser_noti": req.is_browser_noti,
                "is_email_noti": req.is_email_noti,
                "is_active": True,
            },
        )
        return ReminderSimpleResponse(
            reminder_id=reminder.reminder_id,
            reminder_time=reminder.reminder_time,
            is_active=reminder.is_active,
        )

    async def patch_reminder(self, guide_id: int, user_id: int, req: ReminderPatchRequest) -> ReminderSimpleResponse:
        await self._get_guide_or_404(guide_id, user_id)
        reminders = await self._repo.get_reminders(guide_id)
        if not reminders:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="등록된 알림이 없습니다.")
        reminder = await self._repo.update_reminder(reminders[0], req.model_dump(exclude_none=True))
        return ReminderSimpleResponse(
            reminder_id=reminder.reminder_id,
            reminder_time=reminder.reminder_time,
            is_active=reminder.is_active,
        )

    async def delete_reminder(self, guide_id: int, user_id: int) -> MessageResponse:
        await self._get_guide_or_404(guide_id, user_id)
        reminders = await self._repo.get_reminders(guide_id)
        if not reminders:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="등록된 알림이 없습니다.")
        await self._repo.delete_reminder(reminders[0])
        return MessageResponse(message="알림이 삭제되었습니다.")

    # ──────────────────────────────────────────
    # 복약 달력 — 월별 전체 날짜 상태 조회
    # ──────────────────────────────────────────
    async def get_med_check_monthly(
        self, guide_id: int, user_id: int, year: int, month: int
    ) -> MedCheckMonthlyResponse:
        guide = await self._get_guide_or_404(guide_id, user_id)
        meds = await self._repo.get_medications(guide_id)
        # ✅ 수정: 전체 슬롯 수 기준으로 달력 완료 여부 판단
        total_slots = sum(_parse_frequency(m.frequency) for m in meds)

        _, last_day = calendar.monthrange(year, month)
        month_start = date(year, month, 1)
        month_end = date(year, month, last_day)
        today = date.today()

        fetch_end = min(month_end, today)
        checks_raw = await self._repo.get_med_checks_by_period(guide_id, month_start, fetch_end)

        checks_by_date: dict[date, list] = {}
        for c in checks_raw:
            checks_by_date.setdefault(c.check_date, []).append(c)

        med_start = guide.med_start_date or month_start

        days: list[MedCheckDayItem] = []
        for day in range(1, last_day + 1):
            d = date(year, month, day)
            if d > today or d < med_start:
                day_status = "future"
            elif d not in checks_by_date:
                day_status = "missed"
            else:
                taken = sum(1 for c in checks_by_date[d] if c.is_taken)
                if total_slots == 0 or taken == 0:
                    day_status = "missed"
                elif taken >= total_slots:
                    day_status = "done"
                else:
                    day_status = "partial"
            days.append(MedCheckDayItem(date=d, status=day_status))

        return MedCheckMonthlyResponse(year=year, month=month, days=days)

    # ──────────────────────────────────────────
    # AI 가이드 생성 진행 상태 조회
    # ──────────────────────────────────────────
    async def get_ai_generate_status(self, guide_id: int, user_id: int) -> AiGenerateStatusResponse:
        await self._get_guide_or_404(guide_id, user_id)
        results = await self._repo.get_latest_ai_results(guide_id)

        if not results:
            return AiGenerateStatusResponse(status="pending", completed_types=[])

        completed_types = [
            RESULT_TYPE_REVERSE_MAP.get(r.result_type_code, r.result_type_code) for r in results if r.is_latest
        ]

        db_required = {"SUMMARY", "LIFESTYLE_TIP", "SIDE_EFFECT"}
        db_completed = {r.result_type_code for r in results if r.is_latest}
        if db_required.issubset(db_completed):
            overall = "done"
        else:
            overall = "processing"

        return AiGenerateStatusResponse(status=overall, completed_types=completed_types)

    # ──────────────────────────────────────────
    # 문서 분석 결과로 가이드 생성
    # ──────────────────────────────────────────
    async def create_guide_from_doc(self, user_id: int, req: GuideCreateFromDocRequest) -> GuideCreateResponse:
        from app.models.medical_doc import DocAnalysisResult

        result = await DocAnalysisResult.get_or_none(
            doc_result_id=req.doc_result_id,
            user__user_id=user_id,
            is_deleted=False,
        )
        logger.info(f"조회 결과: doc_result_id={req.doc_result_id}, user_id={user_id}, result={result}")
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="분석 결과를 찾을 수 없습니다.")

        analysis: dict = result.analysis_json or {}
        medications_raw: list = analysis.get("medications", [])
        if not medications_raw:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="분석 결과에 약물 정보가 없습니다.")

        diagnosis_name: str | None = analysis.get("diagnosis_name") or None
        hospital_name: str | None = analysis.get("hospital_name") or None
        visit_date_str: str | None = analysis.get("visit_date")
        visit_date = None
        if visit_date_str:
            try:
                visit_date = date.fromisoformat(visit_date_str)
            except (ValueError, TypeError):
                visit_date = None

        title = req.title or (
            f"{diagnosis_name} 가이드" if diagnosis_name else f"{hospital_name or '의료 문서'} 복약 가이드"
        )

        guide = await self._repo.create_guide(
            user_id=user_id,
            data={
                "title": title,
                "diagnosis_name": diagnosis_name,
                "hospital_name": hospital_name,
                "visit_date": visit_date,
                "med_start_date": req.med_start_date,
                "med_end_date": req.med_end_date,
                "guide_status_code": "ACTIVE",
                "input_method_code": "OCR",
            },
        )

        med_dicts = [
            {
                "medication_name": m.get("medication_name", ""),
                "dosage": m.get("dosage"),
                "frequency": m.get("frequency"),
                "timing_code": TIMING_MAP.get(m.get("timing", "")),
                "duration_days": m.get("duration_days"),
                "daily_slots": m.get("daily_slots"),  # ✅ 추가: 체크박스 선택값 저장
            }
            for m in medications_raw
            if m.get("medication_name")
        ]
        if med_dicts:
            await self._repo.create_medications(guide.guide_id, med_dicts)

        return GuideCreateResponse(
            guide_id=guide.guide_id,
            title=guide.title,
            guide_status=guide.guide_status_code,
            input_method=guide.input_method_code,
        )

    # ──────────────────────────────────────────
    # ✅ 추가: 사용자 헬스 정보 조회
    # ──────────────────────────────────────────
    async def _get_user_health_info(self, user_id: int) -> dict:
        """사용자 기저질환·알레르기·생활습관 조회 → AI 프롬프트용 dict 반환."""
        try:
            from app.models.user_allergy import UserAllergy
            from app.models.user_disease import UserDisease
            from app.models.user_lifestyle import UserLifestyle

            diseases = await UserDisease.filter(user_id=user_id).values_list("disease_name", flat=True)
            allergies = await UserAllergy.filter(user_id=user_id).values_list("allergy_name", flat=True)
            lifestyle = await UserLifestyle.filter(user_id=user_id).first()

            return {
                "diseases": list(diseases),
                "allergies": list(allergies),
                "smoking": lifestyle.smoking_code if lifestyle else None,
                "drinking": lifestyle.drinking_code if lifestyle else None,
                "exercise": lifestyle.exercise_code if lifestyle else None,
            }
        except Exception as e:
            logger.warning(f"사용자 헬스 정보 조회 실패 (user_id={user_id}): {e}")
            return {}

    # ──────────────────────────────────────────
    # 내부 헬퍼
    # ──────────────────────────────────────────
    async def _get_guide_or_404(self, guide_id: int, user_id: int):
        guide = await self._repo.get_guide_by_id(guide_id, user_id)
        if not guide:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="가이드를 찾을 수 없습니다.")
        return guide
