# app/models/ai_settings.py
# ai_settings 테이블 매핑
# config_name: 'ANSWER_MODEL' | 'FILTER_MODEL'

from tortoise import fields
from tortoise.models import Model


class AISettings(Model):
    setting_id = fields.IntField(pk=True, generated=True)
    config_name = fields.CharField(max_length=50, unique=True)
    api_model = fields.CharField(max_length=50, default="gpt-4")
    system_prompt = fields.TextField()
    emergency_keywords = fields.TextField(null=True)
    temperature = fields.DecimalField(max_digits=3, decimal_places=2, default="0.70")
    max_tokens = fields.IntField(default=1000)
    min_threshold = fields.DecimalField(max_digits=3, decimal_places=2, default="0.50")
    auto_retry_count = fields.IntField(default=3)
    is_active = fields.BooleanField(default=False)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "ai_settings"
