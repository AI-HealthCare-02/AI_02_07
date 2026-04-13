from datetime import date, datetime, timezone

from fastapi import HTTPException, status

from app.dtos.guide_dto import (
    AiGenerateRequest,
    AiGenerateResponse,
    AiResultDetailItem,
    ConditionItem,
    ConditionsPutRequest,
    ConditionsResponse,
    GuideCreateRequest,
    GuideCreateResponse,
    GuideDetailResponse,
    GuideListItem,
    GuideListResponse,
    GuidePatchRequest,
    GuidePatchResponse,
    MedCheckCreateRequest,
    MedCheckCreateResponse,
    MedCheckItem,
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


class GuideService:
    def __init__(self) -> None:
        self._repo = GuideRepository()
        self._ai = AiGuideService()

    # ──────────────────────────────────────────
    # 가이드 목록 조회
    # ──────────────────────────────────────────
    async def list_guides(
        self, user_id: int, period: str | None, status: str | None, page: int, size: int
    ) -> GuideListResponse:
        total, guides = await self._repo.get_guides_by_user(user_id, period, status, page, size)

        today = date.today()
        items: list[GuideListItem] = []
        for g in guides:
            med_count = await self._repo.get_medications(g.guide_id)
            d_day: int | None = None
            if g.med_end_date and g.guide_status == "GS_ACTIVE":
                d_day = (g.med_end_date - today).days

            items.append(
                GuideListItem(
                    guide_id=g.guide_id,
                    title=g.title,
                    visit_date=g.visit_date,
                    med_start_date=g.med_start_date,
                    med_end_date=g.med_end_date,
                    d_day=d_day,
                    medication_count=len(med_count),
                    guide_status=g.guide_status,
                    input_method=g.input_method,
                )
            )
        return GuideListResponse(total_count=total, page=page, size=size, guides=items)

    # ──────────────────────────────────────────
    # 가이드 생성 (직접 입력)
    # ──────────────────────────────────────────
    async def create_guide(self, user_id: int, req: GuideCreateRequest) -> GuideCreateResponse:
        title = req.title or f"{req.diagnosis_name} 가이드"

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
                "patient_gender": req.patient_gender,
                "guide_status": "GS_ACTIVE",
                "input_method": "IM_MANUAL",
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
            guide_status=guide.guide_status,
            input_method=guide.input_method,
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
            guide_status=guide.guide_status,
            input_method=guide.input_method,
            medications=[
                MedicationDetailItem(
                    medication_id=m.medication_id,
                    medication_name=m.medication_name,
                    dosage=m.dosage,
                    frequency=m.frequency,
                    timing=m.timing,
                    duration_days=m.duration_days,
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
        return GuidePatchResponse(guide_id=guide.guide_id, title=guide.title, guide_status=guide.guide_status)

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

        diseases = [ConditionItem(condition_id=c.condition_id, name=c.name) for c in conditions if c.condition_type == "CT_DISEASE"]
        current_meds = [ConditionItem(condition_id=c.condition_id, name=c.name) for c in conditions if c.condition_type == "CT_CURRENT_MED"]
        allergies = [ConditionItem(condition_id=c.condition_id, name=c.name) for c in conditions if c.condition_type == "CT_ALLERGY"]

        return ConditionsResponse(diseases=diseases, current_meds=current_meds, allergies=allergies)

    async def replace_conditions(self, guide_id: int, user_id: int, req: ConditionsPutRequest) -> MessageResponse:
        await self._get_guide_or_404(guide_id, user_id)
        cond_dicts = [{"condition_type": c.type, "name": c.name} for c in req.conditions]
        await self._repo.replace_conditions(guide_id, cond_dicts)
        return MessageResponse(message="기저질환 정보가 업데이트되었습니다.")

    # ──────────────────────────────────────────
    # AI 가이드 생성
    # ──────────────────────────────────────────
    async def generate_ai_guide(
        self, guide_id: int, user_id: int, req: AiGenerateRequest
    ) -> AiGenerateResponse:
        guide = await self._get_guide_or_404(guide_id, user_id)
        meds = await self._repo.get_medications(guide_id)
        if not meds:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="처방 약물이 없습니다.")

        med_dicts = [{"medication_name": m.medication_name} for m in meds]
        result = await self._ai.generate(
            guide_id=guide_id,
            medications=med_dicts,
            patient_age=guide.patient_age,
            patient_gender=guide.patient_gender,
            diagnosis_name=guide.diagnosis_name,
            result_types=req.result_types,
        )

        # 결과 저장
        saved_results = []
        for r in result["results"]:
            saved = await self._repo.create_ai_result(
                guide_id=guide_id,
                result_type=r["result_type"],
                content=r["content"],
                status=r["status"],
            )
            saved_results.append({"ai_result_id": saved.ai_result_id, **r})

        return AiGenerateResponse(
            completed=result["completed"],
            failed=result["failed"],
            results=saved_results,
        )

    async def get_ai_results(
        self, guide_id: int, user_id: int, result_type: str | None
    ) -> list[AiResultDetailItem]:
        await self._get_guide_or_404(guide_id, user_id)
        results = await self._repo.get_latest_ai_results(guide_id, result_type)
        return [
            AiResultDetailItem(
                ai_result_id=r.ai_result_id,
                result_type=r.result_type,
                content=r.content,
                status=r.status,
                version=r.version,
                created_at=r.created_at,
            )
            for r in results
        ]

    # ──────────────────────────────────────────
    # 복약 체크
    # ──────────────────────────────────────────
    async def get_med_check(
        self, guide_id: int, user_id: int, check_date: date | None
    ) -> MedCheckResponse:
        guide = await self._get_guide_or_404(guide_id, user_id)
        target_date = check_date or date.today()
        meds = await self._repo.get_medications(guide_id)
        checks = await self._repo.get_med_checks_by_date(guide_id, target_date)
        check_map = {c.guide_medication_id: c for c in checks}

        day_count = (target_date - guide.med_start_date).days + 1
        taken_count = sum(1 for c in checks if c.is_taken)
        total = len(meds)
        progress = int(taken_count / total * 100) if total > 0 else 0

        items: list[MedCheckItem] = []
        for m in meds:
            c = check_map.get(m.medication_id)
            items.append(
                MedCheckItem(
                    check_id=c.check_id if c else None,
                    guide_medication_id=m.medication_id,
                    medication_name=m.medication_name,
                    timing=m.timing,
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

    async def create_med_check(
        self, guide_id: int, user_id: int, req: MedCheckCreateRequest
    ) -> MedCheckCreateResponse:
        await self._get_guide_or_404(guide_id, user_id)

        if await self._repo.check_duplicate(req.guide_medication_id, req.check_date):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="이미 해당 날짜에 복약 완료가 기록되어 있습니다.",
            )

        taken_at = req.taken_at or datetime.now(timezone.utc)
        check = await self._repo.create_med_check(
            guide_id=guide_id,
            guide_medication_id=req.guide_medication_id,
            check_date=req.check_date,
            taken_at=taken_at,
        )
        return MedCheckCreateResponse(
            check_id=check.check_id,
            guide_medication_id=check.guide_medication_id,
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
    # 복약 알림 (설정 저장만, 실제 발송 스케줄러 미포함)
    # ──────────────────────────────────────────
    async def get_reminder(self, guide_id: int, user_id: int) -> ReminderResponse:
        await self._get_guide_or_404(guide_id, user_id)
        reminder = await self._repo.get_reminder(guide_id)
        if not reminder:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="등록된 알림이 없습니다.")

        return ReminderResponse(
            reminder_id=reminder.reminder_id,
            reminder_time=reminder.reminder_time,
            repeat_type=reminder.repeat_type,
            custom_days=reminder.custom_days,
            is_browser_noti=reminder.is_browser_noti,
            is_email_noti=reminder.is_email_noti,
            is_active=reminder.is_active,
        )

    async def create_reminder(
        self, guide_id: int, user_id: int, req: ReminderCreateRequest
    ) -> ReminderSimpleResponse:
        await self._get_guide_or_404(guide_id, user_id)

        if await self._repo.get_reminder(guide_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="이미 알림이 등록되어 있습니다.",
            )

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

    async def patch_reminder(
        self, guide_id: int, user_id: int, req: ReminderPatchRequest
    ) -> ReminderSimpleResponse:
        await self._get_guide_or_404(guide_id, user_id)
        reminder = await self._repo.get_reminder(guide_id)
        if not reminder:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="등록된 알림이 없습니다.")

        reminder = await self._repo.update_reminder(reminder, req.model_dump(exclude_none=True))
        return ReminderSimpleResponse(
            reminder_id=reminder.reminder_id,
            reminder_time=reminder.reminder_time,
            is_active=reminder.is_active,
        )

    async def delete_reminder(self, guide_id: int, user_id: int) -> MessageResponse:
        await self._get_guide_or_404(guide_id, user_id)
        reminder = await self._repo.get_reminder(guide_id)
        if not reminder:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="등록된 알림이 없습니다.")

        await self._repo.delete_reminder(reminder)
        return MessageResponse(message="알림이 삭제되었습니다.")

    # ──────────────────────────────────────────
    # 내부 헬퍼
    # ──────────────────────────────────────────
    async def _get_guide_or_404(self, guide_id: int, user_id: int):
        guide = await self._repo.get_guide_by_id(guide_id, user_id)
        if not guide:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="가이드를 찾을 수 없습니다.")
        return guide
