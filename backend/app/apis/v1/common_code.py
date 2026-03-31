# app/apis/v1/common_code.py
# ──────────────────────────────────────────────
# 공통 코드 조회 API
# 프론트엔드에서 셀렉트박스, 라디오버튼 등의 옵션을 구성할 때 사용
# ──────────────────────────────────────────────

from fastapi import APIRouter

from app.dtos.common_code_dto import CommonCodeResponseDTO, CommonGroupCodeResponseDTO
from app.dtos.common_dto import ResponseDTO
from app.services.common_code_service import get_all_groups, get_codes_by_group

router = APIRouter()


@router.get(
    "/groups",
    response_model=ResponseDTO[list[CommonGroupCodeResponseDTO]],
    summary="전체 그룹 코드 목록 조회",
)
async def list_group_codes():
    """
    사용 중인 전체 그룹 코드를 조회합니다.
    각 그룹의 하위 코드도 함께 반환합니다.
    """
    groups = await get_all_groups()
    result = []

    for group in groups:
        codes = await get_codes_by_group(group["group_code"])
        result.append(
            CommonGroupCodeResponseDTO(
                group_code=group["group_code"],
                group_name=group["group_name"],
                description=group.get("description"),
                codes=[CommonCodeResponseDTO(**c) for c in codes],
            )
        )

    return ResponseDTO(success=True, data=result)


@router.get(
    "/{group_code}",
    response_model=ResponseDTO[list[CommonCodeResponseDTO]],
    summary="특정 그룹의 상세 코드 목록 조회",
)
async def list_codes_by_group(group_code: str):
    """
    특정 그룹 코드에 속한 활성 상세 코드를 조회합니다.

    사용 예시 (프론트엔드):
        GET /api/v1/codes/GENDER → [{code: "MALE", code_name: "남성"}, ...]
        GET /api/v1/codes/SMOKING → [{code: "NON_SMOKER", code_name: "비흡연"}, ...]
    """
    codes = await get_codes_by_group(group_code.upper())
    data = [CommonCodeResponseDTO(**c) for c in codes]
    return ResponseDTO(success=True, data=data)
