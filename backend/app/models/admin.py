# app/models/admin.py
# ──────────────────────────────────────────────
# 관리자 계정 모델 — DDL의 admin_users 테이블에 대응
# 일반 사용자(users)와 분리된 별도 테이블
# ──────────────────────────────────────────────

from tortoise import fields
from tortoise.models import Model


class AdminUser(Model):
    """
    관리자 계정 (admin_users).
    일반 사용자 테이블(users)과 완전히 분리되어 있습니다.
    role_code는 공통코드 ADMIN_ROLE 그룹 참조.
    """

    admin_id = fields.BigIntField(pk=True, description="관리자 고유 ID")
    admin_email = fields.CharField(
        max_length=100,
        unique=True,
        description="관리자 이메일",
    )
    password = fields.CharField(max_length=255, description="관리자 암호")
    admin_name = fields.CharField(max_length=50, description="관리자 성함")

    # ── 권한 (공통코드: ADMIN_ROLE) ──
    role_grp = fields.CharField(
        max_length=20,
        default="ADMIN_ROLE",
        description="권한 그룹코드 (고정: ADMIN_ROLE)",
    )
    role_code = fields.CharField(
        max_length=20,
        default="MANAGER",
        description="권한 코드 → common_code(ADMIN_ROLE, code). 예: SUPER_ADMIN, MANAGER",
    )

    last_login_at = fields.DatetimeField(null=True, description="최종 로그인 일시")
    created_at = fields.DatetimeField(auto_now_add=True, description="등록일")

    class Meta:
        table = "admin_users"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"AdminUser(admin_id={self.admin_id}, email={self.admin_email})"
