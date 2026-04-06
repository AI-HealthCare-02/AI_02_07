# app/models/user_disease.py
# ──────────────────────────────────────────────
# 사용자 기저질환 모델 — DDL의 user_diseases 테이블에 대응
# users와 1:N 관계
# (user_id, disease_name) UNIQUE 제약 있음
# ──────────────────────────────────────────────

from tortoise import fields
from tortoise.models import Model


class UserDisease(Model):
    """
    사용자별 기저질환 직접입력 내역 (user_diseases).
    사용자가 직접 텍스트로 입력합니다.
    """

    # DDL: disease_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY
    disease_id = fields.BigIntField(pk=True, description="질환 고유 ID")

    user = fields.ForeignKeyField(
        "models.User",
        related_name="diseases",
        on_delete=fields.CASCADE,
        description="회원 ID (FK → users)",
    )

    disease_name = fields.CharField(
        max_length=100,
        description="질환 명칭 (직접 입력)",
    )

    created_at = fields.DatetimeField(auto_now_add=True, description="등록일")

    class Meta:
        table = "user_diseases"
        unique_together = (("user", "disease_name"),)
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"UserDisease(id={self.disease_id}, name={self.disease_name})"
