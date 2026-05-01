from tortoise import fields
from tortoise.models import Model


class Guide(Model):
    """
    맞춤 건강 가이드 메인 테이블
    input_method_code: MANUAL(직접 입력) | OCR(문서 업로드, 승원 파트)
    guide_status_code: ACTIVE(복약 중) | COMPLETED(완료)
    """

    guide_id = fields.BigIntField(pk=True, generated=True)
    user = fields.ForeignKeyField("models.User", related_name="guides", on_delete=fields.CASCADE)
    title = fields.CharField(max_length=200, null=True)
    diagnosis_name = fields.CharField(max_length=500, null=True)
    hospital_name = fields.CharField(max_length=200, null=True)
    visit_date = fields.DateField(null=True)
    med_start_date = fields.DateField(null=True)
    med_end_date = fields.DateField(null=True)
    patient_age = fields.IntField(null=True)
    patient_gender_grp = fields.CharField(max_length=20, default="GENDER")
    patient_gender_code = fields.CharField(max_length=20, null=True)
    guide_status_grp = fields.CharField(max_length=20, default="GUIDE_STATUS")
    guide_status_code = fields.CharField(max_length=20, default="ACTIVE")
    input_method_grp = fields.CharField(max_length=20, default="INPUT_METHOD")
    input_method_code = fields.CharField(max_length=20, default="MANUAL")
    is_deleted = fields.BooleanField(default=False)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "health_guide"


class GuideMedication(Model):
    """가이드에 포함된 약물 정보"""

    guide_medication_id = fields.BigIntField(pk=True, generated=True)
    guide = fields.ForeignKeyField("models.Guide", related_name="medications", on_delete=fields.CASCADE)
    medication_name = fields.CharField(max_length=200)
    dosage = fields.CharField(max_length=100, null=True)
    frequency = fields.CharField(max_length=100, null=True)
    timing_grp = fields.CharField(max_length=20, default="MED_TIMING")
    timing_code = fields.CharField(max_length=20, null=True)
    duration_days = fields.IntField(null=True)
    # ✅ 추가: 사용자가 선택한 복약 시간대 (아침/점심/저녁/취침전)
    # 예: ["아침", "저녁"] — 분석 결과 화면에서 체크박스로 선택
    daily_slots = fields.JSONField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "guide_medication"


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
        table = "health_condition"


class GuideAiResult(Model):
    """
    AI 생성 결과 저장
    result_type_code: SUMMARY | LIFESTYLE_TIP | SIDE_EFFECT | EMERGENCY_SIGN
    is_latest: 최신 버전 여부
    """

    ai_result_id = fields.BigIntField(pk=True, generated=True)
    guide = fields.ForeignKeyField("models.Guide", related_name="ai_results", on_delete=fields.CASCADE)
    result_type_grp = fields.CharField(max_length=20, default="RESULT_TYPE")
    result_type_code = fields.CharField(max_length=20)
    content = fields.TextField(null=True)
    version = fields.IntField(default=1)
    is_latest = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "guide_ai_result"


class GuideMedCheck(Model):
    """
    복약 체크 기록
    당일만 취소 가능 (check_date == 오늘)
    timing_slot: SLOT_1 / SLOT_2 / SLOT_3 (1일 N회 복약 시 회차 구분)
    동일 약물·날짜·슬롯 중복 불가 (unique_together)
    """

    check_id = fields.IntField(pk=True)
    guide = fields.ForeignKeyField("models.Guide", related_name="med_checks", on_delete=fields.CASCADE)
    guide_medication = fields.ForeignKeyField(
        "models.GuideMedication", related_name="med_checks", on_delete=fields.CASCADE
    )
    check_date = fields.DateField()
    # ✅ 추가: 1일 N회 복약 회차 구분 (SLOT_1 / SLOT_2 / SLOT_3)
    timing_slot = fields.CharField(max_length=20, default="SLOT_1")
    is_taken = fields.BooleanField(default=True)
    taken_at = fields.DatetimeField()
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "med_check_log"
        # ✅ 수정: timing_slot 포함 복합 UNIQUE (같은 약·날짜·회차 중복 방지)
        unique_together = (("guide_medication_id", "check_date", "timing_slot"),)


class GuideReminder(Model):
    """
    복약 알림 설정
    repeat_type: RPT_DAILY | RPT_WEEKDAY | RPT_CUSTOM
    알림 채널: is_browser_noti | is_email_noti | is_kakao_noti
    is_kakao_noti: 카카오 나에게 보내기 (카카오 로그인 사용자만 가능)
    """

    reminder_id = fields.IntField(pk=True)
    guide = fields.ForeignKeyField("models.Guide", related_name="reminders", on_delete=fields.CASCADE)
    reminder_time = fields.TimeField()
    repeat_type = fields.CharField(max_length=20, default="RPT_DAILY")
    custom_days = fields.JSONField(null=True)
    is_browser_noti = fields.BooleanField(default=False)
    is_email_noti = fields.BooleanField(default=False)
    # ✅ 추가: 카카오 나에게 보내기 알림 여부 (카카오 로그인 사용자만 활성화 가능)
    is_kakao_noti = fields.BooleanField(default=False)
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "med_reminder"
