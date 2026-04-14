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
    async def get_guides_by_user(
        self, user_id: int, period: str | None, status: str | None, page: int, size: int,
    ) -> tuple[int, list[Guide]]:
        qs = Guide.filter(user_id=user_id)

        if status:
            qs = qs.filter(guide_status_code=status)

        if period == "1M":
            cutoff = date.today() - timedelta(days=30)
            qs = qs.filter(created_at__date__gte=cutoff)
        elif period == "3M":
            cutoff = date.today() - timedelta(days=90)
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
        await guide.delete()

    async def create_medications(self, guide_id: int, medications: list[dict]) -> list[GuideMedication]:
        objs = [GuideMedication(guide_id=guide_id, **m) for m in medications]
        await GuideMedication.bulk_create(objs)
        return await GuideMedication.filter(guide_id=guide_id)

    async def get_medications(self, guide_id: int) -> list[GuideMedication]:
        return await GuideMedication.filter(guide_id=guide_id)

    async def get_conditions(self, guide_id: int) -> list[GuideCondition]:
        return await GuideCondition.filter(guide_id=guide_id)

    async def replace_conditions(self, guide_id: int, conditions: list[dict]) -> None:
        await GuideCondition.filter(guide_id=guide_id).delete()
        if conditions:
            objs = [GuideCondition(guide_id=guide_id, **c) for c in conditions]
            await GuideCondition.bulk_create(objs)

    async def get_latest_ai_results(
        self, guide_id: int, result_type: str | None = None
    ) -> list[GuideAiResult]:
        qs = GuideAiResult.filter(guide_id=guide_id)
        if result_type:
            qs = qs.filter(result_type_code=result_type)

        all_results = await qs.order_by("-version", "-created_at")
        seen: set[str] = set()
        latest: list[GuideAiResult] = []
        for r in all_results:
            if r.result_type_code not in seen:
                seen.add(r.result_type_code)
                latest.append(r)
        return latest

    async def create_ai_result(
        self, guide_id: int, result_type: str, content: dict, status: str
    ) -> GuideAiResult:
        latest = await GuideAiResult.filter(
            guide_id=guide_id, result_type_code=result_type
        ).order_by("-version").first()
        version = (latest.version + 1) if latest else 1

        return await GuideAiResult.create(
            guide_id=guide_id,
            result_type_code=result_type,
            content=content,
            status=status,
            version=version,
        )

    async def get_med_checks_by_date(self, guide_id: int, check_date: date) -> list[GuideMedCheck]:
        return await GuideMedCheck.filter(guide_id=guide_id, check_date=check_date)

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

    async def get_reminder(self, guide_id: int) -> GuideReminder | None:
        return await GuideReminder.filter(guide_id=guide_id).first()

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