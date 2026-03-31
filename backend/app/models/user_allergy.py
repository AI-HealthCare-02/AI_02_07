# app/models/user_allergy.py
# ──────────────────────────────────────────────
# 사용자 알레르기 모델 — DDL의 user_allergies 테이블에 대응
# users와 1:N 관계
# (user_id, allergy_name) UNIQUE 제약 있음
# ──────────────────────────────────────────────

from tortoise import fields
from tortoise.models import Model


class UserAllergy(Model):
    """
    사용자별 알레르기 직접입력 내역 (user_allergies).
    사용자가 직접 텍스트로 입력합니다.
    """

    # DDL: allergy_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY
    allergy_id = fields.BigIntField(pk=True, description="알레르기 고유 ID")

    user = fields.ForeignKeyField(
        "models.User",
        related_name="allergies",
        on_delete=fields.CASCADE,
        description="회원 ID (FK → users)",
    )

    allergy_name = fields.CharField(
        max_length=100,
        description="알레르기 명칭 (직접 입력)",
    )

    created_at = fields.DatetimeField(auto_now_add=True, description="등록일")

    class Meta:
        table = "user_allergies"
        unique_together = (("user", "allergy_name"),)
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"UserAllergy(id={self.allergy_id}, name={self.allergy_name})"
