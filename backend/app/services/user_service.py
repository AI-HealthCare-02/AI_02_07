# app/services/user_service.py
# ──────────────────────────────────────────────
# 사용자 관련 비즈니스 로직
# 프로필 수정, 생활습관 CRUD, 알레르기/기저질환 CRUD,
# 전체 건강 프로필 조회, 회원 탈퇴
# ──────────────────────────────────────────────

import logging
from datetime import datetime, timezone

from fastapi import HTTPException, status

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
from app.models.user_allergy import UserAllergy
from app.models.user_disease import UserDisease
from app.models.user_lifestyle import UserLifestyle
from app.services.common_code_service import validate_common_code

logger = logging.getLogger(__name__)


# ============================================================
# 프로필
# ============================================================


async def get_user_profile(user: User) -> UserProfileResponseDTO:
    """사용자 프로필 조회"""
    return UserProfileResponseDTO(
        user_id=user.user_id,
        email=user.email,
        nickname=user.nickname,
        name=user.name,
        gender_code=user.gender_code,
        birth_date=user.birth_date,
        provider_code=user.provider_code,
        is_suspended=user.is_suspended,
        is_active=user.is_active,
        agreed_personal_info=user.agreed_personal_info,
        agreed_sensitive_info=user.agreed_sensitive_info,
        agreed_medical_data=user.agreed_medical_data,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


async def update_user_profile(
    user: User, body: UserProfileUpdateDTO
) -> UserProfileResponseDTO:
    """
    사용자 프로필 수정 (PATCH).
    전달된 필드만 업데이트합니다.
    """
    update_data = body.model_dump(exclude_unset=True)

    # 성별 코드 검증
    if "gender_code" in update_data and update_data["gender_code"] is not None:
        if not await validate_common_code("GENDER", update_data["gender_code"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"유효하지 않은 성별 코드입니다: {update_data['gender_code']}",
            )

    # 필드 업데이트
    for field, value in update_data.items():
        setattr(user, field, value)

    await user.save()
    logger.info(
        f"프로필 수정: user_id={user.user_id}, fields={list(update_data.keys())}"
    )

    return await get_user_profile(user)


async def update_user_agreements(
    user: User, body: UserAgreementUpdateDTO
) -> UserProfileResponseDTO:
    """
    동의 정보 업데이트.
    True → 현재 시각으로 기록, False → NULL로 초기화.
    """
    now = datetime.now(timezone.utc)
    update_data = body.model_dump(exclude_unset=True)

    if "agreed_personal_info" in update_data:
        user.agreed_personal_info = now if update_data["agreed_personal_info"] else None
    if "agreed_sensitive_info" in update_data:
        user.agreed_sensitive_info = (
            now if update_data["agreed_sensitive_info"] else None
        )
    if "agreed_medical_data" in update_data:
        user.agreed_medical_data = now if update_data["agreed_medical_data"] else None

    await user.save()
    logger.info(f"동의 정보 수정: user_id={user.user_id}")

    return await get_user_profile(user)


async def delete_user(user: User, body: UserDeleteRequestDTO) -> None:
    """
    회원 탈퇴 (소프트 딜리트).
    deleted_at에 현재 시각을 기록합니다.
    확인 문구 검증으로 실수를 방지합니다.
    """
    # 확인 문구 검증
    if body.confirm_text != "탈퇴합니다":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="탈퇴 확인 문구가 올바르지 않습니다. '탈퇴합니다'를 입력해주세요.",
        )

    user.deleted_at = datetime.now(timezone.utc)
    await user.save()
    logger.info(f"회원 탈퇴: user_id={user.user_id}")


# ============================================================
# 생활 습관
# ============================================================

# 생활 습관 코드 필드 → 공통코드 그룹 매핑
_LIFESTYLE_CODE_GROUPS: dict[str, str] = {
    "pregnancy_code": "PREGNANCY",
    "smoking_code": "SMOKING",
    "drinking_code": "DRINKING",
    "exercise_code": "EXERCISE",
    "sleep_time_code": "SLEEP_TIME",
}


async def get_user_lifestyle(user: User) -> UserLifestyleResponseDTO | None:
    """사용자 생활 습관 조회. 아직 입력하지 않았으면 None."""
    lifestyle = await UserLifestyle.get_or_none(user=user)
    if lifestyle is None:
        return None
    return UserLifestyleResponseDTO.model_validate(lifestyle)


async def update_user_lifestyle(
    user: User, body: UserLifestyleUpdateDTO
) -> UserLifestyleResponseDTO:
    """
    생활 습관 수정 (PATCH).
    레코드가 없으면 생성, 있으면 업데이트합니다.

    모든 코드 값은 공통코드 테이블에 존재하는지 검증합니다.
    """
    update_data = body.model_dump(exclude_unset=True)

    # 코드 값 검증
    for field_name, group_code in _LIFESTYLE_CODE_GROUPS.items():
        if field_name in update_data and update_data[field_name] is not None:
            if not await validate_common_code(group_code, update_data[field_name]):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"유효하지 않은 코드입니다: {group_code}.{update_data[field_name]}",
                )

    # 생성 또는 업데이트
    lifestyle = await UserLifestyle.get_or_none(user=user)

    if lifestyle is None:
        # 신규 생성
        lifestyle = await UserLifestyle.create(user=user, **update_data)
        logger.info(f"생활 습관 생성: user_id={user.user_id}")
    else:
        # 기존 업데이트
        for field, value in update_data.items():
            setattr(lifestyle, field, value)
        await lifestyle.save()
        logger.info(
            f"생활 습관 수정: user_id={user.user_id}, fields={list(update_data.keys())}"
        )

    return UserLifestyleResponseDTO.model_validate(lifestyle)


# ============================================================
# 알레르기
# ============================================================


async def get_user_allergies(user: User) -> list[UserAllergyResponseDTO]:
    """사용자 알레르기 목록 조회"""
    allergies = await UserAllergy.filter(user=user).order_by("created_at")
    return [UserAllergyResponseDTO.model_validate(a) for a in allergies]


async def create_user_allergy(
    user: User, body: UserAllergyCreateDTO
) -> UserAllergyResponseDTO:
    """알레르기 단일 추가"""
    # 중복 체크 (DB unique 제약도 있지만, 명확한 에러 메시지를 위해)
    existing = await UserAllergy.get_or_none(user=user, allergy_name=body.allergy_name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"이미 등록된 알레르기입니다: {body.allergy_name}",
        )

    allergy = await UserAllergy.create(user=user, allergy_name=body.allergy_name)
    logger.info(f"알레르기 추가: user_id={user.user_id}, name={body.allergy_name}")

    return UserAllergyResponseDTO.model_validate(allergy)


async def bulk_create_user_allergies(
    user: User,
    body: UserAllergyBulkCreateDTO,
) -> list[UserAllergyResponseDTO]:
    """알레르기 일괄 추가 (중복 무시)"""
    created = []
    for name in body.allergy_names:
        name = name.strip()
        if not name:
            continue
        existing = await UserAllergy.get_or_none(user=user, allergy_name=name)
        if existing is None:
            allergy = await UserAllergy.create(user=user, allergy_name=name)
            created.append(UserAllergyResponseDTO.model_validate(allergy))

    logger.info(f"알레르기 일괄 추가: user_id={user.user_id}, count={len(created)}")
    return created


async def delete_user_allergy(user: User, allergy_id: int) -> None:
    """알레르기 삭제"""
    allergy = await UserAllergy.get_or_none(allergy_id=allergy_id, user=user)
    if allergy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="알레르기 항목을 찾을 수 없습니다.",
        )
    await allergy.delete()
    logger.info(f"알레르기 삭제: user_id={user.user_id}, allergy_id={allergy_id}")


async def delete_all_user_allergies(user: User) -> int:
    """사용자의 모든 알레르기 삭제. 삭제된 건수 반환."""
    count = await UserAllergy.filter(user=user).delete()
    logger.info(f"알레르기 전체 삭제: user_id={user.user_id}, count={count}")
    return count


# ============================================================
# 기저질환
# ============================================================


async def get_user_diseases(user: User) -> list[UserDiseaseResponseDTO]:
    """사용자 기저질환 목록 조회"""
    diseases = await UserDisease.filter(user=user).order_by("created_at")
    return [UserDiseaseResponseDTO.model_validate(d) for d in diseases]


async def create_user_disease(
    user: User, body: UserDiseaseCreateDTO
) -> UserDiseaseResponseDTO:
    """기저질환 단일 추가"""
    existing = await UserDisease.get_or_none(user=user, disease_name=body.disease_name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"이미 등록된 기저질환입니다: {body.disease_name}",
        )

    disease = await UserDisease.create(user=user, disease_name=body.disease_name)
    logger.info(f"기저질환 추가: user_id={user.user_id}, name={body.disease_name}")

    return UserDiseaseResponseDTO.model_validate(disease)


async def bulk_create_user_diseases(
    user: User,
    body: UserDiseaseBulkCreateDTO,
) -> list[UserDiseaseResponseDTO]:
    """기저질환 일괄 추가 (중복 무시)"""
    created = []
    for name in body.disease_names:
        name = name.strip()
        if not name:
            continue
        existing = await UserDisease.get_or_none(user=user, disease_name=name)
        if existing is None:
            disease = await UserDisease.create(user=user, disease_name=name)
            created.append(UserDiseaseResponseDTO.model_validate(disease))

    logger.info(f"기저질환 일괄 추가: user_id={user.user_id}, count={len(created)}")
    return created


async def delete_user_disease(user: User, disease_id: int) -> None:
    """기저질환 삭제"""
    disease = await UserDisease.get_or_none(disease_id=disease_id, user=user)
    if disease is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="기저질환 항목을 찾을 수 없습니다.",
        )
    await disease.delete()
    logger.info(f"기저질환 삭제: user_id={user.user_id}, disease_id={disease_id}")


async def delete_all_user_diseases(user: User) -> int:
    """사용자의 모든 기저질환 삭제. 삭제된 건수 반환."""
    count = await UserDisease.filter(user=user).delete()
    logger.info(f"기저질환 전체 삭제: user_id={user.user_id}, count={count}")
    return count


# ============================================================
# 전체 건강 프로필
# ============================================================


async def get_full_health_profile(user: User) -> UserFullHealthProfileDTO:
    """
    사용자의 전체 건강 프로필을 조회합니다.
    프로필 + 생활습관 + 알레르기 + 기저질환을 한 번에 반환합니다.
    채팅 AI가 사용자 컨텍스트를 구성할 때 이 함수를 호출합니다.
    """
    profile = await get_user_profile(user)
    lifestyle = await get_user_lifestyle(user)
    allergies = await get_user_allergies(user)
    diseases = await get_user_diseases(user)

    return UserFullHealthProfileDTO(
        profile=profile,
        lifestyle=lifestyle,
        allergies=allergies,
        diseases=diseases,
    )
