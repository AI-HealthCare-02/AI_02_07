# app/dtos/common_code_dto.py
# ──────────────────────────────────────────────
# 공통 코드 관련 DTO
# 공통 코드 조회 API 응답에 사용
# ──────────────────────────────────────────────

from pydantic import BaseModel


class CommonCodeResponseDTO(BaseModel):
    """공통 코드 단일 항목 응답"""

    group_code: str
    code: str
    code_name: str
    sort_order: int

    class Config:
        from_attributes = True


class CommonGroupCodeResponseDTO(BaseModel):
    """공통 그룹 코드 + 하위 코드 목록 응답"""

    group_code: str
    group_name: str
    description: str | None = None
    codes: list[CommonCodeResponseDTO] = []

    class Config:
        from_attributes = True
