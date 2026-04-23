import json
from datetime import date, datetime, timedelta

from app.models.guide import (
    Guide,
    GuideAiResult,
    GuideCondition,
    GuideMedCheck,
    GuideMedication,
    GuideReminder,
)


class GuideRepository:
    # ──────────────────────────────────────────
    # Guide CRUD
    # ──────────────────────────────────────────
    async def get_guides_by_user(
        self,
        user_id: int,
        period: str | None,
        status: str | None,
        page: int,
        size: int,
    ) -> tuple[int, list[Guide]]:
        qs = Guide.filter(user_id=user_id)

        if status:
            qs = qs.filter(guide_status_code=status)

        if period == "1M":
            cutoff = date.today() - timedelta(days=30)
            qs = qs.filter(created_at__date__gte=cutoff)
        elif period == "3M":
            m = date.today().month
            y = date.today().year
            if m <= 3:
                cutoff = date(y - 1, m + 9, 1)
            else:
                cutoff = date(y, m - 3, 1)
            qs = qs.filter(created_at__date__gte=cutoff)

        total = await qs.count()
        guides = await qs.order_by("-created_at").offset((page - 1) * size).limit(size)
        return total, guides

    async def get_guide_by_id(self, guide_id: int, user_id: int) -> Guide | None:
        return await Guide.filter(guide_id=guide_id, user_id=user_id).first()

    async def create_guide(self, user_id: int, data: dict) -> Guide:
        return await Guide.create(user_id=user_id, **data)

    async def update_guide(self, guide: Guide, data: dict) -> Guide:
        for k, v in data.items():
            setattr(guide, k, v)
        await guide.save()
        return guide

    async def soft_delete_guide(self, guide: Guide) -> None:
        # ✅ 수정: is_deleted 없으므로 guide_status_code를 EXPIRED로 변경
        guide.guide_status_code = "EXPIRED"
        await guide.save()

    # ──────────────────────────────────────────
    # GuideMedication
    # ──────────────────────────────────────────
    async def create_medications(self, guide_id: int, medications: list[dict]) -> list[GuideMedication]:
        objs = [GuideMedication(guide_id=guide_id, **m) for m in medications]
        await GuideMedication.bulk_create(objs)
        return await GuideMedication.filter(guide_id=guide_id)

    async def get_medications(self, guide_id: int) -> list[GuideMedication]:
        return await GuideMedication.filter(guide_id=guide_id)

    # ──────────────────────────────────────────
    # GuideCondition
    # ──────────────────────────────────────────
    async def get_conditions(self, guide_id: int) -> list[GuideCondition]:
        return await GuideCondition.filter(guide_id=guide_id)

    async def replace_conditions(self, guide_id: int, conditions: list[dict]) -> None:
        """DELETE + INSERT (PUT 시맨틱)"""
        await GuideCondition.filter(guide_id=guide_id).delete()
        if conditions:
            objs = [GuideCondition(guide_id=guide_id, **c) for c in conditions]
            await GuideCondition.bulk_create(objs)

    # ──────────────────────────────────────────
    # GuideAiResult
    # ──────────────────────────────────────────
    async def get_latest_ai_results(self, guide_id: int, result_type: str | None = None) -> list[GuideAiResult]:
        """result_type_code별 최신 버전만 반환"""
        # ✅ 수정: is_latest=True 필터로 최신 결과만 조회
        qs = GuideAiResult.filter(guide_id=guide_id, is_latest=True)
        if result_type:
            qs = qs.filter(result_type_code=result_type)
        return await qs.order_by("-created_at")

    async def create_ai_result(
        self, guide_id: int, result_type: str, content: dict, status: str
    ) -> GuideAiResult:
        # ✅ 수정: 기존 is_latest=True 결과를 False로 변경 후 새 결과 저장
        await GuideAiResult.filter(
            guide_id=guide_id,
            result_type_code=result_type,
            is_latest=True,
        ).update(is_latest=False)

        # 버전 증가
        latest = await GuideAiResult.filter(
            guide_id=guide_id, result_type_code=result_type
        ).order_by("-version").first()
        version = (latest.version + 1) if latest else 1

        # ✅ 수정: content dict → JSON 문자열로 저장, status 제거
        return await GuideAiResult.create(
            guide_id=guide_id,
            result_type_code=result_type,
            content=json.dumps(content, ensure_ascii=False),
            version=version,
            is_latest=True,
        )

    # ──────────────────────────────────────────
    # GuideMedCheck
    # ──────────────────────────────────────────
    async def get_med_checks_by_date(self, guide_id: int, check_date: date) -> list[GuideMedCheck]:
        return await GuideMedCheck.filter(guide_id=guide_id, check_date=check_date)

    async def get_med_checks_by_period(self, guide_id: int, start: date, end: date) -> list[GuideMedCheck]:
        return await GuideMedCheck.filter(
            guide_id=guide_id,
            check_date__gte=start,
            check_date__lte=end,
        )

    async def get_med_check(self, check_id: int, guide_id: int) -> GuideMedCheck | None:
        return await GuideMedCheck.filter(check_id=check_id, guide_id=guide_id).first()

    async def check_duplicate(self, guide_medication_id: int, check_date: date) -> bool:
        return await GuideMedCheck.filter(
            guide_medication_id=guide_medication_id, check_date=check_date
        ).exists()

    async def create_med_check(
        self, guide_id: int, guide_medication_id: int, check_date: date, taken_at: datetime
    ) -> GuideMedCheck:
        return await GuideMedCheck.create(
            guide_id=guide_id,
            guide_medication_id=guide_medication_id,
            check_date=check_date,
            taken_at=taken_at,
            is_taken=True,
        )

    async def delete_med_check(self, med_check: GuideMedCheck) -> None:
        await med_check.delete()

    # ──────────────────────────────────────────
    # GuideReminder
    # ──────────────────────────────────────────
    async def get_reminders(self, guide_id: int) -> list[GuideReminder]:
        return await GuideReminder.filter(guide_id=guide_id).order_by("reminder_time")

    async def get_reminder_by_id(self, reminder_id: int, guide_id: int) -> GuideReminder | None:
        return await GuideReminder.filter(reminder_id=reminder_id, guide_id=guide_id).first()

    async def create_reminder(self, guide_id: int, data: dict) -> GuideReminder:
        return await GuideReminder.create(guide_id=guide_id, **data)

    async def update_reminder(self, reminder: GuideReminder, data: dict) -> GuideReminder:
        for k, v in data.items():
            if v is not None:
                setattr(reminder, k, v)
        await reminder.save()
        return reminder

    async def delete_reminder(self, reminder: GuideReminder) -> None:
        await reminder.delete()
