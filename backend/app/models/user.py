# ===========================================================
# app/models/user.py
# 사용자 모델 — DDL의 users 테이블과 매핑
#
# ⚠️ gender_grp, provider_grp 등 고정값 컬럼은 DB CHECK 제약으로 보호되며,
#    ORM 에서는 default 값으로 설정합니다.
#    복합 FK (gender_grp, gender_code) 는 DB 레벨에서만 동작합니다.
# ===========================================================

from tortoise import fields
from tortoise.models import Model


class User(Model):
    """users 테이블"""

    user_id = fields.BigIntField(pk=True, generated=True, description="회원 고유 ID")
    email = fields.CharField(max_length=100, unique=True, description="이메일")
    password = fields.CharField(
        max_length=255, null=True, description="암호 (OAuth는 NULL)"
    )
    nickname = fields.CharField(max_length=50, description="닉네임")
    name = fields.CharField(max_length=50, description="이름")

    # 성별 (복합 FK 는 DB 레벨)
    gender_grp = fields.CharField(
        max_length=20, default="GENDER", description="고정: GENDER"
    )
    gender_code = fields.CharField(max_length=20, null=True, description="성별 코드")
    birth_date = fields.DateField(null=True, description="생년월일")

    # 가입 경로
    provider_grp = fields.CharField(
        max_length=20, default="PROVIDER", description="고정: PROVIDER"
    )
    provider_code = fields.CharField(
        max_length=20, default="LOCAL", description="가입 경로 코드"
    )
    provider_id = fields.CharField(
        max_length=255, null=True, description="OAuth 고유 ID"
    )

    # 상태
    is_suspended = fields.BooleanField(default=False, description="계정 정지 여부")
    deleted_at = fields.DatetimeField(null=True, description="탈퇴 일시")

    # 동의
    agreed_personal_info = fields.DatetimeField(
        null=True, description="개인정보 동의 일시"
    )
    agreed_sensitive_info = fields.DatetimeField(
        null=True, description="민감정보 동의 일시"
    )
    agreed_medical_data = fields.DatetimeField(
        null=True, description="의료문서 동의 일시"
    )

    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = "users"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"User({self.user_id}, {self.email})"

    @property
    def is_active(self) -> bool:
        """탈퇴하지 않고 정지되지 않은 활성 사용자인지"""
        return self.deleted_at is None and not self.is_suspended
