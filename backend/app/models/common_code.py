# ===========================================================
# app/models/common_code.py (대안)
#
# Tortoise 가 복합 PK 를 지원하지 않으므로,
# ORM 모델과 DB 스키마를 분리합니다.
# ● DB 스키마: Raw SQL 의 (group_code, code) 복합 PK
# ● ORM 조회: Raw SQL 또는 group_code + code 필터로 조회
# ===========================================================


from tortoise import Tortoise, fields
from tortoise.models import Model


class CommonGroupCode(Model):
    """공통 그룹 코드"""

    group_code = fields.CharField(max_length=20, pk=True)
    group_name = fields.CharField(max_length=100)
    description = fields.TextField(null=True, default="")
    is_used = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "common_group_code"

    def __str__(self) -> str:
        return f"[{self.group_code}] {self.group_name}"


class CommonCode(Model):
    """
    공통 상세 코드

    ⚠️ DB PK 는 (group_code, code) 복합키이지만,
       Tortoise 에서는 단일 PK 를 요구하므로 code 를 pk 로 매핑합니다.
       같은 code 가 다른 그룹에 존재할 수 있으므로,
       반드시 group_code + code 로 조회하세요.

    ⚠️ generate_schemas=False 이므로 이 모델 정의가 DB 를 변경하지 않습니다.
    """

    # code 를 pk 로 사용 (실제 DB 에서는 복합 PK 의 일부)
    # 같은 code 가 다른 그룹에 존재 가능하므로 ORM 내부 pk 는 참고용
    code = fields.CharField(max_length=20, pk=True)
    group_code = fields.CharField(max_length=20, description="소속 그룹 코드")
    code_name = fields.CharField(max_length=100)
    sort_order = fields.IntField(default=0)
    is_used = fields.BooleanField(default=True)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "common_code"

    def __str__(self) -> str:
        return f"[{self.group_code}/{self.code}] {self.code_name}"

    # ── 편의 조회 메서드 (Raw SQL 사용) ──

    @classmethod
    async def get_by_group_and_code(cls, group_code: str, code: str) -> dict | None:
        """
        복합 PK 로 단일 코드를 조회합니다.

        Usage:
            result = await CommonCode.get_by_group_and_code('GENDER', 'MALE')
            # {'code': 'MALE', 'code_name': '남성', ...}
        """
        conn = Tortoise.get_connection("default")
        rows = await conn.execute_query_dict(
            "SELECT code, group_code, code_name, sort_order, is_used "
            "FROM common_code "
            "WHERE group_code = $1 AND code = $2 AND is_used = TRUE",
            [group_code, code],
        )
        return rows[0] if rows else None

    @classmethod
    async def get_codes_by_group(cls, group_code: str) -> list[dict]:
        """
        그룹에 속한 모든 활성 코드를 조회합니다.

        Usage:
            genders = await CommonCode.get_codes_by_group('GENDER')
            # [{'code': 'MALE', 'code_name': '남성', ...}, ...]
        """
        conn = Tortoise.get_connection("default")
        return await conn.execute_query_dict(
            "SELECT code, group_code, code_name, sort_order "
            "FROM common_code "
            "WHERE group_code = $1 AND is_used = TRUE "
            "ORDER BY sort_order",
            [group_code],
        )

    @classmethod
    async def validate(cls, group_code: str, code: str) -> bool:
        """
        group_code + code 조합이 유효한지 검증합니다.

        Usage:
            is_valid = await CommonCode.validate('GENDER', 'MALE')  # True
        """
        conn = Tortoise.get_connection("default")
        rows = await conn.execute_query_dict(
            "SELECT 1 FROM common_code WHERE group_code = $1 AND code = $2 AND is_used = TRUE LIMIT 1",
            [group_code, code],
        )
        return len(rows) > 0
