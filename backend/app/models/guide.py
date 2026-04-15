from tortoise import fields
from tortoise.models import Model


class Guide(Model):
    """
    맞춤 건강 가이드 메인 테이블
    input_method: IM_MANUAL(직접 입력) | IM_DOCUMENT(문서 업로드, 승원 파트)
    guide_status: GS_ACTIVE(복약 중) | GS_COMPLETED(완료)
    """

    guide_id = fields.IntField(pk=True)
    user = fields.ForeignKeyField("models.User", related_name="guides", on_delete=fields.CASCADE)
    title = fields.CharField(max_length=200)
    diagnosis_name = fields.CharField(max_length=200)
    hospital_name = fields.CharField(max_length=200, null=True)
    visit_date = fields.DateField(null=True)
    med_start_date = fields.DateField()
    med_end_date = fields.DateField(null=True)
    patient_age = fields.IntField(null=True)
    patient_gender = fields.CharField(max_length=20, null=True)  # GD_MALE | GD_FEMALE
    guide_status = fields.CharField(max_length=20, default="GS_ACTIVE")
    input_method = fields.CharField(max_length=20, default="IM_MANUAL")
    is_deleted = fields.BooleanField(default=False)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "guides"


class GuideMedication(Model):
    """가이드에 포함된 약물 정보"""

    medication_id = fields.IntField(pk=True)
    guide = fields.ForeignKeyField("models.Guide", related_name="medications", on_delete=fields.CASCADE)
    medication_name = fields.CharField(max_length=200)
    dosage = fields.CharField(max_length=100, null=True)         # 1회 용량
    frequency = fields.CharField(max_length=50, null=True)       # 복용 횟수
    timing = fields.CharField(max_length=200, null=True)         # 식전/식후 (복수 선택 시 쉼표 구분)
    duration_days = fields.IntField(null=True)                   # 투약 기간(일)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "guide_medications"


class GuideCondition(Model):
    """
    기저질환 · 복용 중인 약 · 알레르기
    condition_type: CT_DISEASE | CT_CURRENT_MED | CT_ALLERGY
    """

    condition_id = fields.IntField(pk=True)
    guide = fields.ForeignKeyField("models.Guide", related_name="conditions", on_delete=fields.CASCADE)
    condition_type = fields.CharField(max_length=30)
    name = fields.CharField(max_length=200)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "guide_conditions"


class GuideAiResult(Model):
    """
    AI 생성 결과 저장
    result_type: RT_MEDICATION | RT_LIFESTYLE | RT_CAUTION
    status: COMPLETED | FAILED
    version: 재생성 시 증가
    """

    ai_result_id = fields.IntField(pk=True)
    guide = fields.ForeignKeyField("models.Guide", related_name="ai_results", on_delete=fields.CASCADE)
    result_type = fields.CharField(max_length=30)
    content = fields.JSONField()
    status = fields.CharField(max_length=20, default="COMPLETED")
    version = fields.IntField(default=1)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "guide_ai_results"


class GuideMedCheck(Model):
    """
    복약 체크 기록
    당일만 취소 가능 (check_date == 오늘)
    동일 약물·날짜 중복 불가 (unique_together)
    """

    check_id = fields.IntField(pk=True)
    guide = fields.ForeignKeyField("models.Guide", related_name="med_checks", on_delete=fields.CASCADE)
    guide_medication = fields.ForeignKeyField(
        "models.GuideMedication", related_name="med_checks", on_delete=fields.CASCADE
    )
    check_date = fields.DateField()
    is_taken = fields.BooleanField(default=True)
    taken_at = fields.DatetimeField()
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "guide_med_checks"
        unique_together = (("guide_medication_id", "check_date"),)


class GuideReminder(Model):
    """
    복약 알림 설정 (가이드당 1개)
    repeat_type: RPT_DAILY | RPT_WEEKDAY | RPT_CUSTOM
    ※ 1차 배포: 설정 저장만, 실제 발송 스케줄러(Celery beat) 미포함
    ※ 카카오 알림톡 제외
    """

    reminder_id = fields.IntField(pk=True)
    guide = fields.OneToOneField("models.Guide", related_name="reminder", on_delete=fields.CASCADE)
    reminder_time = fields.TimeField()                           # HH:MM:SS
    repeat_type = fields.CharField(max_length=20, default="RPT_DAILY")
    custom_days = fields.JSONField(null=True)                    # RPT_CUSTOM일 때 요일 목록
    is_browser_noti = fields.BooleanField(default=False)
    is_email_noti = fields.BooleanField(default=False)
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "guide_reminders"
