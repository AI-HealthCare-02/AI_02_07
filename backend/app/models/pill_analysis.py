# app/models/pill_analysis.py
# ──────────────────────────────────────────────
# 알약 분석 모델 — 안은지 담당
# DDL의 uploaded_file / pill_analysis_history 테이블과 매핑
# ──────────────────────────────────────────────

from tortoise import fields
from tortoise.models import Model


class UploadedFile(Model):
    """uploaded_file 테이블"""

    file_id = fields.BigIntField(pk=True, generated=True)
    user = fields.ForeignKeyField("models.User", related_name="uploaded_files")
    original_name = fields.CharField(max_length=500)
    stored_name = fields.CharField(max_length=500)
    s3_bucket = fields.CharField(max_length=200)
    s3_key = fields.CharField(max_length=1000, unique=True)
    s3_url = fields.CharField(max_length=2000)
    content_type = fields.CharField(max_length=200, null=True)
    file_size = fields.BigIntField(default=0)
    file_extension = fields.CharField(max_length=20, null=True)
    file_category_grp = fields.CharField(max_length=20, default="FILE_CATEGORY")
    file_category_code = fields.CharField(max_length=20)
    is_deleted = fields.BooleanField(default=False)
    deleted_at = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "uploaded_file"
        ordering = ["-created_at"]


class PillAnalysisHistory(Model):
    """pill_analysis_history 테이블"""

    analysis_id = fields.BigIntField(pk=True, generated=True)
    user = fields.ForeignKeyField("models.User", related_name="pill_analyses")
    file = fields.ForeignKeyField("models.UploadedFile", related_name="pill_analyses")
    product_name = fields.CharField(max_length=500)
    active_ingredients = fields.TextField(null=True)
    efficacy = fields.TextField(null=True)
    usage_method = fields.TextField(null=True)
    warning = fields.TextField(null=True)
    caution = fields.TextField(null=True)
    interactions = fields.TextField(null=True)
    side_effects = fields.TextField(null=True)
    storage_method = fields.TextField(null=True)
    gpt_model_version = fields.CharField(max_length=50, null=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "pill_analysis_history"
        ordering = ["-created_at"]
