from tortoise import fields
from tortoise.models import Model


class Guide(Model):
    guide_id = fields.IntField(pk=True, generated=True)
    user = fields.ForeignKeyField("models.User", related_name="guides", on_delete=fields.CASCADE)
    title = fields.CharField(max_length=200, null=True)
    diagnosis_name = fields.CharField(max_length=500, null=True)
    hospital_name = fields.CharField(max_length=200, null=True)
    visit_date = fields.DateField(null=True)
    med_start_date = fields.DateField(null=True)
    med_end_date = fields.DateField(null=True)
    guide_status_grp = fields.CharField(max_length=20, default="GUIDE_STATUS")
    guide_status_code = fields.CharField(max_length=20)
    input_method_grp = fields.CharField(max_length=20, default="INPUT_METHOD")
    input_method_code = fields.CharField(max_length=20)
    patient_age = fields.IntField(null=True)
    patient_gender_grp = fields.CharField(max_length=20, default="GENDER")
    patient_gender_code = fields.CharField(max_length=20, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "health_guide"


class GuideMedication(Model):
    guide_medication_id = fields.IntField(pk=True, generated=True)
    guide = fields.ForeignKeyField("models.Guide", related_name="medications", on_delete=fields.CASCADE)
    medication_name = fields.CharField(max_length=200)
    dosage = fields.CharField(max_length=100, null=True)
    frequency = fields.CharField(max_length=100, null=True)
    timing_grp = fields.CharField(max_length=20, default="MED_TIMING")
    timing_code = fields.CharField(max_length=20, null=True)
    duration_days = fields.IntField(null=True)
    sort_order = fields.IntField(default=0)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "guide_medication"


class GuideCondition(Model):
    condition_id = fields.IntField(pk=True, generated=True)
    guide = fields.ForeignKeyField("models.Guide", related_name="conditions", on_delete=fields.CASCADE)
    condition_type_grp = fields.CharField(max_length=20, default="CONDITION_TYPE")
    condition_type_code = fields.CharField(max_length=20)
    condition_name = fields.CharField(max_length=200, null=True)
    sort_order = fields.IntField(default=0)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "health_condition"


class GuideAiResult(Model):
    ai_result_id = fields.IntField(pk=True, generated=True)
    guide = fields.ForeignKeyField("models.Guide", related_name="ai_results", on_delete=fields.CASCADE)
    result_type_grp = fields.CharField(max_length=20, default="RESULT_TYPE")
    result_type_code = fields.CharField(max_length=20)
    content = fields.TextField(null=True)
    status = fields.CharField(max_length=20, default="COMPLETED")
    version = fields.IntField(default=1)
    is_latest = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "guide_ai_result"


class GuideMedCheck(Model):
    check_id = fields.IntField(pk=True, generated=True)
    guide = fields.ForeignKeyField("models.Guide", related_name="med_checks", on_delete=fields.CASCADE)
    guide_medication = fields.ForeignKeyField(
        "models.GuideMedication", related_name="med_checks", on_delete=fields.CASCADE
    )
    check_date = fields.DateField()
    is_taken = fields.BooleanField(default=False)
    taken_at = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "med_check_log"
        unique_together = (("guide_medication_id", "check_date"),)


class GuideReminder(Model):
    reminder_id = fields.IntField(pk=True, generated=True)
    guide = fields.OneToOneField("models.Guide", related_name="reminder", on_delete=fields.CASCADE)
    reminder_time = fields.TimeField()
    repeat_type_grp = fields.CharField(max_length=20, default="REPEAT_TYPE")
    repeat_type_code = fields.CharField(max_length=20, null=True)
    custom_days = fields.JSONField(null=True)
    is_browser_noti = fields.BooleanField(default=False)
    is_email_noti = fields.BooleanField(default=False)
    is_active = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "med_reminder"