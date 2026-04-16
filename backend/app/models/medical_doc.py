# app/models/medical_doc.py
# ──────────────────────────────────────────────
# 의료 문서 분석 모델 — 이승원 담당
# DDL의 doc_analysis_job / doc_analysis_result 테이블과 매핑
# ──────────────────────────────────────────────

from tortoise import fields
from tortoise.models import Model


class DocAnalysisJob(Model):
    """doc_analysis_job 테이블 — 분석 요청 및 상태 관리"""

    job_id = fields.BigIntField(pk=True, generated=True)
    user = fields.ForeignKeyField("models.User", related_name="doc_analysis_jobs")

    status_grp = fields.CharField(max_length=20, default="JOB_STATUS")
    status_code = fields.CharField(max_length=20, default="JOB_PENDING")

    doc_type_grp = fields.CharField(max_length=20, default="DOC_TYPE")
    doc_type_code = fields.CharField(max_length=20, null=True)

    error_message = fields.TextField(null=True)
    processing_time = fields.FloatField(null=True)
    is_deleted = fields.BooleanField(default=False)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "doc_analysis_job"
        ordering = ["-created_at"]


class DocAnalysisResult(Model):
    """doc_analysis_result 테이블 — 분석 결과 저장"""

    doc_result_id = fields.BigIntField(pk=True, generated=True)
    job = fields.OneToOneField("models.DocAnalysisJob", related_name="result")
    user = fields.ForeignKeyField("models.User", related_name="doc_analysis_results")

    doc_type_grp = fields.CharField(max_length=20, default="DOC_TYPE")
    doc_type_code = fields.CharField(max_length=20)

    ocr_status_grp = fields.CharField(max_length=20, default="OCR_STATUS")
    ocr_status_code = fields.CharField(max_length=20, default="OCR_PENDING")

    ocr_raw_text = fields.TextField(null=True)
    ocr_confidence = fields.IntField(null=True)
    overall_confidence = fields.FloatField(null=True)
    raw_summary = fields.TextField(null=True)

    # ── 전체 분석 결과 JSON 저장 (약품명, 복용법 등 포함) ──
    analysis_json = fields.JSONField(null=True)

    is_deleted = fields.BooleanField(default=False)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "doc_analysis_result"
        ordering = ["-created_at"]