# app/models/system_error_log.py
# ──────────────────────────────────────────────
# 시스템 오류 로그 모델 — DDL의 system_error_logs 테이블에 대응
# ──────────────────────────────────────────────

from tortoise import fields
from tortoise.models import Model


class SystemErrorLog(Model):
    """
    시스템 오류 로그 (system_error_logs).
    API 요청 처리 중 발생한 에러를 DB에 기록합니다.
    """

    log_id = fields.BigIntField(pk=True, description="로그 고유 ID")
    user_id = fields.BigIntField(null=True, description="관련 유저 ID (로그인 중인 경우)")
    error_type = fields.CharField(
        max_length=100,
        null=True,
        description="에러 종류 (API_FAIL, DB_ERR 등)",
    )
    error_message = fields.TextField(description="에러 상세 메시지")
    stack_trace = fields.TextField(null=True, description="에러 스택 트레이스")
    request_url = fields.CharField(
        max_length=2048,
        null=True,
        description="문제가 발생한 API 주소",
    )
    created_at = fields.DatetimeField(auto_now_add=True, description="기록 일시")

    class Meta:
        table = "system_error_logs"
        ordering = ["-created_at"]
