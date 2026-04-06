# app/dtos/common_dto.py
# ──────────────────────────────────────────────
# 공통 DTO (응답 래퍼, 페이지네이션 등)
# 모든 API 응답에 일관된 형식을 제공합니다.
# ──────────────────────────────────────────────

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ResponseDTO(BaseModel, Generic[T]):
    """
    공통 API 응답 래퍼.

    사용 예시:
        return ResponseDTO(
            success=True,
            message="사용자 조회 성공",
            data=user_data,
        )
    """

    success: bool = True
    message: str = ""
    data: T | None = None


class ErrorResponseDTO(BaseModel):
    """에러 응답"""

    success: bool = False
    message: str
    detail: str | None = None


class PaginationDTO(BaseModel):
    """페이지네이션 메타정보"""

    page: int = Field(ge=1, default=1)
    size: int = Field(ge=1, le=100, default=20)
    total: int = 0
    total_pages: int = 0


class PaginatedResponseDTO(BaseModel, Generic[T]):
    """페이지네이션 응답 래퍼"""

    success: bool = True
    message: str = ""
    data: list[T] = []
    pagination: PaginationDTO = PaginationDTO()
