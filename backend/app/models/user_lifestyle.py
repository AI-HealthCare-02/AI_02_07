# app/models/user_lifestyle.py
# ──────────────────────────────────────────────
# 사용자 생활 습관 모델 — DDL의 user_lifestyle 테이블에 대응
# users와 1:1 관계 (user_id가 PK이자 FK)
#
# 모든 생활 습관 항목은 공통코드 참조:
#   pregnancy_grp(고정='PREGNANCY') + pregnancy_code
#   smoking_grp(고정='SMOKING') + smoking_code
#   drinking_grp(고정='DRINKING') + drinking_code
#   exercise_grp(고정='EXERCISE') + exercise_code
#   sleep_time_grp(고정='SLEEP_TIME') + sleep_time_code
# ──────────────────────────────────────────────

from tortoise import fields
from tortoise.models import Model


class UserLifestyle(Model):
    """
    사용자 생활 습관 (user_lifestyle).
    users 테이블과 1:1 관계. user_id가 PK이자 FK.

    DDL 컬럼과 1:1 매핑됩니다.
    모든 code 필드는 NULL 허용 (아직 입력하지 않은 경우).
    """

    # ── PK + FK ──
    # DDL: user_id BIGINT PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE
    # Tortoise에서 OneToOneField를 PK로 사용
    user = fields.OneToOneField(
        "models.User",
        related_name="lifestyle",
        pk=True,
        on_delete=fields.CASCADE,
        description="회원 ID (FK → users, PK)",
    )

    # ── 신체 정보 ──
    height = fields.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        description="키 (cm)",
    )
    weight = fields.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        description="몸무게 (kg)",
    )

    # ── 임신/수유 (공통코드: PREGNANCY) ──
    pregnancy_grp = fields.CharField(
        max_length=20,
        default="PREGNANCY",
        description="임신/수유 그룹코드 (고정: PREGNANCY)",
    )
    pregnancy_code = fields.CharField(
        max_length=20,
        null=True,
        description="임신/수유 코드 → common_code(PREGNANCY, code)",
    )

    # ── 흡연 (공통코드: SMOKING) ──
    smoking_grp = fields.CharField(
        max_length=20,
        default="SMOKING",
        description="흡연 그룹코드 (고정: SMOKING)",
    )
    smoking_code = fields.CharField(
        max_length=20,
        null=True,
        description="흡연 상태 코드 → common_code(SMOKING, code)",
    )

    # ── 음주 (공통코드: DRINKING) ──
    drinking_grp = fields.CharField(
        max_length=20,
        default="DRINKING",
        description="음주 그룹코드 (고정: DRINKING)",
    )
    drinking_code = fields.CharField(
        max_length=20,
        null=True,
        description="음주 빈도 코드 → common_code(DRINKING, code)",
    )

    # ── 운동 (공통코드: EXERCISE) ──
    exercise_grp = fields.CharField(
        max_length=20,
        default="EXERCISE",
        description="운동 그룹코드 (고정: EXERCISE)",
    )
    exercise_code = fields.CharField(
        max_length=20,
        null=True,
        description="운동 빈도 코드 → common_code(EXERCISE, code)",
    )

    # ── 수면 (공통코드: SLEEP_TIME) ──
    sleep_time_grp = fields.CharField(
        max_length=20,
        default="SLEEP_TIME",
        description="수면 그룹코드 (고정: SLEEP_TIME)",
    )
    sleep_time_code = fields.CharField(
        max_length=20,
        null=True,
        description="수면 시간 코드 → common_code(SLEEP_TIME, code)",
    )

    class Meta:
        table = "user_lifestyle"

    def __str__(self) -> str:
        return f"UserLifestyle(user_id={self.user_id})"
