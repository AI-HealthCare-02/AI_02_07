# app/apis/v1/user.py
# ──────────────────────────────────────────────
# 사용자 API — 프로필, 생활습관, 알레르기, 기저질환
# DDL의 users / user_lifestyle / user_allergies / user_diseases
# ──────────────────────────────────────────────

from fastapi import APIRouter, Depends, status

from app.core.dependencies import get_current_user
from app.dtos.common_dto import ResponseDTO
from app.dtos.user_dto import (
    UserAgreementUpdateDTO,
    UserAllergyBulkCreateDTO,
    UserAllergyCreateDTO,
    UserAllergyResponseDTO,
    UserDeleteRequestDTO,
    UserDiseaseBulkCreateDTO,
    UserDiseaseCreateDTO,
    UserDiseaseResponseDTO,
    UserFullHealthProfileDTO,
    UserLifestyleResponseDTO,
    UserLifestyleUpdateDTO,
    UserProfileResponseDTO,
    UserProfileUpdateDTO,
)
from app.models.user import User
from app.services import user_service

router = APIRouter()


# ============================================================
# 프로필
# ============================================================


@router.get(
    "/me",
    response_model=ResponseDTO[UserProfileResponseDTO],
    summary="내 프로필 조회",
)
async def get_me(user: User = Depends(get_current_user)):
    """현재 로그인한 사용자의 프로필을 조회합니다."""
    profile = await user_service.get_user_profile(user)
    return ResponseDTO(success=True, data=profile)


@router.patch(
    "/me",
    response_model=ResponseDTO[UserProfileResponseDTO],
    summary="내 프로필 수정",
)
async def update_me(
    body: UserProfileUpdateDTO,
    user: User = Depends(get_current_user),
):
    """
    현재 사용자의 프로필을 수정합니다 (PATCH).
    변경할 필드만 전송하면 됩니다.
    """
    profile = await user_service.update_user_profile(user, body)
    return ResponseDTO(success=True, message="프로필 수정 성공", data=profile)


@router.patch(
    "/me/agreements",
    response_model=ResponseDTO[UserProfileResponseDTO],
    summary="동의 정보 수정",
)
async def update_agreements(
    body: UserAgreementUpdateDTO,
    user: User = Depends(get_current_user),
):
    """
    개인정보/민감정보/의료데이터 동의 상태를 변경합니다.
    True → 현재 시각으로 동의, False → 동의 철회(NULL).
    """
    profile = await user_service.update_user_agreements(user, body)
    return ResponseDTO(success=True, message="동의 정보 수정 성공", data=profile)


@router.delete(
    "/me",
    response_model=ResponseDTO,
    summary="회원 탈퇴",
)
async def delete_me(
    body: UserDeleteRequestDTO,
    user: User = Depends(get_current_user),
):
    """
    회원 탈퇴 (소프트 딜리트).
    일반 가입자는 비밀번호 확인이 필요합니다.
    OAuth 사용자는 비밀번호 없이 탈퇴 가능합니다.
    """
    await user_service.delete_user(user, body)
    return ResponseDTO(success=True, message="회원 탈퇴가 완료되었습니다.")


# ============================================================
# 전체 건강 프로필 (프로필 + 생활습관 + 알레르기 + 기저질환)
# ============================================================


@router.get(
    "/me/health-profile",
    response_model=ResponseDTO[UserFullHealthProfileDTO],
    summary="전체 건강 프로필 조회",
)
async def get_health_profile(user: User = Depends(get_current_user)):
    """
    사용자의 전체 건강 프로필을 한 번에 조회합니다.
    프로필 + 생활습관 + 알레르기 목록 + 기저질환 목록을 반환합니다.
    AI 챗봇이 사용자 컨텍스트를 구성할 때 이 API를 사용합니다.
    """
    full_profile = await user_service.get_full_health_profile(user)
    return ResponseDTO(success=True, data=full_profile)


# ============================================================
# 생활 습관
# ============================================================


@router.get(
    "/me/lifestyle",
    response_model=ResponseDTO[UserLifestyleResponseDTO | None],
    summary="생활 습관 조회",
)
async def get_lifestyle(user: User = Depends(get_current_user)):
    """
    현재 사용자의 생활 습관을 조회합니다.
    아직 입력하지 않았으면 data가 null입니다.
    """
    lifestyle = await user_service.get_user_lifestyle(user)
    return ResponseDTO(success=True, data=lifestyle)


@router.put(
    "/me/lifestyle",
    response_model=ResponseDTO[UserLifestyleResponseDTO],
    summary="생활 습관 등록/수정",
)
async def update_lifestyle(
    body: UserLifestyleUpdateDTO,
    user: User = Depends(get_current_user),
):
    """
    생활 습관을 등록하거나 수정합니다.
    레코드가 없으면 새로 생성, 있으면 업데이트합니다.
    코드 값은 공통코드 테이블에 존재해야 합니다.

    코드 값 확인: GET /api/v1/codes/{group_code}
        PREGNANCY → 임신/수유 상태 코드
        SMOKING   → 흡연 상태 코드
        DRINKING  → 음주 빈도 코드
        EXERCISE  → 운동 빈도 코드
        SLEEP_TIME → 수면 시간 코드
    """
    lifestyle = await user_service.update_user_lifestyle(user, body)
    return ResponseDTO(success=True, message="생활 습관 저장 성공", data=lifestyle)


# ============================================================
# 알레르기
# ============================================================


@router.get(
    "/me/allergies",
    response_model=ResponseDTO[list[UserAllergyResponseDTO]],
    summary="알레르기 목록 조회",
)
async def list_allergies(user: User = Depends(get_current_user)):
    """현재 사용자의 알레르기 목록을 조회합니다."""
    allergies = await user_service.get_user_allergies(user)
    return ResponseDTO(success=True, data=allergies)


@router.post(
    "/me/allergies",
    response_model=ResponseDTO[UserAllergyResponseDTO],
    status_code=status.HTTP_201_CREATED,
    summary="알레르기 추가",
)
async def create_allergy(
    body: UserAllergyCreateDTO,
    user: User = Depends(get_current_user),
):
    """알레르기 항목을 하나 추가합니다."""
    allergy = await user_service.create_user_allergy(user, body)
    return ResponseDTO(success=True, message="알레르기 추가 성공", data=allergy)


@router.post(
    "/me/allergies/bulk",
    response_model=ResponseDTO[list[UserAllergyResponseDTO]],
    status_code=status.HTTP_201_CREATED,
    summary="알레르기 일괄 추가",
)
async def bulk_create_allergies(
    body: UserAllergyBulkCreateDTO,
    user: User = Depends(get_current_user),
):
    """여러 알레르기를 한꺼번에 추가합니다. 이미 존재하는 항목은 무시됩니다."""
    allergies = await user_service.bulk_create_user_allergies(user, body)
    return ResponseDTO(
        success=True, message=f"{len(allergies)}건 추가 완료", data=allergies
    )


@router.delete(
    "/me/allergies/{allergy_id}",
    response_model=ResponseDTO,
    summary="알레르기 삭제",
)
async def delete_allergy(
    allergy_id: int,
    user: User = Depends(get_current_user),
):
    """특정 알레르기 항목을 삭제합니다."""
    await user_service.delete_user_allergy(user, allergy_id)
    return ResponseDTO(success=True, message="알레르기 삭제 성공")


@router.delete(
    "/me/allergies",
    response_model=ResponseDTO,
    summary="알레르기 전체 삭제",
)
async def delete_all_allergies(user: User = Depends(get_current_user)):
    """현재 사용자의 모든 알레르기를 삭제합니다."""
    count = await user_service.delete_all_user_allergies(user)
    return ResponseDTO(success=True, message=f"알레르기 {count}건 삭제 완료")


# ============================================================
# 기저질환
# ============================================================


@router.get(
    "/me/diseases",
    response_model=ResponseDTO[list[UserDiseaseResponseDTO]],
    summary="기저질환 목록 조회",
)
async def list_diseases(user: User = Depends(get_current_user)):
    """현재 사용자의 기저질환 목록을 조회합니다."""
    diseases = await user_service.get_user_diseases(user)
    return ResponseDTO(success=True, data=diseases)


@router.post(
    "/me/diseases",
    response_model=ResponseDTO[UserDiseaseResponseDTO],
    status_code=status.HTTP_201_CREATED,
    summary="기저질환 추가",
)
async def create_disease(
    body: UserDiseaseCreateDTO,
    user: User = Depends(get_current_user),
):
    """기저질환 항목을 하나 추가합니다."""
    disease = await user_service.create_user_disease(user, body)
    return ResponseDTO(success=True, message="기저질환 추가 성공", data=disease)


@router.post(
    "/me/diseases/bulk",
    response_model=ResponseDTO[list[UserDiseaseResponseDTO]],
    status_code=status.HTTP_201_CREATED,
    summary="기저질환 일괄 추가",
)
async def bulk_create_diseases(
    body: UserDiseaseBulkCreateDTO,
    user: User = Depends(get_current_user),
):
    """여러 기저질환을 한꺼번에 추가합니다. 이미 존재하는 항목은 무시됩니다."""
    diseases = await user_service.bulk_create_user_diseases(user, body)
    return ResponseDTO(
        success=True, message=f"{len(diseases)}건 추가 완료", data=diseases
    )


@router.delete(
    "/me/diseases/{disease_id}",
    response_model=ResponseDTO,
    summary="기저질환 삭제",
)
async def delete_disease(
    disease_id: int,
    user: User = Depends(get_current_user),
):
    """특정 기저질환 항목을 삭제합니다."""
    await user_service.delete_user_disease(user, disease_id)
    return ResponseDTO(success=True, message="기저질환 삭제 성공")


@router.delete(
    "/me/diseases",
    response_model=ResponseDTO,
    summary="기저질환 전체 삭제",
)
async def delete_all_diseases(user: User = Depends(get_current_user)):
    """현재 사용자의 모든 기저질환을 삭제합니다."""
    count = await user_service.delete_all_user_diseases(user)
    return ResponseDTO(success=True, message=f"기저질환 {count}건 삭제 완료")
